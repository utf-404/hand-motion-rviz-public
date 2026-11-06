"""Bounded TCP sends with reconnects, without retaining old camera frames."""
import json
import math
import socket
import time


def positive_seconds(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('must be a positive finite number of seconds')
    return value


class TrackerConnection:
    def __init__(self, host, port, retry_interval=2.0, timeout=0.2):
        self.address = (host, port)
        self.retry_interval = positive_seconds(retry_interval)
        self.timeout = positive_seconds(timeout)
        # Resolve before opening the camera, never during frame processing.
        # The ROS receiver uses IPv4. A hostname change requires a tracker restart.
        self._endpoint = socket.getaddrinfo(host, port, socket.AF_INET,
                                            socket.SOCK_STREAM)[0][4]
        self._socket = None
        self._next_attempt = 0.0
        self._closed = False

    @property
    def connected(self):
        return self._socket is not None

    def send(self, frame):
        """Try the current frame once; return False during connection outages.

        Connect and send each have a short timeout so camera preview and quitting
        remain available. No queue is kept: recovery sends the newest frame.
        """
        payload = (json.dumps(frame, allow_nan=False) + '\n').encode('utf-8')
        if self._closed:
            return False
        if self._socket is None:
            if time.monotonic() < self._next_attempt:
                return False
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self.timeout)
                self._socket.connect(self._endpoint)
                print(f'Connected to {self.address[0]}:{self.address[1]}')
            except OSError as error:
                self._disconnect()
                print(f'Waiting for ROS bridge: {error}')
                return False
        try:
            self._socket.sendall(payload)
            return True
        except OSError as error:
            self._disconnect()
            print(f'ROS bridge disconnected; retrying: {error}')
            return False

    def _disconnect(self):
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._next_attempt = time.monotonic() + self.retry_interval

    def close(self):
        self._closed = True
        self._disconnect()
