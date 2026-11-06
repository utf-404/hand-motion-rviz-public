from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    share = get_package_share_directory('hand_motion_rviz')
    model = os.path.join(share, 'urdf', 'hand.urdf.xacro')
    rviz_config = os.path.join(share, 'config', 'hand.rviz')
    robot_description = ParameterValue(Command(['xacro ', model]), value_type=str)
    return LaunchDescription([
        DeclareLaunchArgument('rviz', default_value='true',
                              description='Start RViz on the Ubuntu desktop'),
        DeclareLaunchArgument('demo', default_value='false',
                              description='Animate the hands without a camera'),
        DeclareLaunchArgument('port', default_value='18765',
                              description='TCP port used by the webcam tracker'),
        DeclareLaunchArgument('stale_timeout', default_value='1.0',
                              description='Seconds without a valid frame before opening both hands'),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': robot_description}]),
        Node(package='hand_motion_rviz', executable='hand_bridge',
             arguments=['--port', LaunchConfiguration('port'),
                        '--stale-timeout', LaunchConfiguration('stale_timeout')],
             condition=UnlessCondition(LaunchConfiguration('demo'))),
        Node(package='hand_motion_rviz', executable='hand_bridge',
             arguments=['--demo'],
             condition=IfCondition(LaunchConfiguration('demo'))),
        Node(package='rviz2', executable='rviz2', condition=IfCondition(LaunchConfiguration('rviz')),
             arguments=['-d', rviz_config]),
    ])
