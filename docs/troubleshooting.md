# 종료 시 ROS 컨텍스트 오류

## 증상과 원인

로컬 실행기의 프로세스 그룹에 SIGINT를 보내 종료할 때 브리지에
`ExternalShutdownException`, invalid context 오류 또는 정리 중
`KeyboardInterrupt`가 표시될 수 있었다.

ROS의 기본 신호 처리기가 비동기로 컨텍스트를 종료하면 실행 중인
publish/wait와 종료 시 rosout 로그가 이미 종료된 컨텍스트에 접근한다.
그룹 신호를 받은 ROS launch가 자식에게 신호를 다시 전달하는 경우에는
두 번째 신호가 소켓·노드 정리를 중단할 수도 있다.

## 현재 처리

브리지는 rclpy 기본 신호 처리를 비활성화하고 Python 주 스레드에서
SIGINT/SIGTERM을 받아 정상 정리 경로로 들어간다. 정리 중에는 추가
신호를 무시하고 TCP 수신기를 정지한 후 노드와 ROS 컨텍스트를 종료한다.
상태 로그는 컨텍스트가 유효할 때만 발행한다.

## 검증

ROS 통합 검사는 연결된 트래커가 있는 상태에서 SIGINT와 SIGTERM 각각에
대해 정상 종료 코드와 traceback/invalid rosout 오류가 없음을 확인한다.

```bash
source /opt/ros/humble/setup.bash
HAND_RVIZ_ROS_TESTS=1 python3 -m unittest discover -s tests -p test_ros_bridge.py -v
```

실제 로컬 launcher와 ROS launch를 연결하고 카메라 대신 합성 TCP 송신기를
사용한 검사에서도 브리지·robot_state_publisher의 정상 종료와 포트 해제를
확인했다. 카메라 추적 품질과 RViz 화면 확인은 별도다.
