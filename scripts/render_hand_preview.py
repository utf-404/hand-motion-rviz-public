#!/usr/bin/env python3
"""Render the actual expanded URDF geometry without opening RViz or a camera."""
import argparse
from pathlib import Path
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET

try:
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError as error:
    raise SystemExit('Use .venv/bin/python; this preview needs NumPy and Matplotlib.') from error


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'src/hand_motion_rviz'


def vector(text, default):
    return np.array([float(v) for v in text.split()] if text else default)


def rotation(axis, angle):
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) * np.cos(angle) + (1 - np.cos(angle)) * np.outer(axis, axis) + np.sin(angle) * cross


def origin(element):
    transform = np.eye(4)
    if element is not None:
        transform[:3, 3] = vector(element.get('xyz'), (0, 0, 0))
        r, p, y = vector(element.get('rpy'), (0, 0, 0))
        transform[:3, :3] = rotation(np.array([0., 0, 1]), y) @ rotation(np.array([0., 1, 0]), p) @ rotation(np.array([1., 0, 0]), r)
    return transform


def triangles(geometry):
    mesh = geometry.find('mesh')
    if mesh is not None:
        uri = mesh.get('filename')
        prefix = 'package://hand_motion_rviz/'
        if not uri.startswith(prefix):
            raise ValueError(f'Unsupported mesh URI: {uri}')
        path = PACKAGE / uri[len(prefix):]
        data = path.read_bytes()
        count, = struct.unpack_from('<I', data, 80)
        if len(data) != 84 + 50 * count:
            raise ValueError(f'Expected binary STL: {path}')
        points = np.array([struct.unpack_from('<9f', data, 84 + i * 50 + 12)
                           for i in range(count)]).reshape(-1, 3, 3)
        return points * vector(mesh.get('scale'), (1, 1, 1))
    box = geometry.find('box')
    if box is not None:
        x, y, z = vector(box.get('size'), (1, 1, 1)) / 2
        vertices = np.array([[-x, -y, -z], [x, -y, -z], [x, y, -z], [-x, y, -z],
                             [-x, -y, z], [x, -y, z], [x, y, z], [-x, y, z]])
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        return np.array([[vertices[a], vertices[b], vertices[c]]
                         for a, b, c, d in faces] + [[vertices[a], vertices[c], vertices[d]]
                                                    for a, b, c, d in faces])
    cylinder, sphere = geometry.find('cylinder'), geometry.find('sphere')
    radius = float((cylinder if cylinder is not None else sphere).get('radius'))
    theta = np.linspace(0, 2 * np.pi, 25)
    if cylinder is not None:
        half = float(cylinder.get('length')) / 2
        rings = [np.array([[radius * np.cos(t), radius * np.sin(t), z] for t in theta])
                 for z in (-half, half)]
        faces = []
        for i in range(24):
            a, b, c, d = rings[0][i], rings[0][i + 1], rings[1][i + 1], rings[1][i]
            faces.extend([(a, b, c), (a, c, d), ((0, 0, -half), b, a), ((0, 0, half), d, c)])
        return np.array(faces)
    latitude = np.linspace(-np.pi / 2, np.pi / 2, 13)
    grid = np.array([[[radius * np.cos(p) * np.cos(t), radius * np.cos(p) * np.sin(t), radius * np.sin(p)]
                      for t in theta] for p in latitude])
    return np.array([face for j in range(12) for i in range(24)
                     for face in ((grid[j, i], grid[j, i + 1], grid[j + 1, i + 1]),
                                  (grid[j, i], grid[j + 1, i + 1], grid[j + 1, i]))])


def scene(robot, curl):
    transforms = {'hands_base': np.eye(4)}
    pending = list(robot.findall('joint'))
    while pending:
        ready = [joint for joint in pending if joint.find('parent').get('link') in transforms]
        if not ready:
            raise ValueError('URDF has an unconnected or cyclic joint tree')
        for joint in ready:
            motion = np.eye(4)
            if joint.get('type') == 'revolute':
                angle = curl * float(joint.find('limit').get('upper'))
                motion[:3, :3] = rotation(vector(joint.find('axis').get('xyz'), (1, 0, 0)), angle)
            transforms[joint.find('child').get('link')] = transforms[joint.find('parent').get('link')] @ origin(joint.find('origin')) @ motion
            pending.remove(joint)
    materials = {item.get('name'): vector(item.find('color').get('rgba'), (0.7, 0.7, 0.7, 1))
                 for item in robot.findall('material')}
    visuals = []
    for link in robot.findall('link'):
        for visual in link.findall('visual'):
            faces = triangles(visual.find('geometry'))
            transform = transforms[link.get('name')] @ origin(visual.find('origin'))
            faces = faces @ transform[:3, :3].T + transform[:3, 3]
            material = visual.find('material')
            color = materials.get(material.get('name'), np.array([0.7, 0.7, 0.7, 1])) if material is not None else np.array([0.7, 0.7, 0.7, 1])
            if material is not None and material.find('color') is not None:
                color = vector(material.find('color').get('rgba'), (0.7, 0.7, 0.7, 1))
            visuals.append((faces[:, :, [1, 0, 2]] * [1, 1, -1], color))
    return visuals


