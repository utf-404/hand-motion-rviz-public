import argparse
import math
import unittest

from isaac_hand.run import ordered_targets, positive_duration


class IsaacHandStreamTests(unittest.TestCase):
    def test_headless_duration_must_be_positive_and_finite(self):
        self.assertEqual(positive_duration("2.5"), 2.5)
        for value in ("0", "-1", "nan", "inf"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                positive_duration(value)

    def test_position_targets_follow_names_not_publisher_order(self):
        dofs = ["left_index_mcp_joint", "right_wrist_yaw_joint"]
        self.assertEqual(ordered_targets(dofs[::-1], [-0.3, 0.5], dofs), [0.5, -0.3])

    def test_rejects_partial_duplicate_unknown_and_nonfinite_pose(self):
        dofs = ["left_joint", "right_joint"]
        for names, angles in [
            (dofs[:1], [0.2]),
            (dofs, [0.2]),
            (["left_joint", "left_joint"], [0.2, 0.3]),
            (["left_joint", "unrelated_joint"], [0.2, 0.3]),
            (dofs, [math.nan, 0.3]),
            (dofs, [math.inf, 0.3]),
        ]:
            with self.subTest(names=names, angles=angles):
                self.assertIsNone(ordered_targets(names, angles, dofs))
