# Mac webcam → ROS 2 RViz two hands

Mac 카메라에서 MediaPipe로 왼손과 오른손의 손가락 굽힘 정도를 각각 계산하고, Ubuntu의 ROS 2 브리지를 통해 30관절 RViz 양손 모델에 반영하는 프로젝트입니다.

```text
Mac camera → left/right curls → TCP/SSH tunnel → hand_bridge → /joint_states → RViz
```

## 환경

- Ubuntu 22.04, ROS 2 Humble, RViz2
- macOS Apple Silicon, Python 3.11
- 두 컴퓨터가 같은 네트워크에 연결되어 있어야 합니다.
- 예시 Ubuntu 계정/주소: `user@ubuntu-host`
- Ubuntu 작업공간: `/path/to/hand-motion-rviz`

## 실행 방법 요약

Ubuntu 데스크톱에 로그인되어 있고 최초 설치를 완료했다면, 다음 순서로 실행합니다.

### 1. Mac의 최신 코드를 Ubuntu로 복사

Mac 터미널에서 실행합니다. Ubuntu에 이미 최신 코드가 있다면 이 단계는 생략할 수 있습니다.

```bash
cd ~/Desktop/hand-motion-rviz
rsync -av \
  --exclude .git --exclude .venv \
  --exclude build --exclude install --exclude log \
  ./ user@ubuntu-host:/path/to/hand-motion-rviz/
```

### 2. Ubuntu RViz와 Mac 카메라를 함께 실행

같은 Mac 터미널에서 실행합니다.

```bash
cd ~/Desktop/hand-motion-rviz
./scripts/start_all.sh
```

이 명령 하나가 SSH 터널 생성, Ubuntu 빌드, ROS/RViz 실행, Mac 카메라 추적기 실행을 모두 처리합니다. Mac의 `Two-hand tracker` 창에 양손을 보여주면 Ubuntu RViz의 양손 모델이 각각 움직입니다.

### 3. 종료

Mac의 `Two-hand tracker` 창에서 `q`를 누르면 카메라 추적기, SSH 연결, Ubuntu ROS/RViz가 함께 종료됩니다.

카메라 번호나 연결 정보를 바꿀 때는 다음처럼 실행합니다.

```bash
HAND_RVIZ_CAMERA=1 ./scripts/start_all.sh
HAND_RVIZ_REMOTE=user@ubuntu-host ./scripts/start_all.sh
HAND_RVIZ_PORT=18765 ./scripts/start_all.sh
```

## 최초 1회 설치

### Ubuntu

Ubuntu 데스크톱의 터미널에서 실행합니다.

```bash
cd /path/to/hand-motion-rviz
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### Mac: 가상환경 사용

Mac의 이 저장소 루트에서 실행합니다. 검증된 MediaPipe/OpenCV 버전이 `requirements.txt`에 고정되어 있습니다.

```bash
cd ~/Desktop/hand-motion-rviz
python3 -m venv .venv
.venv/bin/python -m pip install -r src/hand_motion_rviz/mac/requirements.txt
```

### Mac: 가상환경 없이 사용

이 Mac에는 `pyenv` Python 3.11.5가 설치되어 있으므로 해당 Python에 패키지를 한 번 직접 설치할 수 있습니다. macOS 시스템 Python에 설치하는 방식보다 안전하지만, 이 Python을 사용하는 다른 프로젝트와 패키지 버전을 공유한다는 점은 주의해야 합니다.

```bash
cd ~/Desktop/hand-motion-rviz
~/.pyenv/versions/3.11.5/bin/python3 -m pip install \
  -r src/hand_motion_rviz/mac/requirements.txt
```

원클릭 실행 시 이 Python을 명시합니다.

```bash
HAND_RVIZ_PYTHON=~/.pyenv/versions/3.11.5/bin/python3 \
  ./scripts/start_all.sh
```

트래커만 직접 실행할 수도 있습니다.

```bash
~/.pyenv/versions/3.11.5/bin/python3 \
  src/hand_motion_rviz/mac/hand_tracker.py \
  --host 127.0.0.1 \
  --camera 0
