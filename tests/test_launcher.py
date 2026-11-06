"""Launch orchestration tests using fake camera and ROS processes, no hardware."""
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UbuntuLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        shutil.copy2(ROOT / 'scripts/start_all.sh', self.root / 'scripts/start_all.sh')
        self.write('setup.bash', 'export PATH="' + str(self.root / 'bin') + ':$PATH"\n')
        self.write('bin/xacro', '#!/bin/sh\nexit 0\n')
        self.write('scripts/start_ubuntu.sh', '#!/bin/bash\nexec /usr/bin/python3 "' +
                   str(self.root / 'backend.py') + '" "$@"\n')
        self.write('backend.py', '''import json, os, signal, socket, subprocess, sys, time
from pathlib import Path
root = Path(os.environ['TEST_ROOT'])
child = subprocess.Popen(['/usr/bin/python3', '-c', 'import time; time.sleep(60)'])
def stop(*args):
    child.terminate()
    child.wait(timeout=2)
    raise SystemExit(0)
signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
(root / 'backend.json').write_text(json.dumps({'pid': os.getpid(), 'child': child.pid, 'args': sys.argv[1:], 'path': os.environ['PATH']}))
mode = os.environ.get('TEST_BACKEND', 'ready')
if mode == 'fail':
    child.terminate(); child.wait(); raise SystemExit(7)
if mode == 'silent':
    while True: time.sleep(.1)
server = socket.socket()
server.bind(('127.0.0.1', int(os.environ['HAND_RVIZ_PORT'])))
server.listen()
server.settimeout(.1)
deadline = time.monotonic() + .6
while True:
    if mode == 'ready-fail' and time.monotonic() > deadline:
        child.terminate(); child.wait(); raise SystemExit(7)
    try:
        peer, _ = server.accept()
        peer.close()
    except socket.timeout:
        pass
''')
        self.write('.venv/bin/python', '''#!/usr/bin/python3
import json, os, signal, sys, time
from pathlib import Path
if sys.argv[1] == '-':
    sys.stdin.read()
    raise SystemExit(0)
root = Path(os.environ['TEST_ROOT'])
(root / 'tracker.json').write_text(json.dumps({'pid': os.getpid(), 'args': sys.argv[1:]}))
if os.environ.get('TEST_TRACKER') == 'stay':
    signal.signal(signal.SIGINT, lambda *args: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
    while True: time.sleep(.1)
raise SystemExit(int(os.environ.get('TEST_TRACKER_STATUS', '0')))
''')
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        self.env = dict(os.environ, TEST_ROOT=str(self.root),
                        HAND_RVIZ_ROS_SETUP=str(self.root / 'setup.bash'),
                        HAND_RVIZ_PORT=str(port), HAND_RVIZ_CAMERA='/dev/video2',
                        HAND_RVIZ_RVIZ='false', HAND_RVIZ_START_TIMEOUT='3')
        self.env.pop('HAND_RVIZ_PYTHON', None)
        self.env.pop('HAND_RVIZ_WORKSPACE', None)

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        path.chmod(0o755)

    def launch(self, **changes):
        return subprocess.Popen(['/bin/bash', str(self.root / 'scripts/start_all.sh')],
                                cwd=self.root, env=dict(self.env, **changes),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def finish(self, process):
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            self.fail('launcher failed to exit within 10 seconds')
        return process.returncode, output

    def assert_backend_stopped(self):
        record = json.loads((self.root / 'backend.json').read_text())
        for key in ['pid', 'child']:
            with self.subTest(process=key):
                self.assertFalse(Path('/proc', str(record[key])).exists(), f'{key} was left running')

    def test_local_launch_passes_camera_port_and_rviz_and_cleans_up(self):
        code, output = self.finish(self.launch())
        self.assertEqual(code, 0, output)
        tracker = json.loads((self.root / 'tracker.json').read_text())
        self.assertEqual(tracker['args'][1:], ['--host', '127.0.0.1', '--port',
                                             self.env['HAND_RVIZ_PORT'], '--camera', '/dev/video2'])
        self.assertIn('/tracker/hand_tracker.py', tracker['args'][0])
        backend = json.loads((self.root / 'backend.json').read_text())
        self.assertEqual(backend['args'], ['rviz:=false'])
        self.assertNotIn('/.venv/', backend['path'])
        self.assert_backend_stopped()

    def test_tracker_error_is_propagated_and_backend_is_stopped(self):
        code, output = self.finish(self.launch(TEST_TRACKER_STATUS='7'))
        self.assertEqual(code, 7, output)
        self.assert_backend_stopped()

    def test_backend_failure_does_not_start_tracker(self):
        code, output = self.finish(self.launch(TEST_BACKEND='fail'))
        self.assertEqual(code, 1, output)
        self.assertIn('stopped before the bridge became ready', output)
        self.assertFalse((self.root / 'tracker.json').exists())
        self.assert_backend_stopped()

    def test_readiness_timeout_stops_process_group(self):
        code, output = self.finish(self.launch(TEST_BACKEND='silent', HAND_RVIZ_START_TIMEOUT='1'))
        self.assertEqual(code, 1, output)
        self.assertIn('Timed out waiting for the local bridge', output)
        self.assertFalse((self.root / 'tracker.json').exists())
        self.assert_backend_stopped()

    def test_running_backend_failure_stops_tracker(self):
        code, output = self.finish(self.launch(TEST_BACKEND='ready-fail', TEST_TRACKER='stay'))
        self.assertEqual(code, 1, output)
        self.assertIn('shutting down the camera tracker', output)
        tracker_pid = json.loads((self.root / 'tracker.json').read_text())['pid']
        self.assertFalse(Path('/proc', str(tracker_pid)).exists())
        self.assert_backend_stopped()

    def test_occupied_port_does_not_start_processes(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', int(self.env['HAND_RVIZ_PORT'])))
            listener.listen()
            code, output = self.finish(self.launch())
        self.assertEqual(code, 1, output)
        self.assertIn('Cannot use TCP port', output)
        self.assertFalse((self.root / 'backend.json').exists())
        self.assertFalse((self.root / 'tracker.json').exists())

    def assert_signal_cleanup(self, signum, expected_code):
        process = self.launch(TEST_TRACKER='stay')
        deadline = time.monotonic() + 5
        while not (self.root / 'tracker.json').exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue((self.root / 'tracker.json').exists())
        tracker_pid = json.loads((self.root / 'tracker.json').read_text())['pid']
        process.send_signal(signum)
        code, output = self.finish(process)
        self.assertEqual(code, expected_code, output)
        self.assertFalse(Path('/proc', str(tracker_pid)).exists())
        self.assert_backend_stopped()

    def test_termination_stops_camera_and_backend(self):
        self.assert_signal_cleanup(signal.SIGTERM, 143)

    def test_interrupt_stops_camera_and_backend(self):
        self.assert_signal_cleanup(signal.SIGINT, 130)


if __name__ == '__main__':
    unittest.main()
