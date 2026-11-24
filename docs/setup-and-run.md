# 설치 및 실행

명령은 각 컴퓨터에 클론한 이 저장소의 루트에서 실행합니다. 기본 환경은 Ubuntu 22.04, ROS 2 Humble, Python 3.10입니다.

## 설치

RViz2 또는 웹캠 실시간 추적을 사용하려면 Ubuntu에 ROS 2 Humble을 설치한 다음 빌드 도구와 손 모델 변환 도구를 설치합니다. [ROS 2 Humble 설치 안내](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)

```bash
sudo apt update
sudo apt install python3-venv python3-colcon-common-extensions \
  ros-humble-xacro ros-humble-robot-state-publisher ros-humble-rviz2
```

웹캠을 사용할 컴퓨터에서는 트래커 가상환경을 준비합니다. 설치 목록에는 MediaPipe, OpenCV, NumPy의 호환 버전이 지정되어 있습니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/hand_motion_rviz/tracker/requirements.txt
```

트래커는 `.venv`의 Python을, Ubuntu의 ROS 노드는 시스템 Python을 씁니다. 실행기에서 가상환경의 Python을 직접 선택하므로 활성화는 선택 사항입니다.

## RViz2 실행

### 웹캠과 RViz2

Ubuntu 데스크톱 터미널에서 실행합니다. 실행기가 ROS 패키지를 빌드하고 RViz2를 열며, 브리지가 준비되면 카메라 트래커를 시작합니다.

```bash
./scripts/start_all.sh
```

카메라에 양손 전체를 보여주면 손가락 굽힘과 손목 회전이 각각 반영됩니다. 기본 화면에서 손바닥이 앞을 보고 왼손 모델은 왼쪽에, 오른손 모델은 오른쪽에 놓입니다. 손이 화면에서 사라지면 해당 모델이 열린 자세와 기본 방향으로 돌아갑니다. 종료하려면 카메라 창에서 `q`를 누르거나 터미널에서 `Ctrl+C`를 누릅니다.

| 환경 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `HAND_RVIZ_CAMERA` | `0` | 카메라 번호 또는 `/dev/video0` 같은 장치 경로 |
| `HAND_RVIZ_PORT` | `18765` | 트래커와 ROS 브리지의 TCP 포트 |
| `HAND_RVIZ_PYTHON` | `.venv/bin/python`이 있으면 사용 | 트래커용 Python 경로 |
| `HAND_RVIZ_START_TIMEOUT` | `60` | 빌드와 브리지 시작을 기다리는 시간(초) |
| `HAND_RVIZ_RVIZ` | `true` | `false`면 RViz2 창을 끄고 카메라와 ROS 발행 유지 |

```bash
HAND_RVIZ_CAMERA=1 HAND_RVIZ_START_TIMEOUT=120 ./scripts/start_all.sh
```

### 웹캠 없는 데모

```bash
./scripts/start_ubuntu.sh demo:=true
```

실행기가 ROS 환경을 로드하고 패키지를 빌드합니다. 화면 없이 ROS 발행만 확인하려면 `rviz:=false`를 덧붙입니다.

### 브리지와 트래커 수동 실행

터미널 A에서 ROS 환경을 로드하고 패키지를 빌드한 뒤 브리지와 RViz2를 시작합니다. 설치가 끝난 뒤에는 빌드와 실행을 묶은 `./scripts/start_ubuntu.sh`도 사용할 수 있습니다.

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select hand_motion_rviz
source install/setup.bash
ros2 launch hand_motion_rviz hand_rviz.launch.py
```

터미널 B에서 트래커를 시작합니다. Ubuntu에서는 기본 카메라 백엔드가 V4L2입니다.

```bash
.venv/bin/python src/hand_motion_rviz/tracker/hand_tracker.py --camera 0
```

카메라 장치를 직접 선택하려면 `--camera /dev/video0 --backend v4l2`를 지정합니다. TCP 포트를 바꾸면 두 터미널에서 같은 값을 지정합니다.

```bash
# 터미널 A
ros2 launch hand_motion_rviz hand_rviz.launch.py port:=18766

# 터미널 B
.venv/bin/python src/hand_motion_rviz/tracker/hand_tracker.py --port 18766
```

## Isaac Sim 실행

