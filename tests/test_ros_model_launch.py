"""Opt-in full installed launch/TF regression; never opens RViz or a camera."""
import json
import math
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
class RosModelLaunchTests(unittest.TestCase):
    def test_installed_model_rotates_both_palms_at_swapped_mounts(self):
        import rclpy
        from tf2_ros import Buffer, TransformListener
        from test_hand_orientation import landmarks

        root = Path(__file__).resolve().parents[1]
        setup = root / 'install/setup.bash'
        if not setup.exists():
            self.skipTest('build with colcon before running the full model launch test')
        sys.path.insert(0, str(root / 'src/hand_motion_rviz/tracker'))
        from hand_orientation import wrist_rpy

        old_domain = os.environ.get('ROS_DOMAIN_ID')
        os.environ['ROS_DOMAIN_ID'] = str(170 + os.getpid() % 10)
        peer = node = process = None
        log = tempfile.TemporaryFile(mode='w+')
        try:
            rclpy.init()
            node = rclpy.create_node('wrist_model_tf_probe')
            buffer = Buffer()
            listener = TransformListener(buffer, node)
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            process = subprocess.Popen(
                ['/bin/bash', '-c', 'source "$1" && exec ros2 launch hand_motion_rviz '
                 'hand_rviz.launch.py rviz:=false "port:=$2"', '_', str(setup), str(port)],
                cwd=root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            expected = {'left': (.3, -.4, .9), 'right': (-.2, .5, -.8)}
            frame = {'hands': {'left': [0] * 5, 'right': [0] * 5},
                     'wrist_rpy': {side: wrist_rpy(landmarks(side, rpy), side)
                                   for side, rpy in expected.items()}}

            def quaternion(rpy):
                r, p, y = [v / 2 for v in rpy]
                cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
                return (sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
                        cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy)

            deadline = time.monotonic() + 10
            verified = False
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                if peer is None:
                    try:
                        peer = socket.create_connection(('127.0.0.1', port), timeout=.1)
                    except OSError:
                        pass
                if peer is not None:
                    peer.sendall((json.dumps(frame) + '\n').encode())
                rclpy.spin_once(node, timeout_sec=.05)
                if not all(buffer.can_transform('hands_base', side + '_palm', rclpy.time.Time())
                           for side in expected):
                    continue
                verified = True
                for side, rpy in expected.items():
                    tf = buffer.lookup_transform('hands_base', side + '_palm', rclpy.time.Time()).transform
                    q = tf.rotation
                    actual, target = (q.x, q.y, q.z, q.w), quaternion(rpy)
                    error = min(max(abs(a - b) for a, b in zip(actual, target)),
                                max(abs(a + b) for a, b in zip(actual, target)))
                    verified = verified and error < 1e-6
                    self.assertAlmostEqual(tf.translation.y, -.13 if side == 'left' else .13)
                if verified:
                    break
            log.seek(0)
            self.assertTrue(verified, 'missing expected palm TF: ' + log.read()[-4000:])
            # Launch forwards this signal to its children; all must exit cleanly.
            os.killpg(process.pid, signal.SIGINT)
            process.wait(timeout=5)
            log.seek(0)
            output = log.read()
            self.assertEqual(process.returncode, 0, output[-4000:])
            self.assertNotIn('Traceback', output)
            self.assertNotIn('[ERROR]', output)
        finally:
            if peer is not None:
                peer.close()
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
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
