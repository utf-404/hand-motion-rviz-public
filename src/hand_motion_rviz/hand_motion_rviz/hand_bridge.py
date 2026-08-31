"""Receive newline-delimited JSON finger curls over TCP and publish JointState."""
import argparse
import json
import math
import socket
import threading

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


FINGERS = ('thumb', 'index', 'middle', 'ring', 'little')
JOINTS = [f'{finger}_joint' for finger in FINGERS]


class HandBridge(Node):
    def __init__(self, port: int, demo: bool):
        super().__init__('hand_bridge')
        self.publisher = self.create_publisher(JointState, 'joint_states', 10)
        self.curls = [0.0] * len(FINGERS)
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
                        values = data['curls']
                        if len(values) != len(FINGERS):
                            raise ValueError('expected five curls')
                        self.curls = [max(0.0, min(1.0, float(value))) for value in values]
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                        self.get_logger().warning(f'Ignoring invalid tracker data: {error}')

    def publish_state(self):
        if self.demo:
            elapsed = self.get_clock().now().nanoseconds / 1e9 - self.start_time
            self.curls = [(math.sin(elapsed * 1.7 + index * 0.55) + 1.0) / 2.0
                          for index in range(len(FINGERS))]
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = JOINTS
        # 0 is open; 1.45 rad is a comfortably closed finger.
        message.position = [curl * 1.45 for curl in self.curls]
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
