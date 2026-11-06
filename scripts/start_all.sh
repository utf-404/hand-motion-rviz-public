#!/usr/bin/env bash
# Run the camera tracker and ROS/RViz on this Ubuntu computer.
set -eo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
port="${HAND_RVIZ_PORT:-18765}"
camera="${HAND_RVIZ_CAMERA:-0}"
rviz="${HAND_RVIZ_RVIZ:-true}"
start_timeout="${HAND_RVIZ_START_TIMEOUT:-60}"
ros_setup="${HAND_RVIZ_ROS_SETUP:-/opt/ros/humble/setup.bash}"
system_path='/usr/bin:/bin:/usr/sbin:/sbin'

if [[ "$(uname -s)" != Linux ]]; then
  echo "start_all.sh runs locally on Ubuntu. Use start_remote.sh for the Mac/SSH workflow." >&2
  exit 1
fi
if [[ ! "$port" =~ ^[0-9]{1,5}$ ]] || ((10#$port < 1 || 10#$port > 65535)); then
  echo "Invalid TCP port: $port" >&2
  exit 1
fi
port=$((10#$port))
if [[ ! "$start_timeout" =~ ^[0-9]{1,5}$ ]] || ((10#$start_timeout < 1)); then
  echo "HAND_RVIZ_START_TIMEOUT must be a positive integer (seconds)." >&2
  exit 1
fi
start_timeout=$((10#$start_timeout))
if [[ "$rviz" != true && "$rviz" != false ]]; then
  echo "HAND_RVIZ_RVIZ must be true or false." >&2
  exit 1
fi
if [[ ! -f "$ros_setup" ]]; then
  echo "ROS setup not found: $ros_setup" >&2
  exit 1
fi
if [[ -n "${HAND_RVIZ_PYTHON:-}" ]]; then
  tracker_python="$(command -v "$HAND_RVIZ_PYTHON")" || {
    echo "Tracker Python not found: $HAND_RVIZ_PYTHON" >&2; exit 1;
  }
elif [[ -x "$repo_root/.venv/bin/python" ]]; then
  tracker_python="$repo_root/.venv/bin/python"
else
  tracker_python='/usr/bin/python3'
fi

if ! "$tracker_python" - <<'PY'
import cv2
import mediapipe as mp
assert hasattr(mp, 'solutions') and hasattr(mp.solutions, 'hands')
PY
then
  echo "Camera Python dependencies are missing or incompatible: $tracker_python" >&2
  echo "Install src/hand_motion_rviz/tracker/requirements.txt in .venv first." >&2
  exit 1
fi
if ! env -u PYTHONHOME -u VIRTUAL_ENV PATH="$system_path" /bin/bash -c \
  'source "$1" && command -v xacro >/dev/null' _ "$ros_setup"; then
  echo "xacro is missing. Install it with: sudo apt install ros-humble-xacro" >&2
  exit 1
fi
if ! /usr/bin/python3 - "$port" <<'PY'
import socket, sys
try:
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('0.0.0.0', int(sys.argv[1])))
except OSError as error:
    print(f'Cannot use TCP port {sys.argv[1]}: {error}', file=sys.stderr)
    raise SystemExit(1)
PY
then
  exit 1
fi

ros_pid=''
tracker_pid=''
stop_group() {
  local pid="$1"
  local grace_ticks="${2:-20}"
  local tick
  [[ -n "$pid" ]] || return 0
  # Each child is started in its own session. Only its process group is signalled.
  kill -INT -- "-$pid" 2>/dev/null || true
  for ((tick=0; tick<grace_ticks; tick++)); do
    kill -0 -- "-$pid" 2>/dev/null || break
    sleep 0.1
  done
  if kill -0 -- "-$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || true
    sleep 0.2
    kill -KILL -- "-$pid" 2>/dev/null || true
  fi
  wait "$pid" 2>/dev/null || true
}
cleanup() {
  local status=$?
  trap - EXIT INT TERM
  stop_group "$tracker_pid"
  # ROS launch needs time to apply its own 5s SIGTERM / 5s SIGKILL escalation
  # to children that may have their own process groups.
  stop_group "$ros_pid" 120
  return "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_session() {
  # Bash background jobs inherit SIGINT ignored; restore it before exec so the
  # tracker can catch KeyboardInterrupt and release its camera normally.
  setsid --wait /usr/bin/python3 -c '
import os, signal, sys
signal.signal(signal.SIGINT, signal.SIG_DFL)
os.execvp(sys.argv[1], sys.argv[1:])
' "$@" &
  session_pid=$!
}

echo "Starting local Ubuntu ROS/RViz on TCP port $port ..."
start_session /usr/bin/env -u PYTHONHOME -u VIRTUAL_ENV PATH="$system_path" \
  HAND_RVIZ_PORT="$port" HAND_RVIZ_ROS_SETUP="$ros_setup" \
  /bin/bash "$script_dir/start_ubuntu.sh" rviz:="$rviz"
ros_pid=$session_pid
deadline=$((SECONDS + start_timeout))
bridge_ready=false
while ((SECONDS < deadline)); do
  if ! kill -0 "$ros_pid" 2>/dev/null; then
    echo "The local ROS/RViz process stopped before the bridge became ready." >&2
    exit 1
  fi
  if /usr/bin/python3 - "$port" <<'PY'
import socket, sys
try:
    with socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=0.1):
        pass
except OSError:
    raise SystemExit(1)
PY
  then
    bridge_ready=true
    break
  fi
  sleep 0.1
done
if [[ "$bridge_ready" != true ]]; then
  echo "Timed out waiting for the local bridge after $start_timeout seconds." >&2
  exit 1
fi

echo "Starting local camera $camera. Press q in the tracker window to stop everything."
start_session "$tracker_python" "$repo_root/src/hand_motion_rviz/tracker/hand_tracker.py" \
  --host 127.0.0.1 --port "$port" --camera "$camera"
tracker_pid=$session_pid
while kill -0 "$tracker_pid" 2>/dev/null; do
  if ! kill -0 "$ros_pid" 2>/dev/null; then
    echo "The local ROS/RViz process stopped; shutting down the camera tracker." >&2
    exit 1
  fi
  sleep 0.1
done
status=0
wait "$tracker_pid" || status=$?
exit "$status"
