#!/usr/bin/env python3
"""
Веб-сервер для просмотра фото и видео с робота.
Порт 5000.
"""
from flask import Flask, render_template_string, send_from_directory, jsonify
import os

app = Flask(__name__)

PHOTO_DIR = '/home/grunge/ros2_ws/media/photos'
VIDEO_DIR = '/home/grunge/ros2_ws/media/videos'
ROBOT_IP = '192.168.1.131'

# Убедимся, что папки существуют
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📷 Медиа робота</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 2px solid #3d3d3d;
        }
        .header h1 { color: #4fc3f7; }
        .status {
            background: #2d2d2d;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: bold;
            color: #4caf50;
        }
        .section { margin-bottom: 40px; }
        .section h2 {
            color: #4fc3f7;
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
        }
        .item {
            background: #2d2d2d;
            border-radius: 10px;
            overflow: hidden;
            transition: transform 0.2s;
            cursor: pointer;
        }
        .item:hover { transform: scale(1.03); }
        .item img, .item video {
            width: 100%;
            height: 180px;
            object-fit: cover;
            display: block;
        }
        .item-info {
            padding: 10px;
            font-size: 0.9em;
            color: #9e9e9e;
        }
        .item-info .name {
            color: #e0e0e0;
            font-weight: bold;
            margin-bottom: 5px;
            word-break: break-all;
        }
        .empty {
            text-align: center;
            color: #666;
            padding: 40px;
            font-size: 1.2em;
        }
        .controls {
            position: fixed;
            bottom: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            font-weight: bold;
            text-decoration: none;
            color: white;
        }
        .btn-photo { background: #4caf50; }
        .btn-video { background: #f44336; }
        .btn:hover { opacity: 0.8; }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active { display: flex; }
        .modal img, .modal video {
            max-width: 90%;
            max-height: 90%;
        }
        .modal-close {
            position: absolute;
            top: 20px;
            right: 30px;
            color: white;
            font-size: 2em;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📷 Медиа робота</h1>
        <div class="status">✅ Готов к работе</div>
    </div>

    <div class="section">
        <h2>📸 Фото ({{ photos|length }})</h2>
        {% if photos %}
        <div class="grid">
            {% for photo in photos %}
            <div class="item" onclick="openModal('/photo/{{ photo }}')">
                <img src="/photo/{{ photo }}" alt="{{ photo }}">
                <div class="item-info">
                    <div class="name">{{ photo }}</div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty">Нет фото. Нажмите кнопку A на джойстике.</div>
        {% endif %}
    </div>

    <div class="section">
        <h2>🎥 Видео ({{ videos|length }})</h2>
        {% if videos %}
        <div class="grid">
            {% for video in videos %}
            <div class="item" onclick="openModal('/video/{{ video }}', true)">
                <video src="/video/{{ video }}" muted></video>
                <div class="item-info">
                    <div class="name">{{ video }}</div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty">Нет видео. Нажмите кнопку B на джойстике для записи.</div>
        {% endif %}
    </div>

    <div class="controls">
        <a href="/" class="btn btn-photo" onclick="location.reload()">🔄 Обновить</a>
        <a href="http://{{ robot_ip }}:8000/stream" class="btn btn-video" target="_blank">📺 Стрим</a>
    </div>

    <div class="modal" id="modal" onclick="closeModal()">
        <span class="modal-close">&times;</span>
        <div id="modalContent"></div>
    </div>

    <script>
        function openModal(src, isVideo=false) {
            const modal = document.getElementById('modal');
            const content = document.getElementById('modalContent');
            if (isVideo) {
                content.innerHTML = '<video src="' + src + '" controls autoplay style="max-width:90%; max-height:90%;"></video>';
            } else {
                content.innerHTML = '<img src="' + src + '" style="max-width:90%; max-height:90%;">';
            }
            modal.classList.add('active');
        }
        function closeModal() {
            document.getElementById('modal').classList.remove('active');
            document.getElementById('modalContent').innerHTML = '';
        }
        // Автообновление каждые 10 секунд
        setTimeout(() => location.reload(), 10000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    try:
        photos = sorted([f for f in os.listdir(PHOTO_DIR) if f.endswith('.jpg')], reverse=True)
        videos = sorted([f for f in os.listdir(VIDEO_DIR) if f.endswith('.avi')], reverse=True)
        return render_template_string(HTML_TEMPLATE, 
                                      photos=photos, 
                                      videos=videos, 
                                      robot_ip=ROBOT_IP)
    except Exception as e:
        return f'<h1>Ошибка</h1><p>{str(e)}</p>', 500

@app.route('/photo/<filename>')
def photo(filename):
    return send_from_directory(PHOTO_DIR, filename)

@app.route('/video/<filename>')
def video(filename):
    return send_from_directory(VIDEO_DIR, filename, mimetype='video/avi')

@app.route('/api/status')
def api_status():
    try:
        photos = len([f for f in os.listdir(PHOTO_DIR) if f.endswith('.jpg')])
        videos = len([f for f in os.listdir(VIDEO_DIR) if f.endswith('.avi')])
        return jsonify({'photos': photos, 'videos': videos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("📷 МЕДИА-СЕРВЕР ЗАПУЩЕН!")
    print(f"🌐 Откройте: http://{ROBOT_IP}:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
