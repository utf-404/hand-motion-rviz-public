"""Opt-in ROS integration: run after sourcing ROS with HAND_RVIZ_ROS_TESTS=1."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest


@unittest.skipUnless(os.environ.get('HAND_RVIZ_ROS_TESTS') == '1',
                     'set HAND_RVIZ_ROS_TESTS=1 in a sourced ROS environment')
class RosBridgeTests(unittest.TestCase):
    def test_joint_publication_stale_disconnect_reconnect_and_shutdown(self):
        for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(shutdown_signal=shutdown_signal):
                self.run_bridge_lifecycle(shutdown_signal)

    def run_bridge_lifecycle(self, shutdown_signal):
        import rclpy
        from sensor_msgs.msg import JointState

        root = Path(__file__).resolve().parents[1]
        package_path = str(root / 'src/hand_motion_rviz')
        sys.path.insert(0, package_path)
        from hand_motion_rviz.hand_bridge import FINGER_JOINTS, JOINTS

        # Use a separate DDS domain to avoid existing desktop ROS nodes.
        old_domain = os.environ.get('ROS_DOMAIN_ID')
        os.environ['ROS_DOMAIN_ID'] = str(100 + os.getpid() % 50)
        env = dict(os.environ, PYTHONPATH=package_path + os.pathsep + os.environ.get('PYTHONPATH', ''))
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        log = tempfile.TemporaryFile(mode='w+')
        process = node = peer = None
        try:
            rclpy.init()
            node = rclpy.create_node('hand_bridge_integration_probe')
            messages = []
            subscription = node.create_subscription(JointState, 'joint_states', messages.append, 10)
            process = subprocess.Popen(
                [sys.executable, '-c', 'from hand_motion_rviz.hand_bridge import main; main()',
                 '--port', str(port), '--stale-timeout', '0.6'],
                env=env, stdout=log, stderr=subprocess.STDOUT)

            def wait_for(predicate, description, timeout=5):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    rclpy.spin_once(node, timeout_sec=0.05)
                    if messages and predicate(messages[-1]):
                        return messages[-1]
                    if process.poll() is not None:
                        log.seek(0)
                        self.fail('bridge exited unexpectedly: ' + log.read())
                self.fail('timed out waiting for ' + description)

            opened = lambda msg: len(msg.position) == 36 and all(v == 0 for v in msg.position)
            wait_for(opened, 'initial open hands')
            peer = socket.create_connection(('127.0.0.1', port), timeout=1)
            frame = {'hands': {'left': [0.8] * 5, 'right': [0.8] * 5},
                     'wrist_rpy': {'left': [0.2, -0.4, 1.1], 'right': [-0.3, 0.5, -1.2]}}
            expected = [0.8 * maximum for _ in range(2)
                        for finger in FINGER_JOINTS for _, maximum in finger]
            expected += [1.1, -0.4, 0.2, -1.2, 0.5, -0.3]
            bent = lambda msg: len(msg.position) == 36 and all(
                abs(actual - target) < 1e-8 for actual, target in zip(msg.position, expected))
            peer.sendall((json.dumps(frame) + '\n').encode())
            message = wait_for(bent, '30 bent finger joints and 6 wrist rotation joints')
            self.assertEqual(list(message.name), JOINTS)
            self.assertGreater(message.header.stamp.sec, 0)
            peer.sendall((json.dumps({'hands': frame['hands']}) + '\n').encode())
            legacy_expected = expected[:30] + [0.0] * 6
            wait_for(lambda msg: len(msg.position) == 36 and all(
                abs(actual - target) < 1e-8 for actual, target in zip(msg.position, legacy_expected)),
                'legacy frame resets wrist rotation')
            peer.sendall((json.dumps(frame) + '\n').encode())
            wait_for(bent, 'rotation restored after legacy frame')
            wait_for(opened, 'stale-data open hands')
            peer.settimeout(1)
            self.assertEqual(peer.recv(1), b'')
            peer.close()
            peer = socket.create_connection(('127.0.0.1', port), timeout=1)
            peer.sendall((json.dumps(frame) + '\n').encode())
            wait_for(bent, 'reconnected bent joints')
            peer.close()
            peer = None
            wait_for(opened, 'disconnect open hands')
            peer = socket.create_connection(('127.0.0.1', port), timeout=1)
            peer.sendall((json.dumps(frame) + '\n').encode())
            wait_for(bent, 'active tracker before shutdown')
            process.send_signal(shutdown_signal)
            process.wait(timeout=4)
            log.seek(0)
            output = log.read()
            self.assertEqual(process.returncode, 0, output)
            self.assertNotIn('Traceback', output)
            self.assertNotIn("publisher's context is invalid", output)
            node.destroy_subscription(subscription)
        finally:
            if peer is not None:
                peer.close()
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            if node is not None:
                node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
            log.close()
            if old_domain is None:
                os.environ.pop('ROS_DOMAIN_ID', None)
            else:
                os.environ['ROS_DOMAIN_ID'] = old_domain


if __name__ == '__main__':
    unittest.main()
