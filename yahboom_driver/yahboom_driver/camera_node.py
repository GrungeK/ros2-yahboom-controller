#!/usr/bin/env python3
"""
Узел камеры с оверлеем телеметрии поверх видео.
Показывает скорость, угол, координаты и FPS прямо на кадре.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage, Imu
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
import numpy as np
import time

class CameraNode(Node):
    def __init__(self):
        super().__init__('yahboom_camera_node')
        
        # Параметры камеры
        self.declare_parameter('video_device', '/dev/video0')
        self.declare_parameter('fps', 30)
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        
        video_device = self.get_parameter('video_device').value
        fps = self.get_parameter('fps').value
        width = self.get_parameter('width').value
        height = self.get_parameter('height').value
        
        # Инициализация OpenCV
        self.cap = cv2.VideoCapture(video_device)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        if not self.cap.isOpened():
            self.get_logger().error(f'Не удалось открыть камеру {video_device}!')
            return
            
        self.get_logger().info(f'Камера открыта: {video_device} ({width}x{height} @ {fps} FPS)')
        
        self.bridge = CvBridge()
        
        # Публикаторы
        self.raw_pub = self.create_publisher(Image, 'camera/image_raw', 10)
        self.compressed_pub = self.create_publisher(CompressedImage, 'camera/image_raw/compressed', 10)
        
        # Подписчики на телеметрию
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.imu_sub = self.create_subscription(Imu, '/imu/data', self.imu_callback, 10)
        self.speed_sub = self.create_subscription(String, '/speed_mode', self.speed_callback, 10)
        
        # Данные телеметрии для оверлея
        self.odom_data = {'x': 0.0, 'y': 0.0, 'theta': 0.0, 'linear': 0.0, 'angular': 0.0}
        self.imu_data = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0}
        self.speed_mode = 'Средний'
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0
        
        # Таймер захвата
        self.timer = self.create_timer(1.0 / fps, self.capture_frame)
        
        self.get_logger().info('📷 Camera Node с оверлеем запущен!')

    def odom_callback(self, msg: Odometry):
        """Получаем данные одометрии"""
        self.odom_data['x'] = msg.pose.pose.position.x
        self.odom_data['y'] = msg.pose.pose.position.y
        self.odom_data['linear'] = msg.twist.twist.linear.x
        self.odom_data['angular'] = msg.twist.twist.angular.z
        
        # Извлекаем угол из кватерниона
        siny_cosp = 2.0 * (msg.pose.pose.orientation.w * msg.pose.pose.orientation.z + 
                           msg.pose.pose.orientation.x * msg.pose.pose.orientation.y)
        cosy_cosp = 1.0 - 2.0 * (msg.pose.pose.orientation.y * msg.pose.pose.orientation.y + 
                                  msg.pose.pose.orientation.z * msg.pose.pose.orientation.z)
        self.odom_data['theta'] = np.degrees(np.arctan2(siny_cosp, cosy_cosp))

    def imu_callback(self, msg: Imu):
        """Получаем данные IMU"""
        # Упрощённо: используем угловую скорость
        self.imu_data['yaw_rate'] = msg.angular_velocity.z

    def speed_callback(self, msg: String):
        """Получаем текущий режим скорости"""
        self.speed_mode = msg.data

    def draw_overlay(self, frame):
        """Рисуем телеметрию поверх кадра"""
        h, w = frame.shape[:2]
        
        # Полупрозрачный фон для текста (верхний левый угол)
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (280, 130), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        
        # Текст с телеметрией
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        color = (0, 255, 0)  # Зелёный
        y_pos = 30
        
        cv2.putText(frame, f"X: {self.odom_data['x']:.2f} m", (20, y_pos), font, font_scale, color, 1)
        y_pos += 20
        cv2.putText(frame, f"Y: {self.odom_data['y']:.2f} m", (20, y_pos), font, font_scale, color, 1)
        y_pos += 20
        cv2.putText(frame, f"Angle: {self.odom_data['theta']:.1f}deg", (20, y_pos), font, font_scale, color, 1)
        y_pos += 20
        cv2.putText(frame, f"Speed: {self.odom_data['linear']:.2f} m/s", (20, y_pos), font, font_scale, color, 1)
        y_pos += 20
        cv2.putText(frame, f"Mode: {self.speed_mode}", (20, y_pos), font, font_scale, (255, 255, 0), 1)
        
        # FPS в правом верхнем углу
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_fps_time >= 1.0:
            self.current_fps = self.frame_count
            self.frame_count = 0
            self.last_fps_time = current_time
        
        cv2.putText(frame, f"FPS: {self.current_fps}", (w - 100, 30), font, font_scale, (255, 0, 255), 1)
        
        # Статус подключения
        status_color = (0, 255, 0) if abs(self.odom_data['linear']) > 0.01 else (255, 255, 255)
        status_text = "MOVING" if abs(self.odom_data['linear']) > 0.01 else "IDLE"
        cv2.putText(frame, status_text, (w - 100, 50), font, font_scale, status_color, 1)
        
        return frame

    def capture_frame(self):
        ret, frame = self.cap.read()
        if ret:
            try:
                # Рисуем оверлей
                frame_with_overlay = self.draw_overlay(frame)
                
                # Публикуем сырое изображение (с оверлеем)
                raw_msg = self.bridge.cv2_to_imgmsg(frame_with_overlay, encoding='bgr8')
                raw_msg.header.stamp = self.get_clock().now().to_msg()
                raw_msg.header.frame_id = 'camera_link'
                self.raw_pub.publish(raw_msg)
                
                # Публикуем сжатое JPEG
                _, jpeg_buffer = cv2.imencode('.jpg', frame_with_overlay, [cv2.IMWRITE_JPEG_QUALITY, 80])
                compressed_msg = CompressedImage()
                compressed_msg.header.stamp = self.get_clock().now().to_msg()
                compressed_msg.header.frame_id = 'camera_link'
                compressed_msg.format = 'jpeg'
                compressed_msg.data = jpeg_buffer.tobytes()
                self.compressed_pub.publish(compressed_msg)
                
            except Exception as e:
                self.get_logger().error(f'Ошибка публикации кадра: {e}')
        else:
            self.get_logger().warning('Не удалось прочитать кадр с камеры')

    def destroy_node(self):
        if self.cap.isOpened():
            self.cap.release()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
