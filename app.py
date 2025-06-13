from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json
from datetime import datetime
import uuid

app = Flask(__name__)

# Konfiguracja
UPLOAD_FOLDER = 'uploads'
THUMBNAILS_FOLDER = 'thumbnails'
DATA_FILE = 'videos.json'

# Tworzenie folderów jeśli nie istnieją
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAILS_FOLDER, exist_ok=True)

# Ładowanie danych wideo
def load_videos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# Zapisywanie danych wideo
def save_videos(videos):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)

# Przykładowe dane wideo
def init_sample_data():
    if not os.path.exists(DATA_FILE):
        sample_videos = [
            {
                "id": str(uuid.uuid4()),
                "title": "Piękne wschody słońca",
                "description": "Kolekcja najpiękniejszych wschodów słońca z całego świata",
                "thumbnail": "https://picsum.photos/320/180?random=1",
                "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4",
                "views": 1240,
                "upload_date": "2024-06-10",
                "duration": "3:45"
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Relaksująca muzyka do pracy",
                "description": "Spokojna muzyka instrumentalna idealna do koncentracji",
                "thumbnail": "https://picsum.photos/320/180?random=2",
                "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_2mb.mp4",
                "views": 856,
                "upload_date": "2024-06-08",
                "duration": "15:30"
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Szybki tutorial CSS",
                "description": "Nauka CSS w 10 minut - podstawy stylowania stron",
                "thumbnail": "https://picsum.photos/320/180?random=3",
                "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_5mb.mp4",
                "views": 2341,
                "upload_date": "2024-06-12",
                "duration": "10:15"
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Gotowanie: Szybki obiad",
                "description": "Jak przygotować pyszny obiad w 20 minut",
                "thumbnail": "https://picsum.photos/320/180?random=4",
                "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4",
                "views": 567,
                "upload_date": "2024-06-11",
                "duration": "8:22"
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Podróż po górach",
                "description": "Niesamowite widoki z wędrówki po Tatrach",
                "thumbnail": "https://picsum.photos/320/180?random=5",
                "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_2mb.mp4",
                "views": 1789,
                "upload_date": "2024-06-09",
                "duration": "12:18"
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Trening w domu",
                "description": "Efektywny trening bez sprzętu - tylko 15 minut dziennie",
                "thumbnail": "https://picsum.photos/320/180?random=6",
                "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4",
                "views": 3456,
                "upload_date": "2024-06-07",
                "duration": "16:45"
            }
        ]
        save_videos(sample_videos)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/watch/<video_id>')
def watch(video_id):
    videos = load_videos()
    video = next((v for v in videos if v['id'] == video_id), None)
    if not video:
        return "Wideo nie znalezione", 404
    
    # Zwiększ liczbę wyświetleń
    video['views'] += 1
    save_videos(videos)
    
    return render_template('watch.html', video=video)

@app.route('/api/videos')
def api_videos():
    videos = load_videos()
    search_query = request.args.get('search', '').lower()
    
    if search_query:
        filtered_videos = [
            v for v in videos 
            if search_query in v['title'].lower() or search_query in v['description'].lower()
        ]
        return jsonify(filtered_videos)
    
    return jsonify(videos)

@app.route('/api/video/<video_id>')
def api_video(video_id):
    videos = load_videos()
    video = next((v for v in videos if v['id'] == video_id), None)
    if video:
        return jsonify(video)
    return jsonify({"error": "Wideo nie znalezione"}), 404

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        video_url = request.form.get('video_url')
        thumbnail_url = request.form.get('thumbnail_url', 'https://picsum.photos/320/180?random=7')
        
        if title and video_url:
            videos = load_videos()
            new_video = {
                "id": str(uuid.uuid4()),
                "title": title,
                "description": description or "",
                "thumbnail": thumbnail_url,
                "video_url": video_url,
                "views": 0,
                "upload_date": datetime.now().strftime("%Y-%m-%d"),
                "duration": "0:00"
            }
            videos.append(new_video)
            save_videos(videos)
            
            return jsonify({"success": True, "video_id": new_video["id"]})
        
        return jsonify({"success": False, "error": "Brak wymaganych danych"}), 400
    
    return render_template('upload.html')

if __name__ == '__main__':
    init_sample_data()
    app.run(debug=True)
