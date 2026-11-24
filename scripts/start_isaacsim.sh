#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/start_isaacsim.sh [--demo] [--headless-seconds N] [--topic NAME]

Live mode uses the existing publisher on /joint_states.
--demo uses a camera-free publisher on /hand_motion_demo/joint_states.
--headless-seconds N runs the simulation without a window for N seconds.
--topic NAME overrides the topic for Isaac Sim and the demo publisher.

HAND_ISAAC_PYTHON overrides the Isaac Sim installation's python.sh path.
HAND_ISAAC_XACRO overrides the xacro executable.
EOF
}

demo=false
headless_seconds=''
topic=''
while (($#)); do
  case "$1" in
    --demo)
      demo=true
      shift
      ;;
    --headless-seconds|--topic)
      if (($# < 2)) || [[ -z "$2" || "$2" == --* ]]; then
        echo "Missing value for $1." >&2
        exit 2
      fi
      if [[ "$1" == --headless-seconds ]]; then
        headless_seconds="$2"
      else
        topic="$2"
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$demo" == true ]]; then
  topic="${topic:-/hand_motion_demo/joint_states}"
else
  topic="${topic:-/joint_states}"
fi
if [[ ! "$topic" =~ ^(/[a-zA-Z_][a-zA-Z0-9_]*)+$ ]]; then
  echo "Expected an absolute ROS 2 topic name, got: $topic" >&2
  exit 2
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
package_root="$repo_root/src/hand_motion_rviz"
isaac_python="${HAND_ISAAC_PYTHON:-$HOME/isaacsim/python.sh}"
if ! isaac_python="$(command -v -- "$isaac_python")"; then
  echo "Isaac Sim python.sh not found. Set HAND_ISAAC_PYTHON to its path." >&2
  exit 1
fi
isaac_python="$(realpath -- "$isaac_python")"
ros_distro="${ROS_DISTRO:-humble}"
ros_bundle="$(dirname -- "$isaac_python")/exts/isaacsim.ros2.core/$ros_distro"
if [[ ! -d "$ros_bundle/lib" || ( "$demo" == true && ! -d "$ros_bundle/rclpy" ) ]]; then
  echo "Isaac Sim's bundled ROS 2 $ros_distro runtime is missing: $ros_bundle" >&2
  exit 1
fi

if [[ -n "${HAND_ISAAC_XACRO:-}" ]]; then
  if ! xacro="$(command -v -- "$HAND_ISAAC_XACRO")"; then
    echo "Cannot execute xacro: $HAND_ISAAC_XACRO" >&2
    exit 1
  fi
elif ! xacro="$(command -v xacro)"; then
  xacro="$repo_root/.venv/bin/xacro"
  if [[ ! -x "$xacro" ]]; then
    echo "xacro not found. Source ROS 2 or install xacro in .venv." >&2
    exit 1
  fi
fi

work_dir="$(mktemp -d)"
children=()
cleanup() {
  local pid attempt running
  trap - EXIT INT TERM
  for pid in "${children[@]}"; do
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  done
  for ((attempt = 0; attempt < 30; attempt++)); do
    running=false
    for pid in "${children[@]}"; do
      if kill -0 -- "-$pid" 2>/dev/null || kill -0 "$pid" 2>/dev/null; then
        running=true
      fi
    done
    if [[ "$running" == false ]]; then
      break
    fi
    sleep 0.1
  done
  for pid in "${children[@]}"; do
    kill -KILL -- "-$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  rm -rf -- "$work_dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

urdf="$work_dir/hand.urdf"
"$xacro" -o "$urdf" "$package_root/urdf/hand.urdf.xacro"
cd -- "$repo_root"

start_isaac() {
  local python_path="$1"
  shift
  setsid --wait env -u PYTHONHOME -u PYTHONEXE -u VIRTUAL_ENV \
    ROS_DISTRO="$ros_distro" RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}" \
    LD_LIBRARY_PATH="$ros_bundle/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    PYTHONPATH="$python_path" PYTHONNOUSERSITE=1 \
    "$isaac_python" "$@" &
  children+=("$!")
}

if [[ "$demo" == true ]]; then
  start_isaac "$ros_bundle/rclpy:$package_root" \
    -c 'from hand_motion_rviz.hand_bridge import main; main()' \
    --demo --ros-args -r '__node:=isaac_hand_demo' -r "/joint_states:=$topic"
  demo_pid="${children[0]}"
fi

sim_args=(--urdf "$urdf" --package-root "$package_root" --work-dir "$work_dir" --topic "$topic")
if [[ -n "$headless_seconds" ]]; then
  sim_args+=(--headless-seconds "$headless_seconds")
fi
start_isaac "$repo_root" -m isaac_hand.run "${sim_args[@]}"

if [[ "$demo" == false ]]; then
  wait "${children[0]}"
else
  status=0
  wait -n -p finished "${children[@]}" || status=$?
  if [[ "${finished:-}" == "$demo_pid" ]]; then
    echo "The demo publisher exited before Isaac Sim." >&2
    if ((status == 0)); then
      status=1
    fi
  fi
  exit "$status"
fi
