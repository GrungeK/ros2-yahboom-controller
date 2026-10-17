#!/usr/bin/env python3
"""
Оптимизированный узел YOLOv8 для Raspberry Pi.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import String, Bool
from cv_bridge import CvBridge
import cv2
import numpy as np
import onnxruntime as ort
import time
import os

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush"
]

class YoloNode(Node):
    def __init__(self):
        super().__init__('yolo_node')
        
        self.declare_parameter('model_path', '/home/grunge/ros2_ws/src/yahboom_driver/models/yolov8n.onnx')
        self.declare_parameter('confidence_threshold', 0.45)
        self.declare_parameter('nms_threshold', 0.4)
        self.declare_parameter('input_size', 416)
        self.declare_parameter('skip_frames', 2)
        
        model_path = self.get_parameter('model_path').value
        self.confidence = self.get_parameter('confidence_threshold').value
        self.nms_threshold = self.get_parameter('nms_threshold').value
        self.input_size = self.get_parameter('input_size').value
        self.skip_frames = self.get_parameter('skip_frames').value
        
        self.yolo_enabled = False
        
        if not os.path.exists(model_path):
            self.get_logger().error(f'Модель не найдена: {model_path}')
            return
            
        self.get_logger().info(f'Загрузка модели YOLOv8 (input_size={self.input_size})...')
        try:
            session_options = ort.SessionOptions()
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            session_options.intra_op_num_threads = 2
            
            self.session = ort.InferenceSession(model_path, session_options, providers=['CPUExecutionProvider'])
            self.input_name = self.session.get_inputs()[0].name
            self.get_logger().info('✅ Модель загружена!')
        except Exception as e:
            self.get_logger().error(f'Ошибка загрузки модели: {e}')
            return
        
        self.bridge = CvBridge()
        
        self.image_sub = self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        self.toggle_sub = self.create_subscription(Bool, '/yolo_toggle', self.toggle_callback, 10)
        self.detected_compressed_pub = self.create_publisher(CompressedImage, '/camera/detected/compressed', 10)
        self.detections_pub = self.create_publisher(String, '/detections', 10)
        self.status_pub = self.create_publisher(String, '/yolo_status', 10)
        
        self.frame_count = 0
        self.processed_count = 0
        self.last_time = time.time()
        self.frame_counter = 0
        
        self.get_logger().info('🎯 YOLO Node запущен! (ВЫКЛ по умолчанию)')
        self.get_logger().info('🎮 Нажмите START на джойстике для включения')
        self.publish_status()

    def toggle_callback(self, msg: Bool):
        self.yolo_enabled = not self.yolo_enabled
        status = "ВКЛ" if self.yolo_enabled else "ВЫКЛ"
        self.get_logger().info(f'🔄 YOLO: {status}')
        self.publish_status()

    def publish_status(self):
        msg = String()
        msg.data = "ON" if self.yolo_enabled else "OFF"
        self.status_pub.publish(msg)

    def preprocess(self, frame):
        h, w = frame.shape[:2]
        scale = self.input_size / max(h, w)
        new_h, new_w = int(h * scale), int(w * scale)
        resized = cv2.resize(frame, (new_w, new_h))
        padded = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
        y_offset = (self.input_size - new_h) // 2
        x_offset = (self.input_size - new_w) // 2
        padded[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        blob = cv2.dnn.blobFromImage(padded, 1/255.0, (self.input_size, self.input_size), swapRB=True)
        return blob, scale, x_offset, y_offset

    def postprocess(self, outputs, frame_shape, scale, x_offset, y_offset):
        outputs = np.array(outputs[0])
        outputs = np.transpose(outputs, (0, 2, 1))
        boxes, scores, class_ids = [], [], []
        for output in outputs[0]:
            box = output[:4]
            class_scores = output[4:]
            max_score = np.max(class_scores)
            if max_score < self.confidence: continue
            class_id = np.argmax(class_scores)
            cx, cy, bw, bh = box
            x1 = int((cx - bw/2 - x_offset) / scale)
            y1 = int((cy - bh/2 - y_offset) / scale)
            x2 = int((cx + bw/2 - x_offset) / scale)
            y2 = int((cy + bh/2 - y_offset) / scale)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(x2, frame_shape[1]), min(y2, frame_shape[0])
            boxes.append([x1, y1, x2, y2])
            scores.append(float(max_score))
            class_ids.append(int(class_id))
        indices = cv2.dnn.NMSBoxes(boxes, scores, self.confidence, self.nms_threshold)
        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                detections.append({'class': COCO_CLASSES[class_ids[i]], 'confidence': scores[i], 'box': boxes[i]})
        return detections

    def draw_detections(self, frame, detections, yolo_enabled):
        for det in detections:
            x1, y1, x2, y2 = det['box']
            label = f"{det['class']} {det['confidence']:.0%}"
            color = (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            (label_w, label_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - label_h - baseline), (x1 + label_w, y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - baseline), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        status_text = "YOLO: ON" if yolo_enabled else "YOLO: OFF"
        status_color = (0, 255, 0) if yolo_enabled else (0, 0, 255)
        h, w = frame.shape[:2]
        cv2.putText(frame, status_text, (w - 150, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        return frame

    def image_callback(self, msg: Image):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            if self.yolo_enabled:
                self.frame_counter += 1
                if self.frame_counter % self.skip_frames != 0: return
                blob, scale, x_offset, y_offset = self.preprocess(frame)
                outputs = self.session.run(None, {self.input_name: blob})
                detections = self.postprocess(outputs, frame.shape, scale, x_offset, y_offset)
                frame_with_detections = self.draw_detections(frame.copy(), detections, self.yolo_enabled)
                _, jpeg_buffer = cv2.imencode('.jpg', frame_with_detections, [cv2.IMWRITE_JPEG_QUALITY, 70])
                compressed_msg = CompressedImage()
                compressed_msg.header = msg.header
                compressed_msg.header.frame_id = 'camera_link'
                compressed_msg.format = 'jpeg'
                compressed_msg.data = jpeg_buffer.tobytes()
                self.detected_compressed_pub.publish(compressed_msg)
                if detections:
                    det_string = ', '.join([f"{d['class']}({d['confidence']:.0%})" for d in detections])
                    det_msg = String()
                    det_msg.data = det_string
                    self.detections_pub.publish(det_msg)
                self.processed_count += 1
                current_time = time.time()
                if current_time - self.last_time >= 1.0:
                    self.get_logger().info(f'FPS: {self.processed_count}, Обнаружено: {len(detections)}')
                    self.processed_count = 0
                    self.last_time = current_time
            else:
                _, jpeg_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                compressed_msg = CompressedImage()
                compressed_msg.header = msg.header
                compressed_msg.header.frame_id = 'camera_link'
                compressed_msg.format = 'jpeg'
                compressed_msg.data = jpeg_buffer.tobytes()
                self.detected_compressed_pub.publish(compressed_msg)
        except Exception as e:
            self.get_logger().error(f'Ошибка: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = YoloNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
