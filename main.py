import os
import sqlite3
import socket
import subprocess
from bottle import Bottle, run, request, static_file, template, redirect

# Server Config
app = Bottle()
DATABASE = 'PSPyTube.db'
UPLOAD_FOLDER = 'static/'
PSP_RES = "720x480"

# Get IP for PSP connection
hostname = socket.gethostname()
IPAddr = socket.gethostbyname(hostname)

# Initialize Database
def connectDB():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def initDB():
    if not os.path.exists(DATABASE):
        with sqlite3.connect(DATABASE) as conn:
            with open('createdb.sql', 'r') as f:
                conn.executescript(f.read())
        print("Database Initialized")
    else:
        print("Database Already Exists")

# Home Page - List Uploaded Media
@app.route('/')
def index():
    conn = connectDB()
    videos = conn.execute("SELECT * FROM videos ORDER BY upload_date DESC").fetchall()
    tvshows = conn.execute("SELECT * FROM tvshows ORDER BY upload_date DESC").fetchall()
    movies = conn.execute("SELECT * FROM movies ORDER BY upload_date DESC").fetchall()
    conn.close()
    return template('./pages/index.html', videos=videos, tvshows=tvshows, movies=movies, ip=IPAddr)

# Upload and Convert Video
@app.route('/upload', method='POST')
def upload():
    video = request.files.get('video')
    category = request.forms.get('category')
    showname = request.forms.get('showname', '')
    season = request.forms.get('season', '')
    episode = request.forms.get('episode', '')
    movie_title = request.forms.get('movie_title', '')

    if video:
        filename = video.filename
        original_name = filename.rsplit('.', 1)[0]

        # Determine save path based on category
        if category == "Video":
            save_folder = os.path.join(UPLOAD_FOLDER, "videos")
            psp_filename = f"{original_name}.mp4"
        elif category == "TV Show":
            save_folder = os.path.join(UPLOAD_FOLDER, f"tvshows/{showname}/season{season}")
            psp_filename = f"{showname}_S{season}E{episode}.mp4"
        elif category == "Movie":
            save_folder = os.path.join(UPLOAD_FOLDER, "movies")
            psp_filename = f"{movie_title}.mp4"
        else:
            return "Invalid category"

        os.makedirs(save_folder, exist_ok=True)
        save_path = os.path.join(save_folder, filename)
        output_path = os.path.join(save_folder, psp_filename)

        # Save file
        video.save(save_path)

        # FFmpeg conversion to PSP-compatible format
        ffmpeg_command = [
            "ffmpeg", "-i", save_path, "-vcodec", "libx264", "-b:v", "1000k", "-s", "720x480",
            "-aspect", "16:9", "-profile:v", "main", "-level:v", "2.1",
            "-x264-params", "ref=3:bframes=1", "-acodec", "aac", "-b:a", "128k", "-ac", "2",
            "-vf", "format=yuv420p", "-movflags", "+faststart", output_path
        ]
        subprocess.run(ffmpeg_command)

        # Store in database
        conn = connectDB()
        if category == "Video":
            conn.execute("INSERT INTO videos (filename, original_filename) VALUES (?, ?)", (psp_filename, filename))
        elif category == "TV Show":
            conn.execute("INSERT INTO tvshows (filename, original_filename, showname, season, episode) VALUES (?, ?, ?, ?, ?)",
                         (psp_filename, filename, showname, season, episode))
        elif category == "Movie":
            conn.execute("INSERT INTO movies (filename, original_filename, title) VALUES (?, ?, ?)",
                         (psp_filename, filename, movie_title))
        conn.commit()
        conn.close()

        return redirect('/')

    return "Upload Failed"

# Serve Videos
@app.route('/videos/<filename>')
def serve_video(filename):
    return static_file(filename, root=os.path.join(UPLOAD_FOLDER, "videos"), download=filename)

@app.route('/tvshows/<showname>/<season>/<filename>')
def serve_tvshow(showname, season, filename):
    return static_file(filename, root=os.path.join(UPLOAD_FOLDER, f"tvshows/{showname}/season{season}"), download=filename)

@app.route('/movies/<filename>')
def serve_movie(filename):
    return static_file(filename, root=os.path.join(UPLOAD_FOLDER, "movies"), download=filename)

# Delete Video
@app.route('/delete/<category>/<video_id>', method='POST')
def delete_video(category, video_id):
    conn = connectDB()
    if category == "Video":
        table = "videos"
    elif category == "TV Show":
        table = "tvshows"
    elif category == "Movie":
        table = "movies"
    else:
        return "Invalid category"

    video = conn.execute(f"SELECT filename FROM {table} WHERE id=?", (video_id,)).fetchone()
    if video:
        os.remove(os.path.join(UPLOAD_FOLDER, video['filename']))
        conn.execute(f"DELETE FROM {table} WHERE id=?", (video_id,))
        conn.commit()

    conn.close()
    return redirect('/')

if __name__ == '__main__':
    initDB()
    print("HELLO")
    run(app, host='0.0.0.0', port=8181, debug=True,reloader=True)