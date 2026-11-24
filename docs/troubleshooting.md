# 문제 해결

명령은 저장소 루트에서 실행합니다. 설치와 실행 명령은 [설치 및 실행](setup-and-run.md)을 참고하세요.

## 카메라 또는 MediaPipe 오류

- Ubuntu에서는 `ls /dev/video*`로 카메라를 찾고 `HAND_RVIZ_CAMERA=1` 또는 `HAND_RVIZ_CAMERA=/dev/videoN`을 지정하세요. 장치의 읽기·쓰기 권한과 다른 앱의 카메라 사용 여부를 확인합니다.
- `mediapipe`에 `solutions`가 없으면 실행기가 가리키는 Python을 확인한 뒤 저장소의 고정 의존성으로 다시 설치하세요.

```bash
.venv/bin/python -m pip install -r src/hand_motion_rviz/tracker/requirements.txt
.venv/bin/python -c 'import mediapipe as mp; print(mp.__version__); print(mp.solutions.hands)'
```

## 브리지 연결 대기 또는 포트 충돌

`Waiting for ROS bridge`가 계속 나오면 ROS 터미널의 첫 오류를 확인하세요. 기본 포트 `18765`를 사용하는 다른 실행이 있으면 종료하거나 브리지와 트래커의 포트를 함께 변경합니다.

```bash
ss -ltn 'sport = :18765'
```

트래커는 연결이 끊겨도 미리보기를 유지하며 재접속합니다. 전송에 실패한 프레임은 버리고 재접속 후 최신 자세를 보냅니다. 미리보기의 `Connected`는 현재 프레임의 TCP 전송 성공을 뜻합니다.

브리지는 유효한 프레임이 기본 1초 동안 없으면 양손을 열린 자세로 되돌리고 무응답 연결을 해제합니다. 연결 종료를 감지하면 즉시 열린 자세로 돌아갑니다.

끊김 판정 시간과 재시도 간격은 브리지와 트래커를 따로 실행할 때 지정합니다.

```bash
# 브리지 터미널
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch hand_motion_rviz hand_rviz.launch.py stale_timeout:=1.5

# 트래커 터미널
.venv/bin/python src/hand_motion_rviz/tracker/hand_tracker.py \
  --retry-interval 2 --network-timeout 0.2
```

`--network-timeout`은 연결과 전송 각각에 적용됩니다. 큰 값은 미리보기와 종료 키의 반응을 늦출 수 있습니다. `--host`의 호스트명은 카메라 시작 전에 한 번 IPv4로 해석됩니다. 호스트의 IP가 바뀌면 트래커를 다시 시작하세요.

## ROS 토픽과 RViz2 확인

ROS 2 Humble 환경을 불러온 터미널에서 확인합니다.

```bash
source /opt/ros/humble/setup.bash
ros2 node list
ros2 topic hz /joint_states
ros2 topic echo --once /joint_states
ros2 topic info /robot_description --verbose
```

RViz2 실행에서는 `/hand_bridge`, `/robot_state_publisher`, `/rviz`가 보이고 `/joint_states`에 손가락 30개와 손목 6개, 총 36관절이 약 30Hz로 발행됩니다. 손 모델이 안 보이면 Ubuntu 데스크톱에서 RViz2를 실행하고 Displays의 `Robot Hands`와 Fixed Frame `hands_base`를 확인하세요.

`No such file or directory: 'xacro'`가 나오면 `sudo apt install ros-humble-xacro`로 설치한 뒤 ROS 환경을 다시 불러옵니다. RViz2 창을 끈 상태에서도 손 모델 변환에는 `xacro`가 필요합니다.

## Isaac Sim 실행 오류

- `Isaac Sim python.sh not found`가 나오면 `HAND_ISAAC_PYTHON`에 설치한 `python.sh` 경로를 지정하세요. `bundled ROS 2 ... runtime is missing`이면 선택한 `ROS_DISTRO`용 라이브러리가 해당 설치본에 포함되는지 확인합니다.
- `xacro not found`가 나오면 [설치 및 실행](setup-and-run.md)에 따라 `xacro`를 설치하거나 `HAND_ISAAC_XACRO`에 실행 파일을 지정하세요.
- GUI 창을 열려면 Ubuntu 데스크톱의 터미널에서 실행하세요. `No Isaac Sim viewport is available` 오류가 나오면 `printenv DISPLAY`로 현재 GUI 세션을 확인합니다. 화면 없이 점검할 때는 아래 명령을 사용할 수 있습니다.

```bash
./scripts/start_isaacsim.sh --demo --headless-seconds 8
```

`Received and applied 36 joint targets`가 나오면 36개 관절 목표값을 적용한 상태입니다. 헤드리스 실행이 `No complete hand pose received`로 끝나거나 실시간 모드의 손이 움직이지 않으면 실행기에 표시된 토픽과 발행 토픽을 비교하세요. 실시간 기본값은 `/joint_states`, 데모 기본값은 `/hand_motion_demo/joint_states`입니다. 실시간 구독은 발행기와 `ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION` 설정을 맞추고, 토픽을 바꿨다면 `--topic`을 사용합니다.

## 종료 시 ROS 컨텍스트 오류

이전에는 로컬 실행기에 SIGINT를 보낼 때 `ExternalShutdownException`, invalid context 오류 또는 정리 중 `KeyboardInterrupt`가 표시될 수 있었습니다. ROS 기본 신호 처리기가 컨텍스트를 비동기로 종료하면서 진행 중인 publish/wait 또는 rosout 로그가 종료된 컨텍스트에 접근했습니다. ROS launch가 신호를 다시 전달하면 소켓·노드 정리가 중단될 수도 있었습니다.

현재 브리지는 rclpy 기본 신호 처리를 비활성화하고 Python 주 스레드에서 SIGINT/SIGTERM을 처리합니다. 정리 중에는 추가 신호를 무시하고 TCP 수신기, 노드, ROS 컨텍스트 순으로 종료합니다. 상태 로그는 컨텍스트가 유효할 때 발행합니다.

아래 ROS 통합 검사는 트래커가 연결된 상태에서 두 신호 각각의 종료 코드와 traceback·invalid rosout 오류가 없는지 확인합니다.

```bash
source /opt/ros/humble/setup.bash
HAND_RVIZ_ROS_TESTS=1 python3 -m unittest discover -s tests -p test_ros_bridge.py -v
```

로컬 실행기와 ROS launch에 합성 TCP 송신기를 연결한 검사에서도 브리지와 `robot_state_publisher`의 종료 및 포트 해제를 확인했습니다.
