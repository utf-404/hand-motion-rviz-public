# Mac webcam → ROS 2 RViz hand

This project maps the five finger curls detected by a Mac webcam to a simple RViz hand.

## Ubuntu (this computer)

```bash
cd /path/to/hand-motion-rviz
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 launch hand_motion_rviz hand_rviz.launch.py
```

The launch starts the ROS bridge on TCP port `8765` and RViz with the hand already displayed. Use `rviz:=false` when starting it in a non-graphical SSH session.

For an Ubuntu-only check without the Mac camera, run `ros2 run hand_motion_rviz hand_bridge --demo` in one terminal and RViz in another.

## Mac

Open a local Terminal (not an SSH prompt), then:

```bash
mkdir -p ~/hand-tracker
scp user@ubuntu-host:/path/to/hand-motion-rviz/src/hand_motion_rviz/mac/hand_tracker.py ~/hand-tracker/
scp user@ubuntu-host:/path/to/hand-motion-rviz/src/hand_motion_rviz/mac/requirements.txt ~/hand-tracker/
cd ~/hand-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python hand_tracker.py --host 192.0.2.10
```

macOS will ask Terminal for camera permission. Allow it. Keep both computers on the same LAN; if a firewall is enabled on Ubuntu, allow TCP port `8765`.

## Connection troubleshooting

Start the Ubuntu launch command first and leave it running. It must show `Waiting for Mac hand-tracker on TCP port 8765` before starting the Mac script.

If the Mac script repeatedly prints `Waiting for ROS bridge: timed out`, use an SSH tunnel. In another **local Mac** terminal run:

```bash
ssh -N -L 8765:localhost:8765 user@ubuntu-host
```

Then use the tunnel from the camera terminal:

```bash
python hand_tracker.py --host 127.0.0.1
```

The tunnel uses the already working SSH connection and avoids a firewall blocking port `8765`.
