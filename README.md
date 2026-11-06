# Ubuntu webcam → ROS 2 RViz two hands

Ubuntu 컴퓨터 한 대에서 웹캠으로 왼손과 오른손의 굽힘과 방향을 추적하고, ROS 2 브리지를 통해 RViz의 36관절 양손 모델을 움직입니다.

```text
Ubuntu webcam → MediaPipe → local TCP → hand_bridge → /joint_states → RViz
```

기본 환경은 Ubuntu 22.04, ROS 2 Humble, Python 3.10입니다. Ubuntu 데스크톱에서 카메라 미리보기와 RViz를 함께 실행합니다.

## 최초 설치

ROS 2 Humble이 설치된 Ubuntu에서 실행합니다. `sudo` 설치는 사용자 터미널에서 인증이 필요할 수 있습니다.

```bash
sudo apt update
sudo apt install python3-venv python3-colcon-common-extensions \
  ros-humble-xacro ros-humble-robot-state-publisher ros-humble-rviz2

cd ~/ws/hand-motion-rviz
python3 -m venv .venv
.venv/bin/python -m pip install -r src/hand_motion_rviz/tracker/requirements.txt

source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select hand_motion_rviz
```

카메라 트래커는 `.venv`의 MediaPipe/OpenCV를 사용하고 ROS 노드는 시스템 Python을 사용합니다. 전체 실행 전에 `.venv`를 활성화할 필요는 없습니다. 트래커 의존성은 `numpy<2`, `mediapipe==0.10.21`, `opencv-contrib-python==4.11.0.86`으로 지정되어 있습니다.

`xacro`는 손 모델을 URDF로 변환할 때 필요합니다. `colcon build`와 브리지 단독 테스트는 이 실행 의존성을 자동 설치하지 않습니다.

## 카메라와 RViz 함께 실행

Ubuntu 데스크톱 터미널에서 다음 명령을 실행합니다.

```bash
cd ~/ws/hand-motion-rviz
./scripts/start_all.sh
```

기본 TCP 포트는 `18765`입니다.

이 명령은 로컬 ROS/RViz를 시작하고 브리지가 준비되면 같은 컴퓨터의 카메라 트래커를 실행합니다. 트래커 창에 양손 전체를 보여주면 RViz의 왼손과 오른손이 각각 움직입니다. 손바닥을 기울이거나 돌리면 모델의 손목도 3축으로 회전합니다. 화면에서 사라진 손은 열린 자세와 기본 방향으로 돌아갑니다.

기본 RViz 시점은 손바닥을 정면에 가깝게 보며 손가락이 위쪽을 향하도록 설정했습니다. 기존 배치를 교환해 왼손 모델은 화면 왼쪽, 오른손 모델은 화면 오른쪽에 놓입니다. 이 배치는 모델 위치만 바꾸며 추적 손의 left/right 식별을 바꾸지 않습니다. RViz 시점을 마우스로 돌리면 화면에서 보이는 좌우 관계도 달라질 수 있습니다.

트래커 창에서 `q`를 누르거나 터미널에서 `Ctrl+C`를 누르면 이 명령이 시작한 프로세스들이 함께 종료됩니다.

카메라 번호, 포트, 트래커 Python을 바꿀 수 있습니다.

```bash
HAND_RVIZ_CAMERA=1 ./scripts/start_all.sh
HAND_RVIZ_CAMERA=/dev/video0 ./scripts/start_all.sh
HAND_RVIZ_PORT=18766 ./scripts/start_all.sh
HAND_RVIZ_PYTHON=/path/to/venv/bin/python ./scripts/start_all.sh
HAND_RVIZ_START_TIMEOUT=120 ./scripts/start_all.sh
```

시작 제한시간은 기본 60초이며 빌드와 브리지 준비를 기다리는 시간에 적용됩니다.

RViz 창 없이 카메라 추적과 ROS 데이터 발행을 확인하려면:

```bash
HAND_RVIZ_RVIZ=false ./scripts/start_all.sh
```

이 경우에도 카메라 미리보기는 열립니다.

## 수동 실행

각 프로세스를 따로 확인할 때는 터미널 두 개를 사용합니다.

터미널 A에서 ROS와 RViz를 실행합니다.

```bash
cd ~/ws/hand-motion-rviz
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch hand_motion_rviz hand_rviz.launch.py
```

빌드부터 실행하려면 `./scripts/start_ubuntu.sh`를 사용할 수 있습니다. 이 스크립트는 기본적으로 저장소를 작업공간으로 사용하며, `HAND_RVIZ_WORKSPACE`로 다른 작업공간을 지정할 수 있습니다.

터미널 B에서 카메라 트래커를 실행합니다. 기본 연결 주소는 같은 컴퓨터의 `127.0.0.1`입니다.

```bash
cd ~/ws/hand-motion-rviz
.venv/bin/python src/hand_motion_rviz/tracker/hand_tracker.py --camera 0
```

Ubuntu의 `auto` 카메라 백엔드는 V4L2를 사용합니다. 장치 경로나 백엔드를 직접 지정할 수도 있습니다.

