# cliptube-backend/app.py
import os
import uuid
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
import cloudinary
import cloudinary.uploader
import psycopg2 # For connecting to PostgreSQL
from dotenv import load_dotenv # For loading environment variables from .env file

# Load environment variables from .env file (for local development only)
# IMPORTANT: On Render, environment variables will be set directly in the panel,
# so `load_dotenv()` will have no effect there.
load_dotenv()

app = Flask(__name__)
CORS(app) # Enable CORS for all domains (for testing)

# --- Cloudinary Configuration ---
# Get data from environment variables
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# --- PostgreSQL Database Configuration (Render.com) ---
# Render.com automatically provides DATABASE_URL for its PostgreSQL service
DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    """Function to connect to the database."""
    # Render.com provides DATABASE_URL. Remember to provide it in your local .env file.
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set. Please set it in Render.com environment variables or in your .env file.")
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Function to initialize the database schema (create table)."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                video_url TEXT NOT NULL,
                thumbnail_url TEXT,
                upload_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                delete_token TEXT NOT NULL UNIQUE
            );
        """)
        conn.commit()
        print("Table 'videos' created or already exists in PostgreSQL on Render.com.")
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# Initialize the database when the application starts
# We use `app.before_first_request` to ensure Flask context is available
@app.before_first_request
def initialize_database():
    init_db()

# --- Endpoint for uploading videos ---
@app.route('/api/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({"message": "No video file provided for upload."}), 400

    video_file = request.files['video']
    title = request.form.get('title')
    description = request.form.get('description', '')

    if not title:
        return jsonify({"message": "Video title is required."}), 400

    conn = None
    cur = None
    try:
        # Upload video to Cloudinary
        upload_result = cloudinary.uploader.upload(
            video_file,
            resource_type="video",
            folder="cliptube_videos", # Optional folder in Cloudinary
            transformation=[
                {"height": 480, "crop": "limit", "quality": "auto:good"} # Compress to 480p
            ]
        )

        # Generate a unique deletion token
        delete_token = str(uuid.uuid4()) # Using UUID as a token

        # Create new video object
        video_id = upload_result['public_id']
        video_url = upload_result['secure_url']
        thumbnail_url = cloudinary.utils.cloudinary_url(
            video_id,
            resource_type="video",
            format="jpg",
            quality="auto",
            width=320,
            height=180,
            crop="fill",
            gravity="auto"
        )[0] # [0] because it returns a tuple

        new_video_data = {
            "id": video_id,
            "title": title,
            "description": description,
            "video_url": video_url, # Column name in DB
            "thumbnail_url": thumbnail_url, # Column name in DB
            "upload_date": datetime.now(),
            "delete_token": delete_token
        }

        # Save metadata to PostgreSQL database on Render.com
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO videos (id, title, description, video_url, thumbnail_url, upload_date, delete_token)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            new_video_data['id'], new_video_data['title'], new_video_data['description'],
            new_video_data['video_url'], new_video_data['thumbnail_url'], new_video_data['upload_date'],
            new_video_data['delete_token']
        ))
        conn.commit()

        # Prepare response for frontend (without deleteToken)
        response_video = {
            "id": new_video_data['id'],
            "title": new_video_data['title'],
            "description": new_video_data['description'],
            "videoUrl": new_video_data['video_url'],
            "thumbnail": new_video_data['thumbnail_url'],
            "uploadDate": new_video_data['upload_date'].isoformat(),
        }
        response_video['deleteLink'] = f"{request.url_root}api/videos/{new_video_data['id']}/delete?token={delete_token}"

        return jsonify({
            "message": "Video successfully uploaded and is being processed!",
            "video": response_video
        }), 201

    except Exception as e:
        print(f"Error during video upload or saving: {e}")
        return jsonify({"message": f"Server error: {e}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# --- Endpoint for fetching all videos ---
@app.route('/api/videos', methods=['GET'])
def get_videos():
    search_term = request.args.get('search', '').lower()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if search_term:
            cur.execute("""
                SELECT id, title, description, video_url, thumbnail_url, upload_date
                FROM videos
                WHERE LOWER(title) LIKE %s OR LOWER(description) LIKE %s
                ORDER BY upload_date DESC;
            """, (f'%{search_term}%', f'%{search_term}%'))
        else:
            cur.execute("""
                SELECT id, title, description, video_url, thumbnail_url, upload_date
                FROM videos
                ORDER BY upload_date DESC;
            """)

        db_videos = cur.fetchall()
        
        videos_list = []
        for v in db_videos:
            videos_list.append({
                "id": v[0],
                "title": v[1],
                "description": v[2],
                "videoUrl": v[3],
                "thumbnail": v[4],
                "uploadDate": v[5].isoformat() # Convert date to ISO format
            })
        
        return jsonify(videos_list), 200

    except Exception as e:
        print(f"Error fetching videos: {e}")
        return jsonify({"message": f"Server error: {e}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# --- Endpoint for fetching single video details ---
@app.route('/api/videos/<video_id>', methods=['GET'])
def get_single_video(video_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, description, video_url, thumbnail_url, upload_date
            FROM videos
            WHERE id = %s;
        """, (video_id,))
        video_data = cur.fetchone()

        if not video_data:
            return jsonify({"message": "Video not found."}), 404

        video_details = {
            "id": video_data[0],
            "title": video_data[1],
            "description": video_data[2],
            "videoUrl": video_data[3],
            "thumbnail": video_data[4],
            "uploadDate": video_data[5].isoformat()
        }
        return jsonify(video_details), 200

    except Exception as e:
        print(f"Error fetching video details: {e}")
        return jsonify({"message": f"Server error: {e}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# --- Endpoint for deleting a video (requires token) ---
@app.route('/api/videos/<video_id>/delete', methods=['DELETE'])
def delete_video(video_id):
    delete_token = request.args.get('token')

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get token from database
        cur.execute("SELECT delete_token FROM videos WHERE id = %s;", (video_id,))
        db_token_row = cur.fetchone()

        if not db_token_row:
            return jsonify({"message": "Video not found."}), 404

        db_token = db_token_row[0]

        if db_token != delete_token:
            return jsonify({"message": "Invalid deletion token."}), 403

        # Delete video from Cloudinary
        cloudinary.uploader.destroy(video_id, resource_type="video")
        print(f"Deleted video from Cloudinary: {video_id}")

        # Delete record from database
        cur.execute("DELETE FROM videos WHERE id = %s;", (video_id,))
        conn.commit()

        return jsonify({"message": "Video successfully deleted."}), 200

    except Exception as e:
        print(f"Error deleting video: {e}")
        return jsonify({"message": f"Server error: {e}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    # On Render.com, the port is set by the PORT environment variable.
    # Use debug=True only for local development.
    app.run(debug=os.getenv('FLASK_ENV') == 'development', port=int(os.getenv('PORT', 3001)))
