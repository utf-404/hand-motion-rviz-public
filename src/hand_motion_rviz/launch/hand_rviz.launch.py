from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    share = get_package_share_directory('hand_motion_rviz')
    model = os.path.join(share, 'urdf', 'hand.urdf.xacro')
    rviz_config = os.path.join(share, 'config', 'hand.rviz')
    robot_description = Command(['xacro ', model])
    return LaunchDescription([
        DeclareLaunchArgument('rviz', default_value='true'),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': robot_description}]),
        Node(package='hand_motion_rviz', executable='hand_bridge',
             arguments=[]),
        Node(package='rviz2', executable='rviz2', condition=IfCondition(LaunchConfiguration('rviz')),
             arguments=['-d', rviz_config], parameters=[{'robot_description': robot_description}]),
    ])
