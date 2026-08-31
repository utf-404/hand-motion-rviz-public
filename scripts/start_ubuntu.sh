#!/usr/bin/env bash
set -eo pipefail

workspace="${HAND_RVIZ_WORKSPACE:-/path/to/hand-motion-rviz}"
port="${HAND_RVIZ_PORT:-8765}"

cd "$workspace"
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash

if [[ -z "${DISPLAY:-}" ]]; then
  display="$(who | awk -v user="$(id -un)" '$1 == user && $2 ~ /^:/ {print $2; exit}')"
  if [[ -n "$display" ]]; then
    export DISPLAY="$display"
  fi
fi

if [[ -z "${XAUTHORITY:-}" && -f "/run/user/$(id -u)/gdm/Xauthority" ]]; then
  export XAUTHORITY="/run/user/$(id -u)/gdm/Xauthority"
fi

exec ros2 launch hand_motion_rviz hand_rviz.launch.py port:="$port" "$@"
