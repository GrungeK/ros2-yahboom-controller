from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # 1. Узел моторов, IMU и камеры (серво)
        Node(
            package='yahboom_driver',
            executable='base_node',
            name='rosmaster_base',
            output='screen'
        ),
        # 2. Узел USB-камеры
        Node(
            package='yahboom_driver',
            executable='camera_node',
            name='rosmaster_camera',
            output='screen'
        ),
        # 3. Веб-стриминг видео
        Node(
            package='web_video_server',
            executable='web_video_server',
            name='video_server',
            output='screen',
            parameters=[{'port': 8080}]
        ),
        # 4. Драйвер джойстика 8BitDo
        Node(
            package='joy',
            executable='joy_node',
            name='joystick',
            output='screen'
        ),
        # 5. НАШ узел: джойстик → /cmd_vel (вместо teleop_twist_joy)
        Node(
            package='yahboom_driver',
            executable='joy_to_cmdvel',
            name='joy_to_cmdvel',
            output='screen',
            parameters=[{
                'axis_linear': 1,     # Ось Y левого стика = движение вперёд/назад
                'axis_angular': 0,    # Ось X левого стика = поворот
                'max_linear': 0.5,
                'max_angular': 1.0,
                'deadzone': 0.1,
            }]
        )
    ])
