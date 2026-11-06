"""Protocol and real localhost transport regressions; no ROS/camera required."""
import json
from pathlib import Path
import socket
import struct
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'hand_motion_rviz'))
from hand_motion_rviz.tracker_stream import (TrackerServer, neutral_wrists, open_hands,
                                           parse_frame, parse_pose_frame, positive_seconds)


def frame(value=0.7, **metadata):
    return (json.dumps({'hands': {'left': [value] * 5, 'right': [value] * 5},
                        **metadata}) + '\n').encode()


def eventually(predicate, timeout=1.5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError('condition not reached before deadline')


class ParseFrameTests(unittest.TestCase):
    def test_wrist_pose_accepts_radians_and_legacy_frames_default_to_neutral(self):
        self.assertEqual(parse_pose_frame(frame())['wrist_rpy'], neutral_wrists())
        wrists = {'left': [-2.3, 0.5, 2.7], 'right': [1.2, -0.2, -1.6]}
        pose = parse_pose_frame(frame(0.2, wrist_rpy=wrists))
        self.assertEqual(pose['hands']['left'], [0.2] * 5)
        self.assertEqual(pose['wrist_rpy'], wrists)
        self.assertEqual(parse_frame(frame(0.2, wrist_rpy=wrists)), pose['hands'])

    def test_malformed_rotation_rejects_whole_frame(self):
        invalid = [None, [], {}, {'left': [0, 0, 0]},
                   {'left': [0, 0], 'right': [0, 0, 0]}]
        invalid += [{'left': [0, value, 0], 'right': [0, 0, 0]}
                    for value in [True, '0', None, float('nan'), float('inf'), -float('inf')]]
        for wrists in invalid:
            with self.subTest(wrists=wrists), self.assertRaises(ValueError):
                parse_frame(frame(0.8, wrist_rpy=wrists))

    def test_legacy_and_metadata_frames_clamp_finite_numbers(self):
        self.assertEqual(parse_frame(frame(-0.2)), open_hands())
        self.assertEqual(parse_frame(frame(1.4))['right'], [1.0] * 5)
        self.assertEqual(parse_frame(frame(0.2, frame_id=4, captured_at=99999999999))['left'], [0.2] * 5)

    def test_rejects_invalid_shapes_and_nonfinite_or_nonnumeric_values(self):
        invalid = [b'null', b'[]', b'{}', b'{"hands": []}',
                   b'{"hands": {"left": [0,0,0,0,0]}}',
                   b'{"hands": {"left": "00000", "right": [0,0,0,0,0]}}']
        invalid += [frame(x) for x in [True, False, '0.5', None,
                                      float('nan'), float('inf'), -float('inf')]]
        invalid += [frame(0).replace(b'0,', b'1e999,', 1), b'\xff', b'{']
        for wire in invalid:
            with self.subTest(wire=wire[:100]):
                with self.assertRaises((ValueError, UnicodeError)):
                    parse_frame(wire)

    def test_timeout_requires_finite_positive_seconds(self):
        for value in ['nan', 'inf', '-inf', '0', '-1']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                positive_seconds(value)
        self.assertEqual(positive_seconds('0.25'), 0.25)


class TrackerServerTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.server = TrackerServer(port=0, host='127.0.0.1', stale_timeout=0.3,
                                    on_status=self.events.append).start()
        self.addCleanup(self.server.stop)

    def connect(self):
        connection = socket.create_connection(('127.0.0.1', self.server.port), timeout=1)
        self.addCleanup(connection.close)
        return connection

    def test_fragmented_and_coalesced_frames(self):
        connection = self.connect()
        wire = frame(0.2)
        connection.sendall(wire[:12])
        self.assertEqual(self.server.snapshot(), open_hands())
        connection.sendall(wire[12:] + frame(0.8))
        eventually(lambda: self.server.snapshot()['left'] == [0.8] * 5)
        copy = self.server.snapshot()
        copy['left'][0] = 0
        self.assertEqual(self.server.snapshot()['left'][0], 0.8)

    def test_invalid_frame_is_atomic_and_stream_recovers(self):
        connection = self.connect()
        connection.sendall(frame(0.4))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.4)
        connection.sendall(b'{"hands":{"left":[1,1,1,1,1],"right":[false,0,0,0,0]}}\n')
        time.sleep(0.02)
        self.assertEqual(self.server.snapshot()['left'], [0.4] * 5)
        connection.sendall(frame(0.9))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.9)

    def test_pose_is_atomic_copied_and_legacy_frame_resets_rotation(self):
        connection = self.connect()
        wrists = {'left': [-0.2, 0.5, 1.1], 'right': [0.3, -0.7, -1.2]}
        connection.sendall(frame(0.4, wrist_rpy=wrists))
        eventually(lambda: self.server.pose_snapshot()['wrist_rpy'] == wrists)
        pose = self.server.pose_snapshot()
        pose['wrist_rpy']['left'][0] = 8
        self.assertEqual(self.server.pose_snapshot()['wrist_rpy'], wrists)
        connection.sendall(frame(0.9, wrist_rpy={'left': [0, 0, 0], 'right': [True, 0, 0]}))
        time.sleep(0.02)
        self.assertEqual(self.server.pose_snapshot(), {'hands': {'left': [0.4] * 5,
                                                               'right': [0.4] * 5},
                                                      'wrist_rpy': wrists})
        connection.sendall(frame(0.8))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.8)
        self.assertEqual(self.server.pose_snapshot()['wrist_rpy'], neutral_wrists())

    def test_rotation_resets_after_stale_disconnect_and_reconnect(self):
        connection = self.connect()
        wrists = {'left': [0.2, 0.5, 1.1], 'right': [0.3, -0.7, -1.2]}
        connection.sendall(frame(0.4, wrist_rpy=wrists))
        eventually(lambda: self.server.pose_snapshot()['wrist_rpy'] == wrists)
        eventually(lambda: 'stale' in self.events)
        self.assertEqual(self.server.pose_snapshot(), {'hands': open_hands(),
                                                      'wrist_rpy': neutral_wrists()})
        replacement = self.connect()
        replacement.sendall(frame(0.6, wrist_rpy=wrists))
        eventually(lambda: self.server.pose_snapshot()['wrist_rpy'] == wrists)
        replacement.close()
        eventually(lambda: self.server.status == 'disconnected')
        self.assertEqual(self.server.pose_snapshot()['wrist_rpy'], neutral_wrists())

    def test_invalid_rotation_does_not_refresh_watchdog(self):
        connection = self.connect()
        connection.sendall(frame(0.4, wrist_rpy={'left': [0.1] * 3, 'right': [0.2] * 3}))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.4)
        until = time.monotonic() + 0.5
        while time.monotonic() < until and 'stale' not in self.events:
            try:
                connection.sendall(frame(0.9, wrist_rpy={'left': [0] * 3, 'right': ['0'] * 3}))
            except OSError:
                break
            time.sleep(0.015)
        eventually(lambda: 'stale' in self.events)
        self.assertEqual(self.server.pose_snapshot()['wrist_rpy'], neutral_wrists())

    def test_disconnect_opens_hands_and_accepts_reconnection(self):
        connection = self.connect()
        connection.sendall(frame(0.6))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.6)
        connection.close()
        eventually(lambda: self.server.status == 'disconnected')
        self.assertEqual(self.server.snapshot(), open_hands())
        next_connection = self.connect()
        next_connection.sendall(frame(0.3))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.3)

    def test_silent_tracker_times_out_even_with_future_capture_timestamp(self):
        connection = self.connect()
        connection.sendall(frame(0.6, captured_at=99999999999))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.6)
        eventually(lambda: 'stale' in self.events)
        self.assertEqual(self.server.snapshot(), open_hands())
        self.assertEqual(connection.recv(1), b'')
        replacement = self.connect()
        replacement.sendall(frame(0.2))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.2)

    def test_invalid_traffic_does_not_refresh_watchdog(self):
        connection = self.connect()
        connection.sendall(frame(0.6))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.6)
        until = time.monotonic() + 0.5
        while time.monotonic() < until and 'stale' not in self.events:
            try:
                connection.sendall(frame(True))
            except OSError:
                break
            time.sleep(0.015)
        eventually(lambda: 'stale' in self.events)
        self.assertEqual(self.server.snapshot(), open_hands())

    def test_silent_client_without_first_frame_releases_slot(self):
        connection = self.connect()
        eventually(lambda: 'stale' in self.events)
        self.assertEqual(connection.recv(1), b'')
        replacement = self.connect()
        replacement.sendall(frame(0.5))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.5)

    def test_oversized_unterminated_frame_is_disconnected(self):
        connection = self.connect()
        connection.sendall(b'x' * (self.server.max_frame_bytes + 1))
        eventually(lambda: self.server.status == 'disconnected')
        self.assertEqual(connection.recv(1), b'')
        replacement = self.connect()
        replacement.sendall(frame(0.3))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.3)

    def test_oversized_terminated_frame_is_not_accepted(self):
        connection = self.connect()
        connection.sendall(frame(0.2, padding='x' * self.server.max_frame_bytes))
        eventually(lambda: self.server.status == 'disconnected')
        self.assertEqual(self.server.snapshot(), open_hands())

    def test_reset_does_not_kill_receiver(self):
        connection = self.connect()
        connection.sendall(frame(0.6))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.6)
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        connection.close()
        eventually(lambda: self.server.status == 'disconnected')
        replacement = self.connect()
        replacement.sendall(frame(0.1))
        eventually(lambda: self.server.snapshot()['left'][0] == 0.1)

    def test_stop_joins_worker_when_accepting_or_reading(self):
        self.server.stop()
        self.assertFalse(self.server._thread.is_alive())
        second = TrackerServer(port=0, host='127.0.0.1').start()
        self.addCleanup(second.stop)
        connection = socket.create_connection(('127.0.0.1', second.port), timeout=1)
        self.addCleanup(connection.close)
        eventually(lambda: second.status == 'connected')
        second.stop()
        self.assertFalse(second._thread.is_alive())
        self.assertEqual(second.status, 'stopped')
        self.assertEqual(connection.recv(1), b'')
        second.stop()  # idempotent cleanup

    def test_busy_port_failure_is_synchronous(self):
        other = TrackerServer(port=self.server.port, host='127.0.0.1')
        with self.assertRaises(OSError):
            other.start()
        other.stop()


if __name__ == '__main__':
    unittest.main()
