import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/hand_motion_rviz/tracker'))
from tracker_connection import TrackerConnection, positive_seconds


class TrackerConnectionTests(unittest.TestCase):
    def test_refused_connection_is_throttled_and_recovery_sends_only_new_frame(self):
        first = {'hands': {'left': [0.0] * 5, 'right': [0.0] * 5}, 'frame_id': 1}
        latest = dict(first, frame_id=3)
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0))
            server.listen()
            server.settimeout(1)
            connection = TrackerConnection(*server.getsockname())
            self.addCleanup(connection.close)
            with patch('tracker_connection.socket.socket', side_effect=ConnectionRefusedError), \
                    patch('tracker_connection.time.monotonic', return_value=10):
                self.assertFalse(connection.send(first))
            with patch('tracker_connection.socket.socket') as attempt, \
                    patch('tracker_connection.time.monotonic', return_value=11):
                self.assertFalse(connection.send(dict(first, frame_id=2)))
                attempt.assert_not_called()
            with patch('tracker_connection.time.monotonic', return_value=12):
                self.assertTrue(connection.send(latest))
            peer, _ = server.accept()
            with peer, peer.makefile('rb') as stream:
                peer.settimeout(1)
                self.assertEqual(json.loads(stream.readline()), latest)
                connection.close()
                self.assertEqual(stream.read(), b'')

    def test_broken_send_closes_socket_and_reconnects(self):
        broken, recovered = Mock(), Mock()
        broken.sendall.side_effect = BrokenPipeError('bridge stopped')
        with patch('tracker_connection.socket.socket', side_effect=[broken, recovered]), \
                patch('tracker_connection.time.monotonic', side_effect=[10, 10, 11, 12]):
            connection = TrackerConnection('localhost', 18765)
            self.assertFalse(connection.send({'frame_id': 1}))
            broken.close.assert_called_once()
            self.assertFalse(connection.connected)
            self.assertFalse(connection.send({'frame_id': 2}))
            self.assertTrue(connection.send({'frame_id': 3}))
            self.assertTrue(connection.connected)
            self.assertEqual(json.loads(recovered.sendall.call_args.args[0]), {'frame_id': 3})
        connection.close()
        recovered.close.assert_called_once()

    def test_close_prevents_reconnect_and_nonfinite_frames_are_rejected(self):
        connection = TrackerConnection('localhost', 18765)
        connection.close()
        with patch('tracker_connection.socket.socket') as attempt:
            self.assertFalse(connection.send({'frame_id': 1}))
            attempt.assert_not_called()
        with self.assertRaises(ValueError):
            connection.send({'hands': [float('nan')]})

    def test_timeout_options_reject_nonfinite_and_nonpositive_values(self):
        for value in ['nan', 'inf', '-inf', '0', '-1']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                positive_seconds(value)
        self.assertEqual(positive_seconds('0.2'), 0.2)

    def test_dns_is_resolved_once_before_frame_sends(self):
        endpoint = ('127.0.0.1', 18765)
        with patch('tracker_connection.socket.getaddrinfo', return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, '', endpoint)]) as resolve:
            connection = TrackerConnection('ubuntu-host', 18765)
            self.addCleanup(connection.close)
            resolve.assert_called_once()
        with patch('tracker_connection.socket.getaddrinfo', side_effect=AssertionError('DNS during preview')), \
                patch('tracker_connection.socket.socket') as create, \
                patch('tracker_connection.time.monotonic', return_value=10):
            self.assertTrue(connection.send({'frame_id': 1}))
            create.return_value.connect.assert_called_once_with(endpoint)
            create.return_value.settimeout.assert_called_once_with(0.2)


if __name__ == '__main__':
    unittest.main()
