# Hand Motion RViz 작업 인계

## 작업 목표와 완료 조건
- Ubuntu 한 대에서 카메라 추적·ROS/RViz 실행, 통신 안정성, 손목 회전과 손바닥 초기 시점·좌우 배치를 개선한다.
- 사용자 요청에 따라 변경 이유·검증·남은 문제를 기록하고 main에 커밋·푸시한다.
- 실제 카메라/RViz 확인 완료 전에는 전체 장비 검증 완료로 처리하지 않는다.

## 완료한 작업과 변경 파일
- 기준 커밋 `cd936ee`에서 작업 시작. 코드 변경 커밋 `eae3567`을 origin/main에 푸시 완료.
- `tracker/`: 공통 카메라 추적, Linux V4L2/localhost 기본값, 카메라 번호·장치 경로, 제한시간·재접속·최신 프레임 전송, 손목 RPY 계산.
- `mac/`: 기존 경로를 공통 트래커로 위임하는 호환 진입점.
- `tracker_stream.py`, `hand_bridge.py`: 16KiB JSONL 검증, monotonic watchdog, 무응답 연결 해제, 원자적 양손 자세, 종료 정리, 36관절 발행.
- `scripts/`: 기본 로컬 실행, 시스템 ROS Python과 카메라 venv 분리, 시작 제한시간·사전검사·프로세스 그룹 정리. 기존 SSH 흐름은 start_remote.sh로 분리.
- 기본 TCP 포트를 18765로 통일. 환경변수/CLI 사용자 지정 유지.
- `hand.urdf.xacro`, `hand.rviz`: 손마다 yawZ→pitchY→rollX 관절, 양손 mount 교환, 손바닥 초기 시점.
- launch/setup/package: 실행 옵션, tracker helper 설치, 의존성 및 robot_description 문자열 타입 명시.
- README, docs/hand-orientation.md, docs/troubleshooting.md: 사용법·좌표계·종료 문제 근거 보존.
- `tests/`: 카메라 선택·송수신·모델·회전·실행기·실제 ROS/TF 회귀 검사.

## 주요 결정과 이유
- 기존 hands curl 배열과 선택적 wrist_rpy를 함께 수신하며 구형 프레임은 회전0으로 처리한다.
- 수신 컴퓨터의 monotonic 시간으로 freshness를 판단하고 잘못된 프레임은 시간을 갱신하지 않는다.
- 모델 +X 손가락, -Z 손바닥. 미러 카메라 x→+Y/y→-X/z→+Z. 회전은 RzRyRx.
- 추적 left/right 식별은 유지하고 mount만 교환한다. 기본 시점에서 왼손 화면 왼쪽, 오른손 오른쪽.
- 손 미검출·퇴화 좌표·연결 종료에는 열린 자세와 기본 방향으로 복귀한다.
- ROS 기본 비동기 신호 종료 대신 주 스레드에서 정리하고 종료 중 중복 신호를 무시한다.
- SSH 자체 재연결·카메라 재오픈은 현재 범위 밖이다.

## 실행한 검증과 결과
- 최신 코드의 ROS 포함 전체 검사 49개 통과:
  `source /opt/ros/humble/setup.bash && HAND_RVIZ_ROS_TESTS=1 python3 -m unittest discover -s tests -v`
- `colcon build --symlink-install --packages-select hand_motion_rviz` 성공.
- 합성 랜드마크→RPY→TCP→36관절→robot_state_publisher 양손 palm TF 회전·mount 위치와 정상 종료를 실제 ROS로 검증.
- 실제 로컬 launcher에 합성 송신기를 연결해 시작·종료·포트 해제 확인.
- 독립 검토에서 양손 임의 회전 2000개 복원 최대 회전행렬 오차 1.64e-15, 중요 결함 없음.
- MediaPipe/OpenCV import·Hands 모델 초기화/종료, 설치된 tracker --help, bash 구문, git diff --check 통과.
- 실제 카메라·RViz GUI는 미검증. 자동 검사 통과와 구분한다.
- 현재 개발환경 xacro와 카메라 .venv 준비됨. .venv/build/install/log는 Git 제외.

## 관련 이슈
- [#1 Ubuntu 로컬 실행·통신 안정성](https://github.com/utf-404/hand-motion-rviz/issues/1): 구현·자동 검증 완료, 해결 처리됨.
- [#2 손목 회전·손바닥 시점·좌우 배치](https://github.com/utf-404/hand-motion-rviz/issues/2): 구현·자동 검증 완료. 실제 카메라/RViz 확인 전까지 열린 상태 유지.

## 진행 중인 부분
- 없음. 코드 커밋 `eae3567` 및 origin/main 푸시 완료. 이슈 상태와 원격 반영 확인.

## 남은 작업 순서
- 사용자 요청의 코드 커밋·푸시 완료.
- 실제 Ubuntu 카메라/RViz로 회전·초기 손바닥·좌우·가림/복구 확인은 #2에 남김.

## 다음 실행 명령
```bash
./scripts/start_all.sh
```

## 막힌 사항
- 구현·커밋 차단 없음. 실제 장비 검증은 #2로 추적.
- PR 생성·병합·배포 요청 없음.

## Git 전달 결과
- 코드 커밋: `eae3567cd82cc4babddfb800c3ab32a1c05bd1c2`
- 푸시 대상: `origin/main`, 성공.
- #1 해결, #2 실제 장비 검증 대기로 열린 상태.
- Git 작성자 정보가 없어 현재 인증 계정의 이름과 GitHub noreply 주소를 이 저장소에만 설정. 전역 Git 설정은 변경하지 않음.
- 이 파일의 전달 상태 기록은 별도 문서 커밋으로 보존.
