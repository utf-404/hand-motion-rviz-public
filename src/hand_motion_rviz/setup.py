from glob import glob
from setuptools import setup

package_name = 'hand_motion_rviz'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'LICENSE']),
        ('share/' + package_name + '/urdf', ['urdf/hand.urdf.xacro']),
        ('share/' + package_name + '/meshes', glob('meshes/*.stl')),
        ('share/' + package_name + '/launch', ['launch/hand_rviz.launch.py']),
        ('share/' + package_name + '/config', ['config/hand.rviz']),
        ('share/' + package_name + '/tracker', ['tracker/hand_tracker.py',
                                              'tracker/hand_orientation.py',
                                              'tracker/tracker_connection.py',
                                              'tracker/requirements.txt']),
        ('share/' + package_name + '/mac', ['mac/hand_tracker.py', 'mac/requirements.txt']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='utf-404',
    description='Mirror two webcam-tracked hands in RViz.',
    license='Apache-2.0',
    url='https://github.com/utf-404/hand-motion-rviz-public',
    project_urls={'Issues': 'https://github.com/utf-404/hand-motion-rviz-public/issues'},
    entry_points={'console_scripts': ['hand_bridge = hand_motion_rviz.hand_bridge:main']},
)
