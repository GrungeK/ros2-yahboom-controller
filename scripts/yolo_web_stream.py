#!/usr/bin/env python3
"""
Сверхбыстрый веб-стример для YOLO детекции.
Берёт готовые JPEG-байты из ROS и отдаёт в браузер без перекодирования.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time

latest_jpeg_bytes = None

class YoloStreamerNode(Node):
    def __init__(self):
        super().__init__('yolo_web_streamer')
        self.get_logger().info('Подключение к топику /camera/detected/compressed...')
        self.sub = self.create_subscription(
            CompressedImage, 
            '/camera/detected/compressed', 
            self.callback, 
            10
        )

    def callback(self, msg):
        global latest_jpeg_bytes
        latest_jpeg_bytes = msg.data

class VideoHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    if latest_jpeg_bytes is not None:
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                        self.wfile.write(latest_jpeg_bytes)
                        self.wfile.write(b'\r\n')
                    time.sleep(0.1)
            except Exception:
                pass
        else:
            self.send_error(404)

def main():
    rclpy.init()
    node = YoloStreamerNode()
    
    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()
    
    server = HTTPServer(('0.0.0.0', 8000), VideoHandler)
    print("=" * 60)
    print("🎥 YOLO ВИДЕОПОТОК ЗАПУЩЕН!")
    print("🌐 Откройте в браузере: http://192.168.1.131:8000/stream")
    print("=" * 60)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановка стримера...")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
