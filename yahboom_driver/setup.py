from setuptools import setup
import os
from glob import glob

package_name = 'yahboom_driver'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'models'), glob('models/*.onnx')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='grunge',
    maintainer_email='grunge@example.com',
    description='Yahboom Rosmaster ROS 2 Driver',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'base_node = yahboom_driver.base_node:main',
            'camera_node = yahboom_driver.camera_node:main',
            'joy_to_cmdvel = yahboom_driver.joy_to_cmdvel:main',
            'yolo_node = yahboom_driver.yolo_node:main',
            'media_node = yahboom_driver.media_node:main',  # <-- ДОБАВЛЕНО
        ],
    },
)
