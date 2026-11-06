import argparse
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/hand_motion_rviz/tracker'))
import hand_tracker


class CameraTrackerTests(unittest.TestCase):
    def test_backend_uses_native_os_and_allows_override(self):
        cv2 = SimpleNamespace(CAP_V4L2=200, CAP_AVFOUNDATION=1200, CAP_ANY=0)
        self.assertEqual(hand_tracker.camera_backend(cv2, platform='linux'), 200)
        self.assertEqual(hand_tracker.camera_backend(cv2, platform='darwin'), 1200)
        self.assertEqual(hand_tracker.camera_backend(cv2, platform='win32'), 0)
        self.assertEqual(hand_tracker.camera_backend(cv2, 'any', platform='linux'), 0)

    def test_camera_source_accepts_device_paths_and_rejects_invalid_input(self):
        self.assertEqual(hand_tracker.camera_source('1'), 1)
        self.assertEqual(hand_tracker.camera_source('/dev/video0'), '/dev/video0')
        for value in ['-1', 'webcam', '/dev/video', '/dev/video0/../other']:
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                hand_tracker.camera_source(value)

    def fake_dependencies(self):
        cv2 = Mock(CAP_V4L2=200, CAP_AVFOUNDATION=1200, CAP_ANY=0)
        cv2.VideoCapture.return_value.isOpened.return_value = True
        cv2.VideoCapture.return_value.read.return_value = (True, Mock())
        cv2.waitKey.return_value = ord('q')
        processor = Mock()
        processor.process.return_value = SimpleNamespace(multi_hand_landmarks=None,
                                                       multi_handedness=None)
        mp = SimpleNamespace(solutions=SimpleNamespace(
            hands=SimpleNamespace(Hands=Mock(return_value=processor), HAND_CONNECTIONS=[]), drawing_utils=Mock()))
        return cv2, mp, processor

    def test_local_linux_frame_send_and_quit_releases_resources(self):
        cv2, mp, processor = self.fake_dependencies()
        with patch.dict(sys.modules, {'cv2': cv2, 'mediapipe': mp}), \
                patch.object(sys, 'platform', 'linux'), \
                patch.object(sys, 'argv', ['hand_tracker.py', '--camera', '/dev/video0']), \
                patch.object(hand_tracker, 'TrackerConnection') as connection:
            hand_tracker.main()
            connection.assert_called_once_with('127.0.0.1', 18765, 2.0, 0.2)
            cv2.VideoCapture.assert_called_once_with('/dev/video0', 200)
            sent = connection.return_value.send.call_args.args[0]
            self.assertEqual(sent['hands'], {'left': [0] * 5, 'right': [0] * 5})
            self.assertEqual(sent['wrist_rpy'], {'left': [0] * 3, 'right': [0] * 3})
            self.assertEqual(sent['frame_id'], 0)
            self.assertGreater(sent['captured_at'], 0)
            connection.return_value.close.assert_called_once()
        processor.close.assert_called_once()
        cv2.VideoCapture.return_value.release.assert_called_once()
        cv2.destroyAllWindows.assert_called_once()

    def test_camera_open_failure_is_actionable_and_closes_transport(self):
        cv2, mp, _ = self.fake_dependencies()
        cv2.VideoCapture.return_value.isOpened.return_value = False
        with patch.dict(sys.modules, {'cv2': cv2, 'mediapipe': mp}), \
                patch.object(sys, 'platform', 'linux'), \
                patch.object(sys, 'argv', ['hand_tracker.py']), \
                patch.object(hand_tracker, 'TrackerConnection') as connection:
            with self.assertRaisesRegex(RuntimeError, '/dev/video'):
                hand_tracker.main()
            cv2.VideoCapture.return_value.release.assert_called_once()
            connection.return_value.close.assert_called_once()
            mp.solutions.hands.Hands.assert_not_called()

    def test_detected_world_rotation_is_sent_for_the_same_hand(self):
        from test_hand_orientation import landmarks
        cv2, mp, processor = self.fake_dependencies()
        cv2.flip.return_value = SimpleNamespace(shape=(480, 640, 3))
        points = landmarks('right', (0.2, -0.3, 0.8))
        processor.process.return_value = SimpleNamespace(
            multi_hand_landmarks=[SimpleNamespace(landmark=points)],
            multi_hand_world_landmarks=[SimpleNamespace(landmark=points)],
            multi_handedness=[SimpleNamespace(classification=[SimpleNamespace(label='Right')])])
        with patch.dict(sys.modules, {'cv2': cv2, 'mediapipe': mp}), \
                patch.object(sys, 'argv', ['hand_tracker.py']), \
                patch.object(hand_tracker, 'TrackerConnection') as connection:
            hand_tracker.main()
            rotations = connection.return_value.send.call_args.args[0]['wrist_rpy']
        self.assertEqual(rotations['left'], [0, 0, 0])
        for actual, expected in zip(rotations['right'], (0.2, -0.3, 0.8)):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_tracker_initialization_failure_releases_camera(self):
        cv2, mp, _ = self.fake_dependencies()
        mp.solutions.hands.Hands.side_effect = RuntimeError('model unavailable')
        with patch.dict(sys.modules, {'cv2': cv2, 'mediapipe': mp}), \
                patch.object(sys, 'argv', ['hand_tracker.py']), \
                patch.object(hand_tracker, 'TrackerConnection') as connection:
            with self.assertRaisesRegex(RuntimeError, 'model unavailable'):
                hand_tracker.main()
            cv2.VideoCapture.return_value.release.assert_called_once()
            connection.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
