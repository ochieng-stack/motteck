from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import time
import smtplib
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from email.message import EmailMessage

import cloudinary
import cloudinary.uploader
from supabase import create_client

import bcrypt
import requests

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# ================= INIT =================
app = Flask(__name__)
app.secret_key = 'motteck_super_secret_key'

load_dotenv()


# ================= CLOUDINARY =================
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)


# ================= SUPABASE =================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ================= EMAIL =================
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


# ================= LOGIN SECURITY =================
limiter = Limiter(get_remote_address, app=app)

ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH").encode()

FAILED_ATTEMPTS = {}
LOCK_TIME = 600

RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")


# ================= RECAPTCHA =================
def verify_recaptcha(token):
    response = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={"secret": RECAPTCHA_SECRET, "response": token}
    )
    return response.json().get("success", False)


# ================= TIME AGO =================
def time_ago(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", ""))
        now = datetime.utcnow()
        diff = now - dt

        seconds = diff.total_seconds()

        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            return f"{int(seconds // 60)} min ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)} hrs ago"
        else:
            return f"{int(seconds // 86400)} days ago"

    except:
        return ""


# ================= SPONSORED SCORE =================
def sponsored_score(post):
    views = post.get("views", 0)
    likes = post.get("likes", 0)
    return (views * 0.7) + (likes * 2) + random.uniform(1, 5)


# ================= ADMIN DASHBOARD =================
@app.route("/admin-dashboard")
def admin_dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template("admin_dashboard.html", logged_in=True)


# ================= HOME =================
@app.route('/')
@app.route('/home')
def home():
    return render_template('index.html', logged_in=session.get('logged_in', False))


# ================= STATIC PAGES =================
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/service')
def service():
    return render_template('service.html', logged_in=session.get('logged_in', False))

@app.route('/car')
def car():
    return render_template('car.html', logged_in=session.get('logged_in', False))

@app.route('/truck')
def truck():
    return render_template('truck.html', logged_in=session.get('logged_in', False))

@app.route('/motobike')
def motobike():
    return render_template('motobike.html', logged_in=session.get('logged_in', False))

@app.route('/plane')
def plane():
    return render_template('plane.html', logged_in=session.get('logged_in', False))

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/term')
def term():
    return render_template('term.html')


# ================= ADD POST (FIXED) =================
@app.route('/add_post', methods=['POST'])
def add_post():

    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "unauthorized"}), 403

    try:
        category = request.form.get("category", "")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        image_file = request.files.get("image")

        is_featured = request.form.get("is_featured") == "on"
        is_sponsored = request.form.get("is_sponsored") == "on"

        image_url = None

        if image_file and image_file.filename:
            upload_result = cloudinary.uploader.upload(image_file)
            image_url = upload_result.get("secure_url")

        sponsored_until = None
        if is_sponsored:
            sponsored_until = (datetime.utcnow() + timedelta(days=30)).isoformat()

        new_post = {
            "category": category,
            "title": title,
            "image_url": image_url,
            "description": description,
            "likes": 0,
            "views": 0,
            "created_at": datetime.utcnow().isoformat(),
            "is_featured": is_featured,
            "is_sponsored": is_sponsored,
            "sponsored_until": sponsored_until,
            "ad_clicks": 0,
            "ad_views": 0,
            "ad_earnings": 0
        }

        response = supabase.table("posts").insert(new_post).execute()

        return jsonify({"success": bool(response.data)})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ================= GET POSTS =================
@app.route("/get_posts")
def get_posts():
    posts = supabase.table("posts").select("*").execute().data or []

    for post in posts:
        post["time_ago"] = time_ago(post.get("created_at", ""))

    posts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(posts)


# ================= GET SINGLE POST =================
@app.route("/get_post/<int:post_id>")
def get_post(post_id):

    if not session.get("logged_in"):
        return jsonify({"error": "unauthorized"}), 403

    post = supabase.table("posts").select("*").eq("id", post_id).execute().data
    if not post:
        return jsonify({"error": "not found"}), 404

    return jsonify(post[0])


# ================= ANALYTICS =================
@app.route("/analytics")
def analytics():

    if not session.get("logged_in"):
        return jsonify({"error": "unauthorized"}), 403

    posts = supabase.table("posts").select("*").execute().data or []

    return jsonify({
        "total_posts": len(posts),
        "total_views": sum(p.get("views", 0) for p in posts),
        "total_likes": sum(p.get("likes", 0) for p in posts),
        "top_posts": sorted(posts, key=lambda x: x.get("views", 0), reverse=True)[:5]
    })


# ================= EDIT POST =================
@app.route('/edit_post/<int:post_id>', methods=['POST'])
def edit_post(post_id):

    if not session.get("logged_in"):
        return jsonify({"success": False}), 403

    update_data = {
        "title": request.form.get("title"),
        "description": request.form.get("description"),
        "category": request.form.get("category"),
        "is_featured": request.form.get("is_featured") == "on",
        "is_sponsored": request.form.get("is_sponsored") == "on"
    }

    image_file = request.files.get("image")
    if image_file and image_file.filename:
        upload_result = cloudinary.uploader.upload(image_file)
        update_data["image_url"] = upload_result.get("secure_url")

    supabase.table("posts").update(update_data).eq("id", post_id).execute()

    return jsonify({"success": True})


# ================= DELETE =================
@app.route('/delete_post/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):

    if not session.get("logged_in"):
        return jsonify({"success": False}), 403

    supabase.table("posts").delete().eq("id", post_id).execute()
    return jsonify({"success": True})


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)