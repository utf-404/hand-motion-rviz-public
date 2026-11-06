"""Bounded JSONL tracker transport, independent of ROS and camera libraries."""
import json
import math
import socket
import threading
import time

HANDS = ('left', 'right')
MAX_FRAME_BYTES = 16 * 1024


def positive_seconds(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('timeout must be a finite positive number')
    return value


def open_hands():
    return {hand: [0.0] * 5 for hand in HANDS}


def neutral_wrists():
    return {hand: [0.0] * 3 for hand in HANDS}


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('pose values must be finite numbers')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError('pose values must be finite numbers')
    return float(value)


def parse_pose_frame(line):
    """Validate curls and optional wrist RPY atomically; legacy frames are neutral."""
    def invalid_constant(value):
        raise ValueError(f'non-finite JSON constant: {value}')

    data = json.loads(line, parse_constant=invalid_constant)
    if not isinstance(data, dict) or not isinstance(data.get('hands'), dict):
        raise ValueError('expected an object containing hands')
    parsed = {}
    for hand in HANDS:
        values = data['hands'].get(hand)
        if not isinstance(values, list) or len(values) != 5:
            raise ValueError(f'expected five curls for {hand} hand')
        parsed[hand] = []
        for value in values:
            parsed[hand].append(max(0.0, min(1.0, _finite_number(value))))
    wrists = neutral_wrists()
    if 'wrist_rpy' in data:
        if not isinstance(data['wrist_rpy'], dict):
            raise ValueError('wrist_rpy must be an object')
        for hand in HANDS:
            values = data['wrist_rpy'].get(hand)
            if not isinstance(values, list) or len(values) != 3:
                raise ValueError(f'expected roll, pitch and yaw for {hand} wrist')
            wrists[hand] = [_finite_number(value) for value in values]
    return {'hands': parsed, 'wrist_rpy': wrists}


def parse_frame(line):
    """Compatibility API returning curls while validating the entire frame."""
    return parse_pose_frame(line)['hands']


class TrackerServer:
    """One active tracker, with local monotonic freshness and explicit shutdown.

    Binding is synchronous in start(), so a busy port fails the caller rather
    than silently killing a background thread. Silent/invalid-only clients lose
    their slot after stale_timeout, allowing a new tracker to reconnect.
    """
    def __init__(self, port=18765, host='0.0.0.0', stale_timeout=1.0,
                 on_status=None, max_frame_bytes=MAX_FRAME_BYTES):
        self.host = host
        self.port = port
        self.stale_timeout = positive_seconds(stale_timeout)
        self.max_frame_bytes = max_frame_bytes
        self.on_status = on_status or (lambda status: None)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._server = None
        self._connection = None
        self._thread = None
        self._curls = open_hands()
        self._wrists = neutral_wrists()
        self._last_frame = None
        self._status = 'waiting'

    @property
    def status(self):
        with self._lock:
            return self._status

    def _set_status(self, status, reset=False):
        with self._lock:
            changed = self._status != status
            self._status = status
            if reset:
                self._curls = open_hands()
                self._wrists = neutral_wrists()
                self._last_frame = None
        if changed:
            self.on_status(status)

    def snapshot(self):
        return self.pose_snapshot()['hands']

    def pose_snapshot(self):
        """Return one consistent pose, never mixing wrists from another frame."""
        with self._lock:
            if (self._last_frame is None or
                    time.monotonic() - self._last_frame >= self.stale_timeout):
                return {'hands': open_hands(), 'wrist_rpy': neutral_wrists()}
            return {'hands': {hand: values[:] for hand, values in self._curls.items()},
                    'wrist_rpy': {hand: values[:] for hand, values in self._wrists.items()}}

    def start(self):
        if self._thread is not None:
            raise RuntimeError('tracker server has already been started')
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(1)
            server.settimeout(min(0.1, self.stale_timeout))
        except BaseException:
            server.close()
            raise
        self.port = server.getsockname()[1]
        self._server = server
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()
        return self

    @staticmethod
    def _close_socket(sock):
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    def stop(self):
        self._stop.set()
        with self._lock:
            connection = self._connection
        self._close_socket(connection)
        self._close_socket(self._server)
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join()
        self._set_status('stopped', reset=True)

    def _receive_loop(self):
        while not self._stop.is_set():
            try:
                connection, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                self._connection = connection
            try:
                self._set_status('connected', reset=True)
                self._receive_connection(connection)
            except OSError:
                # Resets and explicit shutdown are normal transport events.
                pass
            finally:
                self._close_socket(connection)
                with self._lock:
                    self._connection = None
                if not self._stop.is_set():
                    self._set_status('disconnected', reset=True)

    def _receive_connection(self, connection):
        connection.settimeout(min(0.1, self.stale_timeout))
        last_valid = time.monotonic()
        buffer = b''
        while not self._stop.is_set():
            if time.monotonic() - last_valid >= self.stale_timeout:
                self._set_status('stale', reset=True)
                return
            try:
                chunk = connection.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                return
            buffer += chunk
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                if len(line) > self.max_frame_bytes:
                    return
                try:
                    pose = parse_pose_frame(line)
                except (ValueError, UnicodeError, RecursionError):
                    continue
                last_valid = time.monotonic()
                with self._lock:
                    self._curls = pose['hands']
                    self._wrists = pose['wrist_rpy']
                    self._last_frame = last_valid
            if len(buffer) > self.max_frame_bytes:
                return
