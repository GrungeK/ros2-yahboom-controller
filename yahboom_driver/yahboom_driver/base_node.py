#!/usr/bin/env python3
"""
Base Node for Yahboom Rosmaster with Bluetooth Joystick Support.
Controls motors via /cmd_vel and camera servos via Right Stick.
ASSUMPTION: Right Stick uses Axes 2 (Pan) and 3 (Tilt).
If your camera moves incorrectly, check which axes change in 'ros2 topic echo /joy'
when moving the RIGHT stick and update indices below.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, Joy
import math
import time
from Rosmaster_Lib import Rosmaster

class RosmasterBaseNode(Node):
    def __init__(self):
        super().__init__('rosmaster_base_node')
        
        # Инициализация библиотеки Yahboom для связи с железом робота
        try:
            self.bot = Rosmaster(car_type=1, com="/dev/myserial")
            self.bot.create_receive_threading() # Запуск потока чтения данных датчиков
            self.bot.set_auto_report_state(True)
        except Exception as e:
            self.get_logger().error(f"Ошибка подключения к Rosmaster: {e}")
            return

        # Подписка на команды движения от джойстика
        self.cmd_vel_sub = self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        
        # Подписка на данные джойстика для управления камерой
        self.joy_sub = self.create_subscription(Joy, '/joy', self.joy_callback, 10)
        
        # Издатели телеметрии (позиция, IMU)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.imu_pub = self.create_publisher(Imu, '/imu/data', 10)
        
        # Параметры движения
        self.max_speed = 1.0
        self.motor_smooth = 0.15 # Коэффициент сглаживания рывков
        
        # Текущие значения скоростей
        self.linear_x = 0.0
        self.angular_z = 0.0
        self.current_linear = 0.0
        self.current_angular = 0.0
        
        # Позиция робота в пространстве (X, Y, Theta)
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.last_time = self.get_clock().now()
        
        # Параметры сервоприводов камеры
        self.servo_pan = 90   # Текущий угол поворота камеры (горизонтально)
        self.servo_tilt = 90  # Текущий угол наклона камеры (вертикально)
        self.servo_step = 3   # Шаг изменения угла за один кадр (чем больше, тем быстрее крутится)
        self.servo_deadzone = 0.15 # Мертвая зона для стика камеры
        
        # Калибровка гироскопа при старте
        self.get_logger().info('Калибровка гироскопа (2 сек)... Не двигайте робота!')
        time.sleep(2)
        samples = []
        for _ in range(20):
            try:
                gyro_data = self.bot.get_gyroscope_data()
                if gyro_data and len(gyro_data) >= 3:
                    samples.append(gyro_data[2]) # Z-axis (Yaw)
            except:
                pass
            time.sleep(0.1)
        
        self.gyro_offset = sum(samples) / len(samples) if samples else 0.0
        self.get_logger().info(f'Смещение гироскопа: {self.gyro_offset:.4f}')
        
        # Установка начальных позиций сервоприводов (центр)
        self.bot.set_pwm_servo(1, int(self.servo_pan))
        self.bot.set_pwm_servo(2, int(self.servo_tilt))
        
        # Таймер основного цикла работы (50 Гц)
        self.timer = self.create_timer(0.02, self.update_loop)
        self.get_logger().info('🚀 Base Node запущен!')

    def cmd_vel_callback(self, msg: Twist):
        """Получение целевой скорости от узла joy_to_cmdvel"""
        self.linear_x = msg.linear.x
        self.angular_z = msg.angular.z

    def joy_callback(self, msg: Joy):
        """Обработка данных джойстика для управления КАМЕРОЙ"""
        # Проверяем наличие осей
        if len(msg.axes) < 4:
            return
            
        try:
            # === НАСТРОЙКА ОСЕЙ КАМЕРЫ ===
            # Для 8BitDo BT обычно:
            # Ось 2 = Правый стик X (Pan - Влево/Вправо)
            # Ось 3 = Правый стик Y (Tilt - Вверх/Вниз)
            
            right_x = msg.axes[2] # Pan
            right_y = msg.axes[3] # Tilt
            
            # Применяем мертвую зону
            if abs(right_x) < self.servo_deadzone: right_x = 0.0
            if abs(right_y) < self.servo_deadzone: right_y = 0.0
            
            # Если стик тронут, обновляем углы сервоприводов
            if right_x != 0.0 or right_y != 0.0:
                # Вычисляем новые углы
                # Знак "+" или "-" зависит от того, куда смотрит камера при движении стика.
                # Если камера крутится наоборот, поменяйте знак напротив int(...)
                new_pan = self.servo_pan + int(right_x * self.servo_step)
                new_tilt = self.servo_tilt + int(right_y * self.servo_step)
                
                # Ограничиваем углы диапазоном 0-180 градусов
                self.servo_pan = max(0, min(180, new_pan))
                self.servo_tilt = max(0, min(180, new_tilt))
                
                # Отправляем команды на физические сервоприводы
                # Channel 1 = Pan, Channel 2 = Tilt
                self.bot.set_pwm_servo(1, int(self.servo_pan))
                self.bot.set_pwm_servo(2, int(self.servo_tilt))
        except Exception as e:
            # Игнорируем ошибки, чтобы не ронять весь узел из-за джойстика
            pass

    def update_loop(self):
        """Основной цикл: плавное движение моторов и чтение датчиков"""
        current_time = self.get_clock().now()
        dt = (current_time - self.last_time).nanoseconds / 1e9
        self.last_time = current_time
        
        # Защита от больших скачков времени
        if dt <= 0 or dt > 1.0:
            dt = 0.02

        try:
            # 1. Плавное изменение скоростей (Inertia smoothing)
            self.current_linear += (self.linear_x - self.current_linear) * self.motor_smooth
            self.current_angular += (self.angular_z - self.current_angular) * self.motor_smooth
            
            # Полная остановка при малых значениях
            if abs(self.current_linear) < 0.01: self.current_linear = 0.0
            if abs(self.current_angular) < 0.01: self.current_angular = 0.0
            
            # 2. Расчет мощностей для левого и правого мотора (Diff Drive)
            left_motor = self.current_linear - self.current_angular
            right_motor = self.current_linear + self.current_angular
            
            # Нормализация диапазона [-1, 1]
            max_val = max(abs(left_motor), abs(right_motor))
            if max_val > 1.0:
                scale = 1.0 / max_val
                left_motor *= scale
                right_motor *= scale
            
            # Инверсия направлений (подгонка под конкретную сборку Yahboom)
            invert_left = True  
            invert_right = False 
            
            if invert_left: left_motor = -left_motor
            if invert_right: right_motor = -right_motor
            
            # Преобразование в PWM (-100..100)
            pwm_left = int(max(-100, min(100, left_motor * 100)))
            pwm_right = int(max(-100, min(100, right_motor * 100)))
            
            # Отправка команд моторам
            self.bot.set_motor(pwm_left, pwm_right, 0, 0)
            
            # 3. Чтение данных с датчиков (IMU/Gyro) для одометрии
            gyro_data = self.bot.get_gyroscope_data()
            accel_data = self.bot.get_accelerometer_data()
            
            raw_gyro_z = 0.0
            if gyro_data and len(gyro_data) >= 3:
                raw_gyro_z = float(gyro_data[2])
            
            corrected_gyro_z = raw_gyro_z - self.gyro_offset
            
            # Обновление ориентации (Theta)
            self.theta += corrected_gyro_z * dt
            self.theta = math.atan2(math.sin(self.theta), math.cos(self.theta))
            
            # Обновление позиции (X, Y)
            self.x += self.current_linear * math.cos(self.theta) * dt
            self.y += self.current_linear * math.sin(self.theta) * dt
            
            # Публикация Odom (для навигации и записи трека)
            odom = Odometry()
            odom.header.stamp = current_time.to_msg()
            odom.header.frame_id = 'odom'
            odom.child_frame_id = 'base_link'
            odom.pose.pose.position.x = self.x
            odom.pose.pose.position.y = self.y
            q_z = math.sin(self.theta / 2.0)
            q_w = math.cos(self.theta / 2.0)
            odom.pose.pose.orientation.z = q_z
            odom.pose.pose.orientation.w = q_w
            odom.twist.twist.linear.x = self.current_linear
            odom.twist.twist.angular.z = corrected_gyro_z
            self.odom_pub.publish(odom)
            
            # Публикация IMU (угловые скорости и ускорения)
            imu_msg = Imu()
            imu_msg.header.stamp = current_time.to_msg()
            imu_msg.header.frame_id = 'base_link'
            if gyro_data and len(gyro_data) >= 3:
                imu_msg.angular_velocity.x = float(gyro_data[0])
                imu_msg.angular_velocity.y = float(gyro_data[1])
                imu_msg.angular_velocity.z = corrected_gyro_z
            if accel_data and len(accel_data) >= 3:
                imu_msg.linear_acceleration.x = float(accel_data[0])
                imu_msg.linear_acceleration.y = float(accel_data[1])
                imu_msg.linear_acceleration.z = float(accel_data[2])
            self.imu_pub.publish(imu_msg)
            
        except Exception as e:
            self.get_logger().error(f'Ошибка в цикле обновления: {e}')

    def destroy_node(self):
        """Корректное завершение работы"""
        self.get_logger().info('Остановка узлов...')
        try:
            self.bot.set_motor(0, 0, 0, 0) # Стоп моторы
            self.bot.set_pwm_servo(1, 90)  # Камера в центр
            self.bot.set_pwm_servo(2, 90)
        except:
            pass
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = RosmasterBaseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
