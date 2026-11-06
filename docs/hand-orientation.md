# 손목 방향과 기본 화면 배치

기존 모델은 손바닥을 고정 관절로 연결하고 curl만 받아 손 전체를 회전할 수
없었다. 현재는 손마다 yaw(Z) → pitch(Y) → roll(X) 연속 관절을 둔다.
회전은 `Rz(yaw) Ry(pitch) Rx(roll)`이며 TCP에서는 `[roll, pitch, yaw]`로 보낸다.
손가락 30관절 뒤에 왼손 yaw/pitch/roll, 오른손 yaw/pitch/roll을 발행한다.

모델 로컬 +X는 손가락 방향, 왼손의 +Y는 엄지 방향이다. 손가락이 굽혀지는
쪽인 -Z가 손바닥이다. 기본 RViz 시점은 -Z 쪽에서 보며, 좌우 mount를
왼손 Y=-0.13m, 오른손 Y=+0.13m로 교환했다. 기본 시점에서 왼손은 화면
왼쪽, 오른손은 화면 오른쪽이며 엄지는 안쪽을 향한다. 추적 손 라벨은
바꾸지 않는다. RViz 시점을 돌리면 화면상의 좌우는 바뀔 수 있다.

방향 추정에는 손목(0)→중지 MCP(9)를 X축으로, 소지 MCP(17)→검지 MCP(5)를
횡축 후보로 사용하고 직교화한다. 오른손 횡축 후보는 부호를 반전해 양손을
동일한 오른손 좌표계로 만든다. 미러링된 카메라의 오른쪽→모델 +Y,
아래쪽→모델 -X, 깊이→모델 +Z로 변환한다. 이 축 정의에서는 양손 모두
손가락이 위로, 손바닥이 카메라로 향하면 기본 회전이 된다.

가능하면 MediaPipe world landmarks를 사용한다. normalized landmarks를
사용할 때에는 이미지 종횡비를 보정한다. 입력 영상의 미러링은 기존 흐름을
유지한다. 사용 중인 legacy MediaPipe Hands API의 좌표·handedness 설명은
[공식 문서](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/hands.md)를 따른다.

퇴화하거나 유효하지 않은 점으로는 회전을 만들지 않고 해당 손의 기본
방향을 보낸다. 손이 사라지거나 연결이 끊기면 열린 자세와 기본 방향으로
돌아간다. 이는 카메라의 추정 방향이며 정밀한 손목 관절 측정은 아니다.

회전 행렬 합성, 양손 방향, Euler 특이점, 종횡비, 입력 검증, ROS 발행,
URDF 관절 구조와 기본 화면 투영은 회귀 검사로 확인한다.

전체 launch에서는 Xacro 결과를 `ParameterValue(..., value_type=str)`로
명시해 `robot_description`이 YAML로 자동 해석되지 않게 한다. XML 주석에
콜론 등이 포함돼도 모델 로딩이 깨지지 않아야 한다. 설치된 launch에서
합성 좌표→TCP→관절→robot_state_publisher→양손 palm TF까지 확인하는
`test_ros_model_launch.py`로 이 경로를 검증한다.

## 외형 메시

손바닥·손가락 외형은 저장소의 생성기로 만든 로컬 STL이며 Xacro의 visual에
적용한다. 관절 origin/axis/limit과 링크 이름은 외형 개선 전과 동일하다.
메시는 package://hand_motion_rviz/meshes/로 참조하고 setup.py에서 함께 설치한다.
따라서 외형 변경은 기존 curl/RPY 전달과 TF 구조에 영향을 주지 않는다.