```

macOS가 카메라 권한을 물으면 허용합니다. 나중에 변경하려면 **시스템 설정 → 개인정보 보호 및 보안 → 카메라**에서 사용하는 터미널 앱을 허용합니다.

## 수동 실행 방법

문제를 단계별로 확인하거나 각 프로세스를 따로 제어할 때 사용합니다. 방화벽 설정이 필요 없고 통신도 암호화되는 SSH 터널 방식이며, 아래 세 터미널을 순서대로 실행하고 계속 열어 둡니다.

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

`Connected to 127.0.0.1:8765`가 출력되면 연결된 상태입니다. `Two-hand tracker` 창에 양손 전체가 보이도록 하면 Ubuntu RViz의 왼손과 오른손이 각각 움직입니다. 화면에서 사라진 손은 열린 자세로 돌아갑니다.

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
- `/joint_states`: 왼손 15개와 오른손 15개, 총 30개 관절
- RViz Fixed Frame: `hands_base`

## 손 모델 관절 구조

카메라는 왼손과 오른손을 구분하여 손가락마다 하나의 curl 값을 보냅니다. 브리지는 각 값을 해당 손가락의 세 관절에 서로 다른 최대각으로 분배합니다. 모든 링크와 관절 이름에는 `left_` 또는 `right_` 접두사가 붙습니다.

| 손가락 | 관절 | 최대 굽힘각 |
| --- | --- | --- |
| 엄지 | CMC / MCP / IP | 0.75 / 1.05 / 1.10 rad |
| 검지 | MCP / PIP / DIP | 1.15 / 1.35 / 0.95 rad |
| 중지 | MCP / PIP / DIP | 1.15 / 1.35 / 0.95 rad |
| 약지 | MCP / PIP / DIP | 1.15 / 1.35 / 0.95 rad |
| 소지 | MCP / PIP / DIP | 1.15 / 1.35 / 0.95 rad |

손마다 15개씩 총 30개의 revolute joint가 있으며, 두 손은 공통 루트 링크 `hands_base` 아래에 좌우 대칭으로 배치됩니다. 외부 메시 패키지 없이 Xacro 기본 도형만 사용하므로 별도 모델 다운로드나 라이선스 의존성이 없습니다.

## 문제 해결

### `Waiting for ROS bridge: timed out`

- Ubuntu launch를 먼저 시작했는지 확인합니다.
- SSH 터널 터미널이 계속 실행 중인지 확인합니다.
- Mac 트래커는 터널 사용 시 반드시 `--host 127.0.0.1`로 실행합니다.
- 로컬 포트 사용 여부는 `lsof -nP -iTCP:8765`로 확인할 수 있습니다.

### RViz에 손 모델이 보이지 않음

- Ubuntu 데스크톱에서 RViz 창이 실제로 실행 중인지 확인합니다.
- Displays에서 `Robot Hands`가 활성화되어 있는지 확인합니다.
- Global Options의 Fixed Frame이 `hands_base`인지 확인합니다.
- 다음 명령의 `/rviz` 구독이 1개인지 확인합니다.

```bash
ros2 topic info /robot_description --verbose
```

### 카메라가 열리지 않거나 트래커가 종료됨

- macOS 카메라 권한을 확인합니다.
- 카메라를 사용하는 FaceTime, Zoom 등의 앱을 종료합니다.
- `--camera 0` 대신 `--camera 1`을 시도합니다.

### `mediapipe`에 `solutions`가 없음

호환되지 않는 최신 MediaPipe가 설치된 상태입니다. 가상환경을 사용한다면 저장소의 환경을 다시 만듭니다.

```bash
cd ~/Desktop/hand-motion-rviz
mv .venv .venv.old
python3 -m venv .venv
.venv/bin/python -m pip install -r src/hand_motion_rviz/mac/requirements.txt
```

가상환경을 사용하지 않는다면 pyenv Python에 고정 버전을 다시 설치합니다.

```bash
~/.pyenv/versions/3.11.5/bin/python3 -m pip install --force-reinstall \
  -r src/hand_motion_rviz/mac/requirements.txt
```

## 주요 파일

- `src/hand_motion_rviz/mac/hand_tracker.py`: Mac 카메라 추적 및 TCP 전송
- `src/hand_motion_rviz/hand_motion_rviz/hand_bridge.py`: TCP 수신 및 `/joint_states` 발행
- `src/hand_motion_rviz/launch/hand_rviz.launch.py`: 브리지, robot_state_publisher, RViz 실행
- `src/hand_motion_rviz/urdf/hand.urdf.xacro`: 손 모델
- `src/hand_motion_rviz/config/hand.rviz`: RViz 표시와 카메라 시점
- `scripts/start_all.sh`: Mac에서 전체 시스템 원클릭 실행
- `scripts/start_ubuntu.sh`: Ubuntu 빌드 및 ROS/RViz 실행
