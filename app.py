# Green Social Online - backend (Flask + yt-dlp)
import os, re, shutil, tempfile, time
from urllib.parse import urlparse
from collections import defaultdict, deque

from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
CORS(app, origins=ALLOWED_ORIGIN)

ALLOWED_HOSTS = (
    "tiktok.com", "instagram.com", "facebook.com", "fb.watch",
    "youtube.com", "youtu.be", "twitter.com", "x.com",
)

MAX_PER_MINUTE = 10
hits = defaultdict(deque)


def too_many_requests(ip):
    now = time.time()
    q = hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= MAX_PER_MINUTE:
        return True
    q.append(now)
    return False


def valid_url(url):
    try:
        u = urlparse(url)
        host = (u.hostname or "").lower()
        return u.scheme in ("http", "https") and any(
            host == h or host.endswith("." + h) for h in ALLOWED_HOSTS
        )
    except Exception:
        return False


def client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()


@app.get("/")
def home():
    return jsonify(ok=True, name="Green Social Online API")


@app.get("/api/info")
def info():
    if too_many_requests(client_ip()):
        return jsonify(error="Bohat zyada requests. Thori der baad try karein."), 429
    url = (request.args.get("url") or "").strip()
    if not valid_url(url):
        return jsonify(error="Ye link support nahi hota. TikTok, Instagram, Facebook ya YouTube ka link dein."), 400
    try:
        opts = {"quiet": True, "skip_download": True, "noplaylist": True, "socket_timeout": 20}
        with yt_dlp.YoutubeDL(opts) as ydl:
            d = ydl.extract_info(url, download=False)
        return jsonify(
            title=d.get("title") or "Video",
            thumbnail=d.get("thumbnail"),
            uploader=d.get("uploader") or d.get("channel") or "",
            duration=d.get("duration"),
        )
    except Exception as e:
        msg = str(e)
        if "private" in msg.lower() or "login" in msg.lower():
            return jsonify(error="Ye video private hai ya login mangti hai."), 400
     return jsonify(error="Video nahi mili. Asli wajah: " + msg[:300]), 400


@app.get("/api/download")
def download():
    if too_many_requests(client_ip()):
        return jsonify(error="Bohat zyada requests. Thori der baad try karein."), 429
    url = (request.args.get("url") or "").strip()
    kind = request.args.get("kind", "video")
    if not valid_url(url):
        return jsonify(error="Ye link support nahi hota."), 400

    tmp = tempfile.mkdtemp(prefix="gso_")
    fmt = "bestaudio[ext=m4a]/bestaudio/best" if kind == "audio" else "best[ext=mp4]/best"
    opts = {
        "quiet": True,
        "noplaylist": True,
        "format": fmt,
        "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
        "socket_timeout": 20,
        "max_filesize": 300 * 1024 * 1024,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            d = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(d)
        title = re.sub(r"[^\w\- ]+", "", d.get("title") or "video")[:60].strip() or "video"
        ext = os.path.splitext(path)[1]

        @after_this_request
        def cleanup(resp):
            shutil.rmtree(tmp, ignore_errors=True)
            return resp

        return send_file(path, as_attachment=True, download_name=f"{title} - GreenSocialOnline{ext}")
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error="Download nahi ho saka. Video private ya bohat bari ho sakti hai."), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