def render(visuals, elevation, azimuth):
    """Orthographic triangle depth buffer, so overlapping shells occlude correctly."""
    width, height = 816, 600
    image = np.full((height, width, 3), [242, 244, 246], dtype=np.uint8)
    depth = np.full((height, width), -np.inf)
    e, a = np.radians([elevation, azimuth])
    eye = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    right = np.array([-np.sin(a), np.cos(a), 0])
    up = np.cross(eye, right)
    camera = np.array([right, up, eye]).T
    light = eye + np.array([-.3, -.2, .5]); light /= np.linalg.norm(light)
    for faces, color in visuals:
        # scene() reflects Z while swapping X/Y, a proper rotation overall.
        normals = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
        normals /= np.maximum(np.linalg.norm(normals, axis=1), 1e-12)[:, None]
        shades = .68 + .32 * np.maximum(0, normals @ light)
        projected = (faces - [0, .035, 0]) @ camera
        projected[:, :, 0] = (projected[:, :, 0] / .49 + .5) * width
        projected[:, :, 1] = (.5 - projected[:, :, 1] / .36) * height
        for points, shade in zip(projected, shades):
            x0, y0 = np.maximum(np.floor(points[:, :2].min(axis=0)).astype(int), [0, 0])
            x1, y1 = np.minimum(np.ceil(points[:, :2].max(axis=0)).astype(int), [width - 1, height - 1])
            if x1 < x0 or y1 < y0:
                continue
            x, y = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = points
            divisor = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(divisor) < 1e-10:
                continue
            u = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / divisor
            v = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / divisor
            w = 1 - u - v
            z = u * az + v * bz + w * cz
            visible = (u >= -1e-8) & (v >= -1e-8) & (w >= -1e-8) & (z > depth[y0:y1 + 1, x0:x1 + 1])
            depth[y0:y1 + 1, x0:x1 + 1][visible] = z[visible]
            image[y0:y1 + 1, x0:x1 + 1][visible] = np.clip(color[:3] * shade * 255, 0, 255).astype(np.uint8)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/hand-model-preview.png')
    args = parser.parse_args()
    model = PACKAGE / 'urdf/hand.urdf.xacro'
    command = ['xacro', str(model)] if shutil.which('xacro') else [
        '/bin/bash', '-c', 'source /opt/ros/humble/setup.bash && xacro "$1"', '_', str(model)]
    robot = ET.fromstring(subprocess.check_output(command, text=True))
    fig = plt.figure(figsize=(17, 8), facecolor='#f2f4f6')
    fig.suptitle('URDF model preview', x=.055, y=.95, ha='left', fontsize=25, fontweight='bold', color='#1c2935')
    fig.text(.055, .90, 'LOCAL GEOMETRY  /  PALM, ARTICULATION & DORSAL DETAILS', fontsize=10, color='#64727d')
    views = [('01  Palm / open', 0, 82, -90), ('02  Palm / flexed', .55, 38, -60),
             ('03  Dorsal / open', 0, -50, -65)]
    for index, (title, curl, elev, azim) in enumerate(views, 1):
        ax = fig.add_subplot(1, 3, index, facecolor='#f2f4f6')
        ax.imshow(render(scene(robot, curl), elev, azim))
        ax.set_axis_off()
        ax.set_title(title, fontsize=13, color='#263746', pad=18)
    fig.text(.055, .075, 'Expanded Xacro + forward kinematics  ·  Native mesh materials  ·  No camera input', fontsize=10, color='#64727d')
    fig.text(.055, .045, 'Offline geometry render — not an RViz screenshot', fontsize=9, color='#89959e')
    fig.subplots_adjust(left=.015, right=.985, top=.83, bottom=.13, wspace=-.07)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(args.output)


if __name__ == '__main__':
    main()
