"""Track both hands with a local webcam on Ubuntu or macOS and send curls to ROS."""
import argparse
import math
import sys
import time

from tracker_connection import TrackerConnection, positive_seconds
from hand_orientation import wrist_rpy


def camera_source(value):
    """Accept a nonnegative device index or Linux /dev/video device path."""
    if value.isdecimal():
        return int(value)
    if value.startswith('/dev/video') and value[len('/dev/video'):].isdecimal():
        return value
    raise argparse.ArgumentTypeError('use a camera index (0, 1, ...) or /dev/videoN')


def camera_backend(cv2, name='auto', platform=None):
    platform = sys.platform if platform is None else platform
    if name == 'auto':
        name = 'v4l2' if platform.startswith('linux') else ('avfoundation' if platform == 'darwin' else 'any')
    return {'v4l2': cv2.CAP_V4L2, 'avfoundation': cv2.CAP_AVFOUNDATION,
            'any': cv2.CAP_ANY}[name]


def camera_error(source):
    if sys.platform.startswith('linux'):
        return (f'Could not open camera {source}. Check /dev/video*, camera permissions, '
                'and whether another app is using it. Try --camera 1 or --backend any.')
    return f'Could not open camera {source}. Check camera permissions and try --camera 1.'


def angle(a, b, c):
    """Angle ABC in degrees, using MediaPipe's normalized landmark coordinates."""
    ab = (a.x - b.x, a.y - b.y, a.z - b.z)
    cb = (c.x - b.x, c.y - b.y, c.z - b.z)
    dot = sum(left * right for left, right in zip(ab, cb))
    magnitude = math.sqrt(sum(value * value for value in ab) * sum(value * value for value in cb))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / max(magnitude, 1e-8)))))


def curl(landmarks, first, middle, tip):
    # Straight is close to 180 degrees; a bent finger produces a smaller angle.
    return max(0.0, min(1.0, (180.0 - angle(landmarks[first], landmarks[middle], landmarks[tip])) / 105.0))


def main():
    parser = argparse.ArgumentParser(description='Send webcam hand curls to two RViz hands.')
    parser.add_argument('--host', default='127.0.0.1', help='ROS bridge IPv4 address (default: local computer)')
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--camera', type=camera_source, default=0,
                        help='Camera index or /dev/videoN (default: 0)')
    parser.add_argument('--backend', choices=('auto', 'v4l2', 'avfoundation', 'any'), default='auto',
                        help='auto selects V4L2 on Linux and AVFoundation on macOS')
    parser.add_argument('--retry-interval', type=positive_seconds, default=2.0,
                        help='Seconds between reconnect attempts (default: 2)')
    parser.add_argument('--network-timeout', type=positive_seconds, default=0.2,
                        help='Timeout per connect/send in seconds (default: 0.2)')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    import cv2
    import mediapipe as mp

    connection = TrackerConnection(args.host, args.port, args.retry_interval, args.network_timeout)
    camera = hands = None
    failed_reads = 0
    frame_id = 0
    try:
        camera = cv2.VideoCapture(args.camera, camera_backend(cv2, args.backend))
        if not camera.isOpened():
            raise RuntimeError(camera_error(args.camera))
        hands = mp.solutions.hands.Hands(max_num_hands=2, min_detection_confidence=0.6,
                                        min_tracking_confidence=0.6)
        draw = mp.solutions.drawing_utils
        while True:
            ok, frame = camera.read()
            if not ok:
                failed_reads += 1
                if failed_reads >= 50:
                    raise RuntimeError('The camera opened but did not produce frames. Try another camera index.')
                time.sleep(0.1)
                continue
            failed_reads = 0
            captured_at = time.time()
            frame = cv2.flip(frame, 1)
            result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            tracked_hands = {'left': [0.0] * 5, 'right': [0.0] * 5}
            tracked_wrists = {'left': [0.0] * 3, 'right': [0.0] * 3}
            if result.multi_hand_landmarks and result.multi_handedness:
                world_hands = getattr(result, 'multi_hand_world_landmarks', None) or []
                for hand_index, (hand_landmarks, handedness) in enumerate(zip(
                        result.multi_hand_landmarks, result.multi_handedness)):
                    side = handedness.classification[0].label.lower()
                    if side not in tracked_hands:
                        continue
                    points = hand_landmarks.landmark
                    if hand_index < len(world_hands):
                        rotation = wrist_rpy(world_hands[hand_index].landmark, side)
                    else:
                        rotation = wrist_rpy(points, side, (frame.shape[1], frame.shape[0]))
                    if rotation is not None:
                        tracked_wrists[side] = rotation
                    tracked_hands[side] = [
                        curl(points, 1, 2, 4), curl(points, 5, 6, 8),
                        curl(points, 9, 10, 12), curl(points, 13, 14, 16),
                        curl(points, 17, 18, 20),
                    ]
                    draw.draw_landmarks(
                        frame, hand_landmarks, mp.solutions.hands.HAND_CONNECTIONS)
                    wrist = points[0]
                    cv2.putText(
                        frame, side.capitalize(),
                        (int(wrist.x * frame.shape[1]), int(wrist.y * frame.shape[0])),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            # Send every frame so a hand that leaves the image returns to an open pose.
            sent = connection.send({'hands': tracked_hands, 'wrist_rpy': tracked_wrists,
                                    'frame_id': frame_id,
                                    'captured_at': captured_at})
            frame_id += 1
            status = 'Connected' if sent else 'Reconnecting to ROS bridge'
            cv2.putText(frame, status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        (0, 255, 0) if sent else (0, 165, 255), 2)
            cv2.imshow('Two-hand tracker (press q to quit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        if hands is not None:
            hands.close()
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()
        connection.close()


if __name__ == '__main__':
    main()
