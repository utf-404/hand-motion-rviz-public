#!/usr/bin/env bash
set -eo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
remote="${HAND_RVIZ_REMOTE:-}"
remote_workspace="${HAND_RVIZ_REMOTE_WORKSPACE:-ws/hand-motion-rviz}"
port="${HAND_RVIZ_PORT:-18765}"
camera="${HAND_RVIZ_CAMERA:-0}"

if [[ -z "$remote" ]]; then
  echo "Set HAND_RVIZ_REMOTE to an SSH destination, for example user@ubuntu-host." >&2
  exit 1
fi

if [[ ! "$port" =~ ^[0-9]+$ ]] || ((port < 1 || port > 65535)); then
  echo "Invalid TCP port: $port" >&2
  exit 1
fi

if [[ -n "${HAND_RVIZ_PYTHON:-}" ]]; then
  tracker_python="$HAND_RVIZ_PYTHON"
elif [[ -x "$repo_root/.venv/bin/python" ]]; then
  tracker_python="$repo_root/.venv/bin/python"
else
  tracker_python="python3"
fi

if ! "$tracker_python" - <<'PY'
import cv2
import mediapipe as mp
assert hasattr(mp, 'solutions') and hasattr(mp.solutions, 'hands')
PY
then
  echo "Mac Python dependencies are missing or incompatible: $tracker_python" >&2
  echo "Install src/hand_motion_rviz/tracker/requirements.txt first." >&2
  exit 1
fi

if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Local TCP port $port is already in use." >&2
  exit 1
fi

# Quote the path for the remote login shell.
remote_directory="'${remote_workspace//\'/\'\\\'\'}'"
if [[ "$remote_workspace" != /* ]]; then
  remote_directory='"$HOME"/'"$remote_directory"
fi
remote_command="cd $remote_directory && HAND_RVIZ_PORT='$port' ./scripts/start_ubuntu.sh"
echo "Starting Ubuntu ROS/RViz over SSH ..."
ssh -tt -o ExitOnForwardFailure=yes \
  -L "$port:127.0.0.1:$port" \
  -- "$remote" "$remote_command" </dev/null &
ssh_pid=$!

cleanup() {
  trap - EXIT INT TERM
  if kill -0 "$ssh_pid" 2>/dev/null; then
    kill -TERM "$ssh_pid" 2>/dev/null || true
    wait "$ssh_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Waiting for the Ubuntu bridge on TCP port $port ..."
bridge_ready=false
for _ in {1..100}; do
  if ! kill -0 "$ssh_pid" 2>/dev/null; then
    echo "The remote ROS/RViz process stopped before the bridge became ready." >&2
    exit 1
  fi
  if ssh -o BatchMode=yes -o ConnectTimeout=2 -- "$remote" \
    "ss -ltn | grep -q ':$port '"; then
    bridge_ready=true
    break
  fi
  sleep 0.2
done

if [[ "$bridge_ready" != true ]]; then
  echo "Timed out waiting for the Ubuntu bridge on TCP port $port." >&2
  exit 1
fi

echo "Starting Mac camera $camera. Press q in the tracker window to stop everything."
"$tracker_python" "$repo_root/src/hand_motion_rviz/tracker/hand_tracker.py" \
  --host 127.0.0.1 \
  --port "$port" \
  --camera "$camera"
