import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/hand_motion_rviz/tracker'))
from hand_orientation import wrist_rpy


def matrix(rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return ((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
            (-sp, cp * sr, cp * cr))


def landmarks(side, rpy, scale=1, normalized_size=None):
    sign = 1 if side == 'left' else -1
    pose = matrix(rpy)
    points = [SimpleNamespace(x=0, y=0, z=0) for _ in range(21)]
    for i, point in {0: (0, 0, 0), 9: (.08, 0, 0),
                     5: (.06, sign * .03, 0), 17: (.06, -sign * .03, 0)}.items():
        scene = [sum(row[j] * point[j] for j in range(3)) * scale for row in pose]
        camera = (scene[1] + .2, -scene[0] + .3, scene[2] + .6)
        if normalized_size:
            w, h = normalized_size
            camera = (camera[0] / w, camera[1] / h, camera[2] / w)
        points[i] = SimpleNamespace(x=camera[0], y=camera[1], z=camera[2])
    return points


class HandOrientationTests(unittest.TestCase):
    def assertOrientation(self, actual, expected):
        self.assertIsNotNone(actual)
        for arow, erow in zip(matrix(actual), matrix(expected)):
            for a, e in zip(arow, erow):
                self.assertAlmostEqual(a, e, places=6)

    def test_both_neutral_palms_face_viewer(self):
        for side in ('left', 'right'):
            with self.subTest(side=side):
                self.assertOrientation(wrist_rpy(landmarks(side, (0, 0, 0)), side), (0, 0, 0))

    def test_three_axis_rotations_preserve_handedness(self):
        for side in ('left', 'right'):
            for expected in [(1.1, 0, 0), (0, -.7, 0), (0, 0, 2.8),
                             (-.8, .9, -1.4), (.2, -1.3, .8), (2.7, .4, -2.6)]:
                with self.subTest(side=side, rotation=expected):
                    self.assertOrientation(wrist_rpy(landmarks(side, expected), side), expected)

    def test_gimbal_lock_has_equivalent_finite_orientation(self):
        for pitch in (-math.pi / 2, math.pi / 2):
            expected = (.8, pitch, -.6)
            self.assertOrientation(wrist_rpy(landmarks('left', expected), 'left'), expected)

    def test_translation_scale_and_image_aspect_do_not_change_orientation(self):
        expected = (.6, -.4, 1.2)
        self.assertOrientation(wrist_rpy(landmarks('right', expected, scale=3), 'right'), expected)
        for size in [(1920, 1080), (480, 640)]:
            self.assertOrientation(wrist_rpy(landmarks('left', expected, normalized_size=size),
                                            'left', size), expected)

    def test_degenerate_and_nonfinite_landmarks_are_not_sent_as_angles(self):
        empty = [SimpleNamespace(x=0, y=0, z=0) for _ in range(21)]
        self.assertIsNone(wrist_rpy(empty, 'left'))
        points = landmarks('left', (0, 0, 0))
        points[5].z = float('nan')
        self.assertIsNone(wrist_rpy(points, 'left'))
        self.assertIsNone(wrist_rpy([], 'right'))


if __name__ == '__main__':
    unittest.main()
