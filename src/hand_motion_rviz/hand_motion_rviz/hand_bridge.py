"""Receive newline-delimited JSON curls for both hands and publish JointState."""
import argparse
import json
import math
import socket
import threading

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


FINGERS = ('thumb', 'index', 'middle', 'ring', 'little')
HANDS = ('left', 'right')
FINGER_JOINTS = (
    (('thumb_cmc_joint', 0.75), ('thumb_mcp_joint', 1.05), ('thumb_ip_joint', 1.10)),
    (('index_mcp_joint', 1.15), ('index_pip_joint', 1.35), ('index_dip_joint', 0.95)),
    (('middle_mcp_joint', 1.15), ('middle_pip_joint', 1.35), ('middle_dip_joint', 0.95)),
    (('ring_mcp_joint', 1.15), ('ring_pip_joint', 1.35), ('ring_dip_joint', 0.95)),
    (('little_mcp_joint', 1.15), ('little_pip_joint', 1.35), ('little_dip_joint', 0.95)),
)
JOINTS = [f'{hand}_{joint}'
          for hand in HANDS
          for finger_joints in FINGER_JOINTS
          for joint, _ in finger_joints]


class HandBridge(Node):
    def __init__(self, port: int, demo: bool):
        super().__init__('hand_bridge')
        self.publisher = self.create_publisher(JointState, 'joint_states', 10)
        self.curls = {hand: [0.0] * len(FINGERS) for hand in HANDS}
        self.curls_lock = threading.Lock()
        self.demo = demo
        self.start_time = self.get_clock().now().nanoseconds / 1e9
        self.create_timer(1 / 30, self.publish_state)
        if not demo:
            threading.Thread(target=self.receive_loop, args=(port,), daemon=True).start()
            self.get_logger().info(f'Waiting for Mac hand-tracker on TCP port {port}')
        else:
            self.get_logger().info('Demo mode: animating hand without a camera')

    def receive_loop(self, port: int):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', port))
        server.listen(1)
        while rclpy.ok():
            connection, address = server.accept()
            self.get_logger().info(f'Hand tracker connected: {address[0]}')
            with connection, connection.makefile('r') as stream:
                for line in stream:
                    try:
                        data = json.loads(line)
                        hands = data['hands']
                        if not isinstance(hands, dict):
                            raise TypeError('hands must be an object')
                        parsed = {}
                        for hand in HANDS:
                            values = hands[hand]
                            if len(values) != len(FINGERS):
                                raise ValueError(f'expected five curls for {hand} hand')
                            parsed[hand] = [max(0.0, min(1.0, float(value)))
                                            for value in values]
                        with self.curls_lock:
                            self.curls = parsed
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                        self.get_logger().warning(f'Ignoring invalid tracker data: {error}')

    def publish_state(self):
        if self.demo:
            elapsed = self.get_clock().now().nanoseconds / 1e9 - self.start_time
            with self.curls_lock:
                self.curls = {
                    hand: [(math.sin(elapsed * 1.7 + index * 0.55 + hand_index * math.pi) + 1.0) / 2.0
                           for index in range(len(FINGERS))]
                    for hand_index, hand in enumerate(HANDS)
                }
        with self.curls_lock:
            curls = {hand: values[:] for hand, values in self.curls.items()}
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = JOINTS
        # A single curl value drives the three anatomical joints of each finger.
        message.position = [curl * maximum
                            for hand in HANDS
                            for curl, finger_joints in zip(curls[hand], FINGER_JOINTS)
                            for _, maximum in finger_joints]
        self.publisher.publish(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--demo', action='store_true')
    args, ros_args = parser.parse_known_args()
    rclpy.init(args=ros_args)
    node = HandBridge(args.port, args.demo)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