```bash
.venv/bin/python src/hand_motion_rviz/tracker/hand_tracker.py \
  --camera /dev/video0 --backend v4l2
```

카메라 창에서 `q`로 트래커를 종료한 뒤, ROS 터미널에서 `Ctrl+C`를 누릅니다. 포트를 바꾸면 양쪽 값을 같게 지정합니다.

```bash
# 터미널 A
ros2 launch hand_motion_rviz hand_rviz.launch.py port:=18766

# 터미널 B
.venv/bin/python src/hand_motion_rviz/tracker/hand_tracker.py --port 18766
```

## 카메라 없는 데모

카메라를 열지 않고 손가락과 손목이 자동으로 움직이는 모델을 확인합니다.

```bash
cd ~/ws/hand-motion-rviz
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch hand_motion_rviz hand_rviz.launch.py demo:=true
```

ROS 데이터만 확인하려면 다음과 같이 실행합니다. `rviz:=false`이므로 화면에 RViz 창은 열리지 않습니다.

```bash
ros2 launch hand_motion_rviz hand_rviz.launch.py demo:=true rviz:=false
```

## 연결 상태와 복구

- 트래커는 브리지가 시작되지 않았거나 연결이 끊겨도 카메라 미리보기를 유지하며 자동 재접속합니다.
- 전송 실패한 프레임은 버리고, 재접속 후 현재 자세부터 보냅니다.
- 브리지는 기본 1초 동안 유효한 프레임이 없으면 양손을 열린 자세로 바꾸고 무응답 연결을 해제합니다. 연결 종료를 감지하면 즉시 열린 자세로 돌아갑니다.
- 브리지 로그에 연결·수신 상태 변화가 표시됩니다. 트래커의 `Connected`는 마지막 프레임을 TCP로 보냈다는 뜻이며 RViz 표시 완료 응답은 아닙니다.

끊김 판정 시간과 재시도 간격을 바꾸려면:

```bash
# ROS 브리지
ros2 launch hand_motion_rviz hand_rviz.launch.py stale_timeout:=1.5

# 카메라 트래커
.venv/bin/python src/hand_motion_rviz/tracker/hand_tracker.py \
  --retry-interval 2 --network-timeout 0.2
```

각 연결·전송 작업은 `network-timeout`까지 기다릴 수 있습니다. 긴 값은 미리보기와 종료 키 반응을 지연시킵니다. 열린 자세 전환은 RViz 표시 동작이며 실제 로봇의 정지 제어를 대신하지 않습니다.

`--host`로 IPv4 주소 또는 IPv4로 해석되는 호스트명을 지정할 수 있습니다. DNS 조회는 카메라를 열기 전에 한 번 수행하며 초기 조회에는 네트워크 제한 시간이 적용되지 않습니다. 실행 중 호스트명의 IP가 변경되면 트래커를 다시 시작하세요.

## 상태 확인