Isaac Sim 6.2와 `xacro`가 필요합니다. 카메라 없는 데모는 Isaac Sim에 포함된 ROS 2 런타임을 사용합니다. 기본 실행 경로는 `~/isaacsim/python.sh`입니다. `xacro`는 `PATH`에서 찾고, 없으면 저장소의 `.venv/bin/xacro`를 사용합니다.

ROS 환경에서 `xacro`를 쓸 수 없다면 Python 가상환경에 설치합니다. Ubuntu에 `venv` 모듈이 없다면 `sudo apt install python3-venv`로 준비합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install xacro
```

설치 위치나 실행 파일을 직접 지정하려면 환경 변수를 사용합니다.

| 환경 변수 | 지정할 값 |
| --- | --- |
| `HAND_ISAAC_PYTHON` | 설치한 Isaac Sim의 `python.sh` 경로 |
| `HAND_ISAAC_XACRO` | 사용할 `xacro` 실행 파일의 경로 또는 `PATH`에 있는 이름 |

### 웹캠 없는 데모

```bash
./scripts/start_isaacsim.sh --demo
```

데모의 기본 토픽은 `/hand_motion_demo/joint_states`입니다. `--topic /example/joint_states`를 지정하면 데모 발행자와 Isaac Sim 구독자가 함께 그 토픽을 사용합니다. 창을 닫거나 터미널에서 `Ctrl+C`를 누르면 데모 발행도 종료됩니다.

창 없이 8초 동안 실행하려면 `--headless-seconds`를 추가합니다. 로그에서 처음 수신한 관절 수와 관절 각도의 변화 범위를 확인할 수 있습니다.

```bash
./scripts/start_isaacsim.sh --demo --headless-seconds 8
```

### 웹캠 입력을 두 화면에 표시

터미널 A에서 `./scripts/start_all.sh`를 실행한 뒤 터미널 B에서 Isaac Sim을 시작합니다. RViz2와 Isaac Sim이 동일한 `/joint_states`의 손가락 굽힘과 손목 회전을 표시합니다.

```bash
./scripts/start_isaacsim.sh
```

ROS 도메인이나 DDS 구현을 바꿨다면 두 터미널에서 `ROS_DOMAIN_ID`와 `RMW_IMPLEMENTATION`을 각각 같은 값으로 맞춥니다. 라이브 입력이 다른 토픽에서 발행된다면 Isaac Sim 실행기에 `--topic`으로 해당 토픽을 지정합니다.

Isaac Sim 화면만 사용하려면 터미널 A에서 `HAND_RVIZ_RVIZ=false ./scripts/start_all.sh`를 실행합니다. 이 옵션으로도 웹캠 미리보기와 ROS 발행은 계속됩니다.

## 원격 실행

Mac의 웹캠과 Ubuntu의 ROS 환경을 SSH로 연결할 수 있습니다. Ubuntu에서 위의 ROS 의존성을 설치하고 데스크톱에 로그인합니다. Mac의 체크아웃에서는 위의 트래커 가상환경을 준비합니다. macOS의 `auto` 카메라 백엔드는 AVFoundation입니다.

스크립트는 원격 사용자 홈 아래 `ws/hand-motion-rviz`에서 RViz2와 브리지를 시작합니다. 원격 체크아웃 폴더가 `ws/hand-motion-rviz-public`이라면 `HAND_RVIZ_REMOTE_WORKSPACE`에 해당 경로를 넣습니다. 절대 경로 또는 원격 사용자 홈을 기준으로 한 상대 경로를 사용할 수 있습니다.

```bash
# Mac 터미널에서 실행합니다. SSH 설정의 호스트 별칭도 사용할 수 있습니다.
HAND_RVIZ_REMOTE=user@ubuntu-host \
  HAND_RVIZ_REMOTE_WORKSPACE=ws/hand-motion-rviz-public \
  ./scripts/start_remote.sh
```

기존 `mac/hand_tracker.py` 경로도 호환됩니다. 트래커를 직접 실행할 때는 `--host`와 `--port`로 신뢰할 수 있는 LAN의 브리지 주소나 SSH 터널의 로컬 주소를 지정합니다.

실행 중 오류나 연결 상태는 [문제 해결](troubleshooting.md)에서 확인합니다.
