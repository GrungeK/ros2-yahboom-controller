#!/usr/bin/env python3
"""
Узел для фото и видеозаписи.
Принимает команды через топик /media/command и сохраняет файлы.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
import os
import time
from datetime import datetime

class MediaNode(Node):
    def __init__(self):
        super().__init__('media_node')
        
        # Папки для сохранения
        self.photo_dir = '/home/grunge/ros2_ws/media/photos'
        self.video_dir = '/home/grunge/ros2_ws/media/videos'
        
        os.makedirs(self.photo_dir, exist_ok=True)
        os.makedirs(self.video_dir, exist_ok=True)
        
        self.bridge = CvBridge()
        
        # Подписчики
        self.image_sub = self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        self.command_sub = self.create_subscription(String, '/media/command', self.command_callback, 10)
        
        # Издатель статуса
        self.status_pub = self.create_publisher(String, '/media/status', 10)
        
        # Состояние
        self.latest_frame = None
        self.recording = False
        self.video_writer = None
        self.video_start_time = None
        self.frame_count = 0
        
        # FPS видео (15 кадров/сек — оптимально для Pi)
        self.video_fps = 15
        self.video_frame_interval = 1.0 / self.video_fps
        self.last_video_frame_time = 0
        
        self.get_logger().info('📷 Media Node запущен!')
        self.get_logger().info('📸 Кнопка A (0) - фото')
        self.get_logger().info('🎥 Кнопка B (1) - старт/стоп видео')
        self.publish_status()

    def image_callback(self, msg: Image):
        """Сохраняем последний кадр для фото и записи"""
        try:
            self.latest_frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            
            # Если идёт запись — добавляем кадр
            if self.recording and self.video_writer is not None:
                current_time = time.time()
                if current_time - self.last_video_frame_time >= self.video_frame_interval:
                    self.video_writer.write(self.latest_frame)
                    self.frame_count += 1
                    self.last_video_frame_time = current_time
        except Exception as e:
            self.get_logger().error(f'Ошибка кадра: {e}')

    def command_callback(self, msg: String):
        """Обработка команд: 'photo' или 'toggle_video'"""
        command = msg.data.strip().lower()
        
        if command == 'photo':
            self.take_photo()
        elif command == 'toggle_video':
            self.toggle_video()

    def take_photo(self):
        """Сделать фото"""
        if self.latest_frame is None:
            self.get_logger().warning('Нет кадра для фото!')
            return
        
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f'photo_{timestamp}.jpg'
        filepath = os.path.join(self.photo_dir, filename)
        
        # Добавляем штамп времени на фото
        frame_with_stamp = self.latest_frame.copy()
        cv2.putText(frame_with_stamp, timestamp, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imwrite(filepath, frame_with_stamp)
        self.get_logger().info(f'📸 Фото сохранено: {filename}')
        self.publish_status()

    def toggle_video(self):
        """Начать или остановить запись видео"""
        if self.recording:
            self.stop_video()
        else:
            self.start_video()

    def start_video(self):
        """Начать запись видео"""
        if self.latest_frame is None:
            self.get_logger().warning('Нет кадра для начала записи!')
            return
        
        h, w = self.latest_frame.shape[:2]
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f'video_{timestamp}.avi'
        filepath = os.path.join(self.video_dir, filename)
        
        # MJPG кодек — самый быстрый для Raspberry Pi
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        self.video_writer = cv2.VideoWriter(filepath, fourcc, self.video_fps, (w, h))
        
        if not self.video_writer.isOpened():
            self.get_logger().error('Не удалось открыть VideoWriter!')
            self.video_writer = None
            return
        
        self.recording = True
        self.video_start_time = time.time()
        self.frame_count = 0
        self.last_video_frame_time = time.time()
        
        self.get_logger().info(f'🎥 Запись начата: {filename}')
        self.publish_status()

    def stop_video(self):
        """Остановить запись видео"""
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
        
        duration = time.time() - self.video_start_time if self.video_start_time else 0
        self.get_logger().info(f'⏹️ Запись остановлена. Длительность: {duration:.1f}с, Кадров: {self.frame_count}')
        
        self.recording = False
        self.video_start_time = None
        self.frame_count = 0
        self.publish_status()

    def publish_status(self):
        """Публикуем статус для веб-сервера"""
        msg = String()
        if self.recording:
            duration = time.time() - self.video_start_time if self.video_start_time else 0
            msg.data = f'RECORDING|{duration:.1f}s|{self.frame_count} frames'
        else:
            photos = len([f for f in os.listdir(self.photo_dir) if f.endswith('.jpg')])
            videos = len([f for f in os.listdir(self.video_dir) if f.endswith('.avi')])
            msg.data = f'IDLE|{photos} photos|{videos} videos'
        self.status_pub.publish(msg)

    def destroy_node(self):
        """Корректное завершение"""
        if self.recording:
            self.stop_video()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = MediaNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
