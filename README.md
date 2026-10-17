# 🤖 ROS 2 Yahboom Rosmaster Controller

Полный стек управления роботом на базе Raspberry Pi 5 и ROS 2 (Jazzy/Humble).
Включает телеуправление через Bluetooth, распознавание объектов (YOLOv8), веб-стриминг видео и автоматическую архивацию фото/видео.

## ✨ Возможности

- ✅ **Телеуправление:** Плавное управление шасси и камерой через геймпад 8BitDo Ultimate 2 (Bluetooth Mode).
- 👁️ **AI Vision:** Распознавание 80+ классов объектов в реальном времени (YOLOv8n ONNX).
- 📸 **Медиа-архив:** Мгновенные снимки и запись видео по кнопкам джойстика.
- 🌐 **Веб-галерея:** Автоматический просмотр сохраненных фото и видео в браузере.
- 📺 **Live Stream:** Трансляция видео с наложенными рамками AI прямо в браузер.

## 🛠️ Требования

- **Железо:** Raspberry Pi 4/5, Yahboom Rosmaster Kit, USB Камера, 8BitDo Ultimate 2.
- **Софт:** Ubuntu 22.04/24.04, ROS 2 Humble/Jazzy.
- **Библиотеки:** OpenCV, NumPy, OnnxRuntime, Flask.

## 🚀 Быстрый старт

### 1. Установка зависимостей
```bash
sudo apt update
sudo apt install ros-humble-desktop python3-opencv python3-numpy onnxruntime-gpu
pip3 install flask opencv-python-headless
```

### 2. Сборка пакета
```bash
cd ~/ros2_ws
colcon build --packages-select yahboom_driver
source install/setup.bash
```

### 3. Запуск системы (4 терминала)

Для работы всех функций необходимо запустить узлы в следующем порядке:

| Терминал | Команда | Описание |
| :--- | :--- | :--- |
| **1. Ядро робота** | `ros2 launch yahboom_driver robot_bringup.launch.py` | Драйверы моторов, камеры и джойстика. |
| **2. YOLO AI** | `ros2 run yahboom_driver yolo_node -p input_size:=416` | Узел искусственного интеллекта. |
| **3. Media Node** | `ros2 run yahboom_driver media_node` | Сервис сохранения фото/видео. |
| **4. Web Stream** | `python3 scripts/yolo_web_stream.py` | Веб-сервер для трансляции видео. |

*(Дополнительно)* Галерея медиафайлов:
```bash
python3 scripts/media_server.py
```

## 🎮 Карта управления (8BitDo BT)

Настройки кнопок уже прошиты в коде `joy_to_cmdvel.py`.

| Действие | Кнопка / Стиль | Индекс ROS | Функция |
| :--- | :--- | :---: | :--- |
| **Движение** | Левый стик | Axis 0, 1 | Езда вперед/назад, повороты. |
| **Камера** | Правый стик | Axis 2, 3 | Панорамирование (Pan) и Наклон (Tilt). |
| **Скорость -** | L4 (Back Left) | Btn 16 | Снижение скорости (SLOW/MED/FAST/MAX). |
| **Скорость +** | R4 (Back Right) | Btn 17 | Повышение скорости. |
| **YOLO ON/OFF**| **+ (Start)** | Btn 11 | Включение/выключение рамок распознавания. |
| **Фото** | **A (Green)** | Btn 0 | Сохранение JPEG в `media/photos/`. |
| **Видео** | **B (Red)** | Btn 1 | Старт/Стоп записи AVI в `media/videos/`. |

## 🌐 Веб-интерфейсы

После запуска доступны следующие адреса (замените `<IP>` на адрес вашего Raspberry Pi):

1.  **Стрим с AI:** `http://<IP>:8000/stream`
    *   Видео с зелеными рамками вокруг распознанных объектов.
2.  **Чистый стрим:** `http://<IP>:8080/stream?topic=/camera/image_raw/compressed`
    *   Оригинальное видео без обработки ИИ (меньше нагрузка).
3.  **Галерея медиа:** `http://<IP>:5000`
    *   Просмотр всех сделанных фото и видео с возможностью скачивания.

## 📂 Структура проекта

```text
my_robot_project/
├── yahboom_driver/       # Основной ROS 2 пакет
│   ├── yahboom_driver/   # Python узлы (base, camera, yolo, media, joy)
│   ├── models/           # Файл yolov8n.onnx
│   └── launch/           # Launch файлы
├── scripts/              # Внешние утилиты
│   ├── yolo_web_stream.py # Flask сервер для стрима
│   ├── media_server.py    # Flask сервер для галереи
│   └── joy_mapper.py      # Инструмент диагностики кнопок
└── media/                # Папка для генерируемых файлов
    ├── photos/
    └── videos/
```

## 🛠️ Диагностика

Если кнопки не работают или оси перепутаны, используйте универсальный маппер:
```bash
# В одном окне
ros2 run joy joy_node

# В другом окне
python3 scripts/joy_mapper.py
```
Нажимайте кнопки — скрипт выведет их реальные индексы в консоли.

## 📝 Лицензия
MIT License
