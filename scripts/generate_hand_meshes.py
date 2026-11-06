#!/usr/bin/env python3
"""Build the hand's small, original visual meshes using only the standard library."""
import math
from pathlib import Path
import struct


DESTINATION = Path(__file__).resolve().parents[1] / 'src/hand_motion_rviz/meshes'


def rounded_outline(vertices, steps=6):
    result = []
    for index, point in enumerate(vertices):
        previous, following = vertices[index - 1], vertices[(index + 1) % len(vertices)]
        start = tuple(.72 * p + .28 * q for p, q in zip(point, previous))
        end = tuple(.72 * p + .28 * q for p, q in zip(point, following))
        for step in range(steps):
            t = step / (steps - 1)
            result.append(tuple((1 - t) ** 2 * a + 2 * t * (1 - t) * p + t ** 2 * b
                                for a, p, b in zip(start, point, end)))
    return result


def extrude(outline, half_depth, bevel=.90):
    rings = [[(x * scale, y * scale, z * half_depth) for x, y in outline]
             for z, scale in [(-1, bevel), (-.62, 1), (.62, 1), (1, bevel)]]
    faces = []
    count = len(outline)
    for lower, upper in zip(rings, rings[1:]):
        for j in range(count):
            k = (j + 1) % count
            faces.extend([(lower[j], lower[k], upper[k]), (lower[j], upper[k], upper[j])])
    for j in range(count):
        k = (j + 1) % count
        faces.append(((0, 0, -half_depth), rings[0][k], rings[0][j]))
        faces.append(((0, 0, half_depth), rings[-1][j], rings[-1][k]))
    return faces


def phalanx(tip=False, samples=32):
    profile = ([(.035, .60), (.10, .88), (.24, 1), (.60, .94), (.81, .81), (.94, .50)]
               if tip else [(.04, .66), (.12, .94), (.27, 1), (.72, .93), (.88, .77), (.96, .43)])
    rings = []
    for x, radius in profile:
        ring = []
        for j in range(samples):
            angle = 2 * math.pi * j / samples
            y, z = math.cos(angle), math.sin(angle)
            ring.append((x, radius * math.copysign(abs(y) ** .62, y),
                         radius * math.copysign(abs(z) ** .62, z)))
        rings.append(ring)
    faces = []
    for first, second in zip(rings, rings[1:]):
        for j in range(samples):
            k = (j + 1) % samples
            faces.extend([(first[j], second[k], second[j]), (first[j], first[k], second[k])])
    for j in range(samples):
        k = (j + 1) % samples
        faces.extend([((0, 0, 0), rings[0][k], rings[0][j]),
                      ((1, 0, 0), rings[-1][j], rings[-1][k])])
    return faces


def write_stl(name, faces):
    destination = DESTINATION / name
    with destination.open('wb') as stream:
        stream.write(('Original Hand Motion RViz visual: ' + name).encode().ljust(80, b'\0'))
        stream.write(struct.pack('<I', len(faces)))
        for a, b, c in faces:
            u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                      u[0] * v[1] - u[1] * v[0])
            length = math.sqrt(sum(value * value for value in normal))
            if length <= 1e-16:
                raise ValueError(f'degenerate triangle in {name}')
            stream.write(struct.pack('<12fH', *(value / length for value in normal), *a, *b, *c, 0))
    print(f'{name}: {len(faces)} triangles, {destination.stat().st_size} bytes')


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    # The thumb-side heel is fuller, while the wrist and little-finger side taper.
    outline = rounded_outline([(-.066, -.025), (-.058, -.036), (-.030, -.044),
                               (.010, -.047), (.050, -.041), (.065, -.029),
                               (.065, .030), (.049, .043), (.006, .050),
                               (-.029, .051), (-.055, .039), (-.066, .023)])
    left = extrude(outline, .013)
    write_stl('palm_left.stl', left)
    write_stl('palm_right.stl', [tuple((x, -y, z) for x, y, z in reversed(face)) for face in left])
    write_stl('phalanx.stl', phalanx())
    write_stl('fingertip.stl', phalanx(tip=True))
    pad = rounded_outline([(-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)], steps=10)
    write_stl('soft_pad.stl', extrude(pad, .5, bevel=.88))


if __name__ == '__main__':
    main()
