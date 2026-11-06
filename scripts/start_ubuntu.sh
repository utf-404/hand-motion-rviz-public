#!/usr/bin/env bash
set -eo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
workspace="${HAND_RVIZ_WORKSPACE:-$(cd "$script_dir/.." && pwd)}"
port="${HAND_RVIZ_PORT:-18765}"
ros_setup="${HAND_RVIZ_ROS_SETUP:-/opt/ros/humble/setup.bash}"

cd "$workspace"
# Keep ROS on Ubuntu's system Python even when the camera venv is activated.
unset PYTHONHOME VIRTUAL_ENV
export PATH='/usr/bin:/bin:/usr/sbin:/sbin'
source "$ros_setup"
/usr/bin/python3 /usr/bin/colcon build --symlink-install --packages-select hand_motion_rviz
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

exec /usr/bin/python3 /opt/ros/humble/bin/ros2 launch hand_motion_rviz hand_rviz.launch.py port:="$port" "$@"
