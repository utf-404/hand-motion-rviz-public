"""Estimate a right-handed palm frame from stable wrist/MCP landmarks.

Model axes: +X towards fingers, +Y towards the left hand's thumb, -Z palm.
Mirrored camera axes map right -> +Y, down -> -X, depth -> +Z.
Angles use Rz(yaw) * Ry(pitch) * Rx(roll), matching the URDF wrist chain.
"""
import math


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(vector):
    magnitude = math.sqrt(_dot(vector, vector))
    if not math.isfinite(magnitude) or magnitude < 1e-8:
        raise ValueError('degenerate palm landmarks')
    return tuple(value / magnitude for value in vector)


def wrist_rpy(landmarks, side, image_size=None):
    """Return [roll, pitch, yaw] radians, or None for an unusable palm.

    Prefer MediaPipe world landmarks, whose axes share metric scale. If using
    normalized image landmarks instead, pass (width, height) to correct the
    y scale: MediaPipe normalized z uses approximately the same scale as x.
    Translation and uniform hand size do not affect the estimated orientation.
    """
    if side not in ('left', 'right'):
        raise ValueError('side must be left or right')
    y_scale = 1.0
    if image_size is not None:
        width, height = image_size
        if width <= 0 or height <= 0:
            raise ValueError('image dimensions must be positive')
        y_scale = height / width

    def point(index):
        p = landmarks[index]
        values = (-float(p.y) * y_scale, float(p.x), float(p.z))
        if not all(math.isfinite(value) for value in values):
            raise ValueError('nonfinite palm landmarks')
        return values

    try:
        wrist, index, middle, little = (point(i) for i in (0, 5, 9, 17))
        x_axis = _unit(tuple(m - w for m, w in zip(middle, wrist)))
        sign = 1 if side == 'left' else -1
        lateral = tuple(sign * (i - p) for i, p in zip(index, little))
        projection = _dot(lateral, x_axis)
        y_axis = _unit(tuple(y - projection * x for x, y in zip(x_axis, lateral)))
        z_axis = _unit(_cross(x_axis, y_axis))
        y_axis = _cross(z_axis, x_axis)
        # Columns of the rotation matrix are the local model axes in the scene.
        cosine_pitch = math.hypot(x_axis[0], x_axis[1])
        pitch = math.atan2(-x_axis[2], cosine_pitch)
        if cosine_pitch > 1e-7:
            roll = math.atan2(y_axis[2], z_axis[2])
            yaw = math.atan2(x_axis[1], x_axis[0])
        else:
            # At gimbal lock roll/yaw are not individually identifiable. This
            # equivalent decomposition keeps the rendered orientation intact.
            roll = math.atan2(-z_axis[1], y_axis[1])
            yaw = 0.0
        return [roll, pitch, yaw]
    except (ValueError, TypeError, IndexError, AttributeError, OverflowError):
        return None
