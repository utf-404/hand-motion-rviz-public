# Mac webcam → ROS 2 RViz hand

Mac 카메라에서 MediaPipe로 한 손의 다섯 손가락 굽힘 정도를 계산하고, Ubuntu의 ROS 2 브리지를 통해 RViz 손 모델에 반영하는 프로젝트입니다.

```text
Mac camera → hand_tracker.py → TCP/SSH tunnel → hand_bridge → /joint_states → RViz
```

## 환경

- Ubuntu 22.04, ROS 2 Humble, RViz2
- macOS Apple Silicon, Python 3.11
- 두 컴퓨터가 같은 네트워크에 연결되어 있어야 합니다.
- 예시 Ubuntu 계정/주소: `user@ubuntu-host`
- Ubuntu 작업공간: `/path/to/hand-motion-rviz`

## 최초 1회 설치

### Ubuntu

Ubuntu 데스크톱의 터미널에서 실행합니다.

```bash
cd /path/to/hand-motion-rviz
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### Mac

Mac의 이 저장소 루트에서 실행합니다. 검증된 MediaPipe/OpenCV 버전이 `requirements.txt`에 고정되어 있습니다.

```bash
cd ~/Desktop/hand-motion-rviz
python3 -m venv .venv
.venv/bin/python -m pip install -r src/hand_motion_rviz/mac/requirements.txt
```

macOS가 카메라 권한을 물으면 허용합니다. 나중에 변경하려면 **시스템 설정 → 개인정보 보호 및 보안 → 카메라**에서 사용하는 터미널 앱을 허용합니다.

## 매번 실행하는 방법

방화벽 설정이 필요 없고 통신도 암호화되는 SSH 터널 방식을 권장합니다. 아래 세 터미널을 순서대로 실행하고 계속 열어 둡니다.

### 1. Ubuntu: ROS와 RViz 시작

Ubuntu 데스크톱의 터미널에서 실행합니다. SSH의 일반 터미널에서는 RViz 창이 Ubuntu 화면에 나타나지 않을 수 있습니다.

```bash
cd /path/to/hand-motion-rviz
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch hand_motion_rviz hand_rviz.launch.py
```

다음 메시지가 보이면 준비된 상태입니다.

```text
Waiting for Mac hand-tracker on TCP port 8765
```

### 2. Mac 터미널 A: SSH 터널 시작

```bash
ssh -N -L 8765:127.0.0.1:8765 user@ubuntu-host
```

정상일 때는 아무 메시지도 출력하지 않고 계속 실행됩니다.

### 3. Mac 터미널 B: 카메라 추적 시작

```bash
cd ~/Desktop/hand-motion-rviz
.venv/bin/python src/hand_motion_rviz/mac/hand_tracker.py \
  --host 127.0.0.1 \
  --camera 0
```

`Connected to 127.0.0.1:8765`가 출력되면 연결된 상태입니다. `Hand tracker` 창에 손 전체가 보이도록 하면 Ubuntu RViz의 파란색 손가락이 움직입니다.

내장 카메라 대신 다른 카메라가 열리면 `--camera 1`을 사용합니다.

## 종료 방법

다음 순서로 종료합니다.

1. Mac의 `Hand tracker` 창에서 `q`를 누릅니다.
2. Mac 터널 터미널에서 `Ctrl+C`를 누릅니다.
3. Ubuntu ROS/RViz 터미널에서 `Ctrl+C`를 누릅니다.

## Ubuntu 단독 데모

Mac 없이 모델과 RViz만 확인할 때 사용합니다. 손가락이 자동으로 움직입니다.

```bash
cd /path/to/hand-motion-rviz
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch hand_motion_rviz hand_rviz.launch.py demo:=true
```

GUI가 없는 SSH 세션에서 ROS 데이터만 확인하려면 다음처럼 RViz를 끕니다.

```bash
ros2 launch hand_motion_rviz hand_rviz.launch.py demo:=true rviz:=false
```

## 직접 LAN 연결

신뢰할 수 있는 로컬 네트워크에서만 사용합니다. Ubuntu 방화벽이 활성화돼 있다면 TCP `8765`를 허용해야 합니다.

```bash
sudo ufw allow 8765/tcp
```

SSH 터널 없이 Mac에서 Ubuntu 주소로 직접 연결합니다.

```bash
.venv/bin/python src/hand_motion_rviz/mac/hand_tracker.py \
  --host 192.0.2.10 \
  --camera 0
```

기본 포트를 바꾸려면 양쪽 값을 같게 지정합니다.

```bash
# Ubuntu
ros2 launch hand_motion_rviz hand_rviz.launch.py port:=18765

# Mac
.venv/bin/python src/hand_motion_rviz/mac/hand_tracker.py --host 192.0.2.10 --port 18765
```

## 상태 확인

Ubuntu에서 ROS 환경을 source한 뒤 사용할 수 있습니다.

```bash
ros2 node list
ros2 topic hz /joint_states
ros2 topic echo --once /joint_states
ros2 topic info /robot_description --verbose
```

정상 상태:

- 노드: `/hand_bridge`, `/robot_state_publisher`, `/rviz`
- `/joint_states`: 약 30Hz
- RViz가 `/robot_description`을 구독
- RViz Fixed Frame: `palm`

## 문제 해결

### `Waiting for ROS bridge: timed out`

- Ubuntu launch를 먼저 시작했는지 확인합니다.
- SSH 터널 터미널이 계속 실행 중인지 확인합니다.
- Mac 트래커는 터널 사용 시 반드시 `--host 127.0.0.1`로 실행합니다.
- 로컬 포트 사용 여부는 `lsof -nP -iTCP:8765`로 확인할 수 있습니다.

### RViz에 손 모델이 보이지 않음

- Ubuntu 데스크톱에서 RViz 창이 실제로 실행 중인지 확인합니다.
- Displays에서 `Robot Hand`가 활성화되어 있는지 확인합니다.
- Global Options의 Fixed Frame이 `palm`인지 확인합니다.
- 다음 명령의 `/rviz` 구독이 1개인지 확인합니다.

```bash
ros2 topic info /robot_description --verbose
```

### 카메라가 열리지 않거나 트래커가 종료됨

- macOS 카메라 권한을 확인합니다.
- 카메라를 사용하는 FaceTime, Zoom 등의 앱을 종료합니다.
- `--camera 0` 대신 `--camera 1`을 시도합니다.

### `mediapipe`에 `solutions`가 없음

호환되지 않는 최신 MediaPipe가 설치된 상태입니다. 저장소의 가상환경을 다시 만듭니다.

```bash
cd ~/Desktop/hand-motion-rviz
mv .venv .venv.old
python3 -m venv .venv
.venv/bin/python -m pip install -r src/hand_motion_rviz/mac/requirements.txt
```

## 주요 파일

- `src/hand_motion_rviz/mac/hand_tracker.py`: Mac 카메라 추적 및 TCP 전송
- `src/hand_motion_rviz/hand_motion_rviz/hand_bridge.py`: TCP 수신 및 `/joint_states` 발행
- `src/hand_motion_rviz/launch/hand_rviz.launch.py`: 브리지, robot_state_publisher, RViz 실행
- `src/hand_motion_rviz/urdf/hand.urdf.xacro`: 손 모델
- `src/hand_motion_rviz/config/hand.rviz`: RViz 표시와 카메라 시점
