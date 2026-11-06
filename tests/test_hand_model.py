"""Model/view geometry regressions; no camera or RViz window is opened."""
import math
from pathlib import Path
import re
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'src/hand_motion_rviz/urdf/hand.urdf.xacro'
CONFIG = ROOT / 'src/hand_motion_rviz/config/hand.rviz'


class HandModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which('xacro'):
            command = ['xacro', str(MODEL)]
        elif Path('/opt/ros/humble/bin/xacro').exists():
            command = ['bash', '-c', 'source /opt/ros/humble/setup.bash && xacro "$1"',
                       '_', str(MODEL)]
        else:
            raise unittest.SkipTest('xacro is needed to validate the expanded model')
        expanded = subprocess.run(command, capture_output=True, text=True, check=True)
        cls.robot = ET.fromstring(expanded.stdout)
        cls.joints = {joint.attrib['name']: joint for joint in cls.robot.findall('joint')}

    def test_wrist_chain_adds_six_dynamic_joints_and_preserves_fingers(self):
        movable = [joint for joint in self.joints.values() if joint.attrib['type'] != 'fixed']
        self.assertEqual(len(movable), 36)
        for side in ('left', 'right'):
            for axis_name, parent, child, axis in (
                    ('yaw', 'mount', 'wrist_yaw', '0 0 1'),
                    ('pitch', 'wrist_yaw', 'wrist_pitch', '0 1 0'),
                    ('roll', 'wrist_pitch', 'palm', '1 0 0')):
                joint = self.joints[f'{side}_wrist_{axis_name}_joint']
                self.assertEqual(joint.attrib['type'], 'continuous')
                self.assertEqual(joint.find('parent').attrib['link'], f'{side}_{parent}')
                self.assertEqual(joint.find('child').attrib['link'], f'{side}_{child}')
                self.assertEqual(joint.find('axis').attrib['xyz'], axis)
                self.assertEqual(joint.find('origin').attrib, {'xyz': '0 0 0', 'rpy': '0 0 0'})
            finger_joints = [joint for name, joint in self.joints.items()
                             if name.startswith(side + '_') and joint.attrib['type'] == 'revolute']
            self.assertEqual(len(finger_joints), 15)

    def test_swapped_mounts_keep_identity_neutral_orientation(self):
        for side, offset in [('left', -0.13), ('right', 0.13)]:
            base = self.joints[f'{side}_base_joint']
            self.assertEqual(base.find('parent').attrib['link'], 'hands_base')
            self.assertEqual(base.find('child').attrib['link'], f'{side}_mount')
            xyz = [float(value) for value in base.find('origin').attrib['xyz'].split()]
            self.assertEqual(xyz, [0, offset, 0])
            self.assertEqual(base.find('origin').attrib['rpy'], '0 0 0')

    def test_palmar_pad_is_on_finger_flexion_side(self):
        for side in ('left', 'right'):
            palm = self.robot.find(f"link[@name='{side}_palm']")
            pad = palm.find(f"visual[@name='{side}_palm_pad']")
            z = float(pad.find('origin').attrib['xyz'].split()[2])
            thickness = float(pad.find('geometry/box').attrib['size'].split()[2])
            self.assertLess(z, 0)
            self.assertLess(z - thickness / 2, -0.013)  # in front of the palm body
            finger = self.joints[f'{side}_middle_mcp_joint']
            self.assertEqual(finger.find('axis').attrib['xyz'], '0 1 0')
            # A +Y joint sends a +X finger toward -Z at positive curl.
            self.assertLess(-math.sin(0.5), 0)

    def test_default_view_faces_palm_with_left_hand_on_screen_left(self):
        config = CONFIG.read_text()
        pitch = float(re.search(r'^\s+Pitch: (.+)$', config, re.M).group(1))
        yaw = float(re.search(r'^\s+Yaw: (.+)$', config, re.M).group(1))
        self.assertAlmostEqual(yaw, 0)
        self.assertLess(pitch, -1.2)
        self.assertGreater(pitch, -math.pi / 2)
        # Orbit camera eye relative to the focal point is below the XY palm.
        eye = (math.cos(pitch) * math.cos(yaw),
               math.cos(pitch) * math.sin(yaw), math.sin(pitch))
        self.assertLess(eye[2], 0)
        # With global +Z up, camera-right is (-sin(yaw), cos(yaw), 0).
        right_axis = (-math.sin(yaw), math.cos(yaw), 0)
        for side, screen_sign in [('left', -1), ('right', 1)]:
            origin = self.joints[f'{side}_base_joint'].find('origin')
            xyz = [float(value) for value in origin.attrib['xyz'].split()]
            screen_x = sum(value * axis for value, axis in zip(xyz, right_axis))
            self.assertGreater(screen_x * screen_sign, 0)


if __name__ == '__main__':
    unittest.main()
