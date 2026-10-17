#!/usr/bin/env python3
"""
Joy to CmdVel Converter for 8BitDo Ultimate 2 (BLUETOOTH MODE).
FINAL VERIFIED MAPPING BASED ON JOY_MAPPER SCRIPT:
- Photo:      A   (Index 0)
- Video:      B   (Index 1)
- YOLO Toggle:+ Start (Index 11)
- Speed Down: L4  (Index 16)
- Speed Up:   R4  (Index 17)
Movement Axes: Axis 0=Turn, Axis 1=Move
Camera Axes: Handled by base_node.py (Axis 2 & 3)
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Bool

class JoyToCmdVel(Node):
    def __init__(self):
        super().__init__('joy_to_cmdvel')
        
        # === НАСТРОЙКИ СКОРОСТИ ===
        self.speed_modes = [
            ("SLOW", 0.30),   # Медленный режим
            ("MEDIUM", 0.60), # Стандартный режим
            ("FAST", 0.85),   # Быстрый режим
            ("MAX", 1.00)     # Максимальная скорость
        ]
        self.current_speed_mode = 1
        
        # Мертвая зона стиков
        self.declare_parameter('deadzone', 0.15)
        self.deadzone = self.get_parameter('deadzone').value
        
        # === ПОДПИСЧИКИ И ИЗДАТЕЛИ ===
        self.joy_sub = self.create_subscription(Joy, '/joy', self.joy_callback, 10)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.speed_pub = self.create_publisher(String, '/speed_mode', 10)
        self.yolo_toggle_pub = self.create_publisher(Bool, '/yolo_toggle', 10)
        self.media_command_pub = self.create_publisher(String, '/media/command', 10)
        
        # === ФЛАГИ ДЛЯ ЗАЩИТЫ ОТ СПАМА ===
        # ROS отправляет данные очень часто. Эти переменные гарантируют,
        # что функция вызовется только один раз при нажатии, а не сотни раз.
        self.l4_was_pressed = False
        self.r4_was_pressed = False
        self.start_was_pressed = False
        self.a_was_pressed = False
        self.b_was_pressed = False
        
        self.get_logger().info('✅ joy_to_cmdvel запущен (Final Verified Map)!')
        self.publish_speed_mode()

    def publish_speed_mode(self):
        """Отправка имени текущего режима скорости"""
        msg = String()
        msg.data = self.speed_modes[self.current_speed_mode][0]
        self.speed_pub.publish(msg)

    def joy_callback(self, msg: Joy):
        """Главная функция обработки данных джойстика"""
        twist = Twist()
        
        # Проверка целостности данных
        # Нам нужно минимум 18 кнопок (индекс 17 - это последняя используемая)
        if len(msg.axes) < 2 or len(msg.buttons) < 18:
            return

        # ---------------------------------------------------------
        # БЛОК 1: УПРАВЛЕНИЕ ФУНКЦИЯМИ (КНОПКИ)
        # ---------------------------------------------------------

        # === ФОТО (Кнопка A -> Index 0) ===
        if msg.buttons[0] == 1:
            if not self.a_was_pressed:
                self.a_was_pressed = True
                cmd = String()
                cmd.data = 'photo'
                self.media_command_pub.publish(cmd)
                self.get_logger().info('📸 Фото отправлено')
        else:
            self.a_was_pressed = False
            
        # === ВИДЕО (Кнопка B -> Index 1) ===
        if msg.buttons[1] == 1:
            if not self.b_was_pressed:
                self.b_was_pressed = True
                cmd = String()
                cmd.data = 'toggle_video'
                self.media_command_pub.publish(cmd)
                self.get_logger().info('🎥 Видео переключено')
        else:
            self.b_was_pressed = False

        # === YOLO TOGGLE (Кнопка + / START -> Index 11) ===
        if msg.buttons[11] == 1:
            if not self.start_was_pressed:
                self.start_was_pressed = True
                toggle_msg = Bool()
                toggle_msg.data = True
                self.yolo_toggle_pub.publish(toggle_msg)
                self.get_logger().info('🔄 YOLO переключение...')
        else:
            self.start_was_pressed = False
            
        # === СКОРОСТЬ ВНИЗ (Кнопка L4 -> Index 16) ===
        if msg.buttons[16] == 1:
            if not self.l4_was_pressed:
                self.l4_was_pressed = True
                if self.current_speed_mode > 0:
                    self.current_speed_mode -= 1
                    self.get_logger().info(f'🐢 Скорость снижена: {self.speed_modes[self.current_speed_mode][0]}')
                    self.publish_speed_mode()
        else:
            self.l4_was_pressed = False
        
        # === СКОРОСТЬ ВВЕРХ (Кнопка R4 -> Index 17) ===
        if msg.buttons[17] == 1:
            if not self.r4_was_pressed:
                self.r4_was_pressed = True
                if self.current_speed_mode < len(self.speed_modes) - 1:
                    self.current_speed_mode += 1
                    self.get_logger().info(f'🚀 Скорость повышена: {self.speed_modes[self.current_speed_mode][0]}')
                    self.publish_speed_mode()
        else:
            self.r4_was_pressed = False

        # ---------------------------------------------------------
        # БЛОК 2: УПРАВЛЕНИЕ ДВИЖЕНИЕМ (ЛЕВЫЙ СТИК)
        # ---------------------------------------------------------
        
        _, speed_mult = self.speed_modes[self.current_speed_mode]
        
        # Ось 0 = Горизонталь левого стика (Поворот)
        raw_turn = msg.axes[0]
        
        # Ось 1 = Вертикаль левого стика (Движение вперед/назад)
        raw_move = msg.axes[1]
        
        # Применяем мертвую зону
        if abs(raw_turn) < self.deadzone: raw_turn = 0.0
        if abs(raw_move) < self.deadzone: raw_move = 0.0
        
        # Формируем команду для моторов
        twist.linear.x = raw_move * speed_mult
        twist.angular.z = -raw_turn * speed_mult 
        
        self.cmd_pub.publish(twist)

def main(args=None):
    rclpy.init(args=args)
    node = JoyToCmdVel()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