ROS 환경을 로드한 다른 터미널에서 실행합니다.

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 node list
ros2 topic hz /joint_states
ros2 topic echo --once /joint_states
ros2 topic info /robot_description --verbose
```

정상 실행 시 `/hand_bridge`, `/robot_state_publisher`와 RViz를 켰다면 `/rviz`가 보입니다. `/joint_states`는 약 30Hz로 손가락 30개와 손목 회전 6개, 총 36개 관절을 발행합니다. RViz의 Fixed Frame은 `hands_base`입니다.

## 문제 해결

### `No such file or directory: 'xacro'`

`sudo apt install ros-humble-xacro`로 설치하고 ROS 환경을 다시 로드한 뒤 실행하세요. `rviz:=false`인 경우에도 손 모델 변환에는 필요합니다.

### 카메라가 열리지 않음

`ls /dev/video*`로 장치가 있는지 확인하고 `HAND_RVIZ_CAMERA=1` 또는 `/dev/videoN`을 지정하세요. 카메라를 사용하는 브라우저·화상회의 앱은 종료합니다. 장치 파일에 현재 사용자의 읽기·쓰기 권한이 있는지도 확인하세요.

### `mediapipe`에 `solutions`가 없음

트래커에 지정한 Python이 저장소의 가상환경인지 확인하고 고정 의존성을 다시 설치합니다.

```bash
.venv/bin/python -m pip install -r src/hand_motion_rviz/tracker/requirements.txt
.venv/bin/python -c 'import mediapipe as mp; print(mp.__version__); print(mp.solutions.hands)'
```

### `Waiting for ROS bridge` 또는 포트 사용 중

ROS 터미널의 앞선 오류부터 확인하세요. 별도로 켜 둔 브리지나 이전 실행이 포트를 사용한다면 종료하거나 양쪽 포트를 함께 변경합니다.

```bash
ss -ltn 'sport = :18765'
```

### RViz에 손 모델이 보이지 않음

Ubuntu 데스크톱에서 실행하고, Displays의 `Robot Hands`와 Fixed Frame `hands_base`를 확인하세요. `demo:=true rviz:=false`는 창을 열지 않는 검사 명령입니다.

## 손 모델과 통신 형식

손가락마다 curl 값 하나를 계산해 세 관절에 서로 다른 최대각으로 분배합니다. 개별 관절 각도를 직접 추정하는 모델은 아닙니다.

| 손가락 | 관절 | 최대 굽힘각 |
| --- | --- | --- |
| 엄지 | CMC / MCP / IP | 0.75 / 1.05 / 1.10 rad |
| 검지·중지·약지·소지 | MCP / PIP / DIP | 1.15 / 1.35 / 0.95 rad |

손목은 손마다 yaw(Z) → pitch(Y) → roll(X)의 연속 관절로 연결됩니다. 손목 방향은 손목·검지/중지/소지 MCP의 3D 위치로 계산하며, 가능하면 MediaPipe world landmarks를 사용합니다. 손가락 curl과 손목 방향을 같은 프레임으로 전달합니다.

양손은 공통 루트 `hands_base` 아래 배치되며 링크·관절에는 `left_` 또는 `right_` 접두사가 붙습니다. Xacro 기본 도형으로 모델을 구성해 외부 메시가 필요하지 않습니다.

TCP에는 UTF-8 JSON 뒤에 줄바꿈(`\n`)을 붙여 보냅니다. `left`, `right`는 엄지부터 소지까지 숫자 다섯 개이며 유한한 값은 0~1로 제한됩니다. 문자열·boolean·NaN·Infinity는 허용하지 않습니다. 프레임 크기는 최대 16 KiB입니다.

```json
{"hands":{"left":[0,0.2,0.4,0.6,1],"right":[0,0,0,0,0]},"wrist_rpy":{"left":[0.2,-0.1,0.4],"right":[0,0,0]},"frame_id":42,"captured_at":1793920000.0}
```

`wrist_rpy`는 손별 `[roll, pitch, yaw]` 라디안 값입니다. 생략하면 기본 방향(0, 0, 0)으로 처리해 기존 송신기와 호환됩니다. 포함할 때에는 양손의 유한 숫자 세 개를 모두 제공해야 하며, 잘못된 값이 있으면 해당 프레임 전체를 무시합니다.

`frame_id`는 실행 중 증가하는 프레임 번호, `captured_at`은 촬영 시각(Unix 초)입니다. 두 항목은 선택 사항이며 이전 `hands` 전용 형식도 사용할 수 있습니다. 끊김은 마지막 유효 프레임의 로컬 monotonic 수신 시각으로 판정합니다. 메타데이터는 현재 관절 제어나 통신 지연 보정에 사용하지 않습니다.

## 개발 검증

저장소 루트에서 기본 회귀 검사를 실행합니다. 카메라·MediaPipe·ROS 없이 실행하는 검사와, ROS 환경에서 선택적으로 실행하는 통합 검사가 구분되어 있습니다.

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/start_all.sh scripts/start_ubuntu.sh

source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select hand_motion_rviz
HAND_RVIZ_ROS_TESTS=1 python3 -m unittest discover -s tests -v
```

ROS 통합 검사는 가짜 TCP 프레임으로 36관절과 손목 회전 출력, 지연·연결 종료 시 열린 자세, 재접속과 종료를 확인합니다. 빌드된 전체 launch 검사에서는 합성 손 좌표에서 양손 palm TF까지 회전 전달과 좌우 배치를 확인합니다. 실제 Ubuntu 카메라 추적 품질과 RViz 화면은 데스크톱에서 별도로 확인해야 합니다.

## 주요 파일

- `src/hand_motion_rviz/tracker/`: 카메라 추적, 자동 재접속, 트래커 의존성
- `src/hand_motion_rviz/hand_motion_rviz/`: ROS 브리지, JSONL 입력 검증·끊김 처리
- `src/hand_motion_rviz/launch/hand_rviz.launch.py`: ROS/RViz 실행
- `src/hand_motion_rviz/urdf/hand.urdf.xacro`: 양손 모델
- `src/hand_motion_rviz/config/hand.rviz`: RViz 표시 설정
- `scripts/start_all.sh`: Ubuntu 로컬 카메라·ROS/RViz 함께 실행
- `scripts/start_ubuntu.sh`: Ubuntu 빌드·ROS/RViz만 실행
- `scripts/start_remote.sh`: 기존 Mac → SSH → Ubuntu 실행 흐름

## macOS 및 원격 실행

트래커의 `--backend auto`는 macOS에서 AVFoundation을 선택합니다. 이전 `mac/hand_tracker.py` 경로는 호환 진입점으로 유지합니다. 원격 브리지에 연결하려면 `--host`와 `--port`를 지정하세요. 신뢰할 수 있는 LAN 또는 SSH 터널에서 사용하고, SSH 터널을 사용하는 경우 트래커의 호스트는 터널의 로컬 주소로 지정합니다. Ubuntu 한 대에서 실행할 때는 이 설정이 필요하지 않습니다.

기존 SSH 자동 실행 흐름은 `scripts/start_remote.sh`로 분리했습니다. 사용할 때는 `HAND_RVIZ_REMOTE=user@ubuntu-host`와 `HAND_RVIZ_REMOTE_WORKSPACE=/path/to/hand-motion-rviz`를 실제 원격 환경에 맞게 지정하세요.
