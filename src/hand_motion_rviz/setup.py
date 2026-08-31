from setuptools import setup

package_name = 'hand_motion_rviz'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/urdf', ['urdf/hand.urdf.xacro']),
        ('share/' + package_name + '/launch', ['launch/hand_rviz.launch.py']),
        ('share/' + package_name + '/config', ['config/hand.rviz']),
        ('share/' + package_name + '/mac', ['mac/hand_tracker.py', 'mac/requirements.txt']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='user',
    maintainer_email='138092660+utf-404@users.noreply.github.com',
    description='Mirror a webcam-tracked hand in RViz.',
    license='Apache-2.0',
    entry_points={'console_scripts': ['hand_bridge = hand_motion_rviz.hand_bridge:main']},
)
