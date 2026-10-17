#!/usr/bin/env python3
"""
Универсальный диагностический инструмент для джойстиков ROS 2.
Показывает индексы кнопок и осей в реальном времени.
Запуск: python3 ~/ros2_ws/joy_mapper.py
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
import sys

class JoyMapper(Node):
    def __init__(self):
        super().__init__('joy_mapper')
        
        self.sub = self.create_subscription(Joy, '/joy', self.callback, 10)
        
        # Хранилище предыдущего состояния для определения изменений
        self.prev_buttons = []
        self.prev_axes = []
        
        print("=" * 60)
        print("🎮 JOYSTICK MAPPER ЗАПУЩЕН")
        print("-" * 60)
        print("Нажимайте кнопки и двигайте стики.")
        print("Скрипт выведет только ИЗМЕНЕНИЯ (чтобы не спамить).")
        print("Для выхода нажмите Ctrl+C")
        print("=" * 60)
        print(f"{'КНОПКИ':<15} | {'ОСИ':<15}")
        print("-" * 32)

    def callback(self, msg: Joy):
        current_buttons = list(msg.buttons)
        current_axes = list(msg.axes)
        
        # Инициализация при первом запуске
        if not self.prev_buttons:
            self.prev_buttons = [0] * len(current_buttons)
            self.prev_axes = [0.0] * len(current_axes)
            
        changed_items = []
        
        # Проверка кнопок
        for i, val in enumerate(current_buttons):
            prev_val = self.prev_buttons[i] if i < len(self.prev_buttons) else 0
            # Если кнопка нажата (стала 1), а раньше была 0
            if val == 1 and prev_val == 0:
                changed_items.append(f"[BTN {i}] Нажата")
            # Если кнопка отпущена (стала 0), а раньше была 1
            elif val == 0 and prev_val == 1:
                changed_items.append(f"[BTN {i}] Отпущена")
                
        # Проверка осей (только если значение изменилось существенно)
        for i, val in enumerate(current_axes):
            prev_val = self.prev_axes[i] if i < len(self.prev_axes) else 0.0
            if abs(val - prev_val) > 0.05: # Порог чувствительности
                direction = "▲" if val > prev_val else "▼"
                changed_items.append(f"[AXIS {i}] {direction} {val:.2f}")
        
        # Выводим изменения, если они были
        if changed_items:
            print(" | ".join(changed_items))
            
        # Сохраняем текущее состояние как предыдущее
        self.prev_buttons = current_buttons
        self.prev_axes = current_axes

def main(args=None):
    rclpy.init(args=args)
    node = JoyMapper()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n\n✅ Остановка Mapper...")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
