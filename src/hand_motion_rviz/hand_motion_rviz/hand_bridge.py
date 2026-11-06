"""Receive newline-delimited JSON curls for both hands and publish JointState."""
import argparse
import math
import signal

import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import JointState

from .tracker_stream import TrackerServer, positive_seconds


FINGERS = ('thumb', 'index', 'middle', 'ring', 'little')
HANDS = ('left', 'right')
FINGER_JOINTS = (
    (('thumb_cmc_joint', 0.75), ('thumb_mcp_joint', 1.05), ('thumb_ip_joint', 1.10)),
    (('index_mcp_joint', 1.15), ('index_pip_joint', 1.35), ('index_dip_joint', 0.95)),
    (('middle_mcp_joint', 1.15), ('middle_pip_joint', 1.35), ('middle_dip_joint', 0.95)),
    (('ring_mcp_joint', 1.15), ('ring_pip_joint', 1.35), ('ring_dip_joint', 0.95)),
    (('little_mcp_joint', 1.15), ('little_pip_joint', 1.35), ('little_dip_joint', 0.95)),
)
FINGER_JOINT_NAMES = [f'{hand}_{joint}'
                      for hand in HANDS
                      for finger_joints in FINGER_JOINTS
                      for joint, _ in finger_joints]
WRIST_JOINTS = [f'{hand}_wrist_{axis}_joint'
                for hand in HANDS for axis in ('yaw', 'pitch', 'roll')]
JOINTS = FINGER_JOINT_NAMES + WRIST_JOINTS


class HandBridge(Node):
    def __init__(self, port: int, demo: bool, stale_timeout: float = 1.0):
        super().__init__('hand_bridge')
        self.publisher = self.create_publisher(JointState, 'joint_states', 10)
        self.tracker = None
        self.demo = demo
        self.start_time = self.get_clock().now().nanoseconds / 1e9
        self.create_timer(1 / 30, self.publish_state)
        if not demo:
            try:
                self.tracker = TrackerServer(
                    port=port, stale_timeout=stale_timeout,
                    on_status=self.log_tracker_status).start()
            except BaseException:
                super().destroy_node()
                raise
            self.get_logger().info(f'Waiting for hand tracker on TCP port {port}')
        else:
            self.get_logger().info('Demo mode: animating hands without a camera')

    def log_tracker_status(self, status):
        # ROS signal handlers may shut down the context before socket cleanup.
        if self.context.ok():
            self.get_logger().info(f'Hand tracker status: {status}')

    def destroy_node(self):
        if self.tracker is not None:
            self.tracker.stop()
        return super().destroy_node()

    def publish_state(self):
        if self.demo:
            elapsed = self.get_clock().now().nanoseconds / 1e9 - self.start_time
            curls = {
                hand: [(math.sin(elapsed * 1.7 + index * 0.55 + hand_index * math.pi) + 1.0) / 2.0
                       for index in range(len(FINGERS))]
                for hand_index, hand in enumerate(HANDS)
            }
            wrists = {
                hand: [0.35 * math.sin(elapsed * 0.8 + hand_index * math.pi),
                       0.30 * math.sin(elapsed * 0.6),
                       0.45 * math.sin(elapsed * 0.7 + hand_index * math.pi)]
                for hand_index, hand in enumerate(HANDS)
            }
        else:
            pose = self.tracker.pose_snapshot()
            curls, wrists = pose['hands'], pose['wrist_rpy']
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = JOINTS
        # A single curl value drives the three anatomical joints of each finger.
        positions = [curl * maximum
                     for hand in HANDS
                     for curl, finger_joints in zip(curls[hand], FINGER_JOINTS)
                     for _, maximum in finger_joints]
        # URDF chain is yaw(Z) -> pitch(Y) -> roll(X), i.e. Rz * Ry * Rx.
        message.position = positions + [value for hand in HANDS for value in reversed(wrists[hand])]
        self.publisher.publish(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--stale-timeout', type=positive_seconds, default=1.0,
                        help='Seconds without a valid frame before opening both hands')
    args, ros_args = parser.parse_known_args()
    # Keep the context alive until the receiver and node have been cleaned up.
    # rclpy's asynchronous signal shutdown can invalidate a running publish/wait.
    rclpy.init(args=ros_args, signal_handler_options=SignalHandlerOptions.NO)
    node = None
    previous_handlers = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, signal.default_int_handler)
        node = HandBridge(args.port, args.demo, args.stale_timeout)
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # A process-group interrupt can also be forwarded again by ROS launch.
        # Finish cleanup before restoring handlers so the second signal cannot
        # interrupt socket/thread/node destruction halfway through.
        for signum in previous_handlers:
            signal.signal(signum, signal.SIG_IGN)
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
