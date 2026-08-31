"""Run on macOS: track one hand with the built-in camera and send curls to ROS."""
import argparse
import json
import math
import socket
import time

import cv2
import mediapipe as mp


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


def connect(host, port):
    while True:
        try:
            sock = socket.create_connection((host, port), timeout=3)
            print(f'Connected to {host}:{port}')
            return sock
        except OSError as error:
            print(f'Waiting for ROS bridge: {error}')
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description='Send webcam hand curls to an RViz hand.')
    parser.add_argument('--host', required=True, help='Ubuntu computer IP, e.g. 192.0.2.10')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--camera', type=int, default=0, help='macOS camera index (default: 0)')
    args = parser.parse_args()
    sock = connect(args.host, args.port)
    camera = cv2.VideoCapture(args.camera, cv2.CAP_AVFOUNDATION)
    if not camera.isOpened():
        raise RuntimeError('Could not open the Mac camera. Grant Terminal camera permission and retry.')
    hands = mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.6,
                                    min_tracking_confidence=0.6)
    draw = mp.solutions.drawing_utils
    failed_reads = 0
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                failed_reads += 1
                if failed_reads >= 50:
                    raise RuntimeError('The Mac camera opened but did not produce frames.')
                time.sleep(0.1)
                continue
            failed_reads = 0
            frame = cv2.flip(frame, 1)
            result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if result.multi_hand_landmarks:
                points = result.multi_hand_landmarks[0].landmark
                curls = [curl(points, 1, 2, 4), curl(points, 5, 6, 8),
                         curl(points, 9, 10, 12), curl(points, 13, 14, 16),
                         curl(points, 17, 18, 20)]
                sock.sendall((json.dumps({'curls': curls}) + '\n').encode())
                draw.draw_landmarks(frame, result.multi_hand_landmarks[0], mp.solutions.hands.HAND_CONNECTIONS)
            cv2.imshow('Hand tracker (press q to quit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        hands.close()
        camera.release()
        cv2.destroyAllWindows()
        sock.close()


if __name__ == '__main__':
    main()
