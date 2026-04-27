from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import time
import smtplib
from datetime import datetime
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


# ================= LOGIN =================
@app.route('/login-goodwill254@', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    ip = get_remote_address()

    if ip in FAILED_ATTEMPTS and FAILED_ATTEMPTS[ip]['locked_until'] > time.time():
        return render_template('admin.html', error="Too many attempts. Try later.")

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        recaptcha_token = request.form.get("g-recaptcha-response")

        if not verify_recaptcha(recaptcha_token):
            return render_template('admin.html', error="reCAPTCHA failed.")

        if username == ADMIN_USER and bcrypt.checkpw(password.encode(), ADMIN_PASS_HASH):
            session['logged_in'] = True
            FAILED_ATTEMPTS.pop(ip, None)
            return redirect(url_for('home'))

        FAILED_ATTEMPTS.setdefault(ip, {'count': 0, 'locked_until': 0})
        FAILED_ATTEMPTS[ip]['count'] += 1

        if FAILED_ATTEMPTS[ip]['count'] >= 5:
            FAILED_ATTEMPTS[ip]['locked_until'] = time.time() + LOCK_TIME

        return render_template('admin.html', error="Invalid login")

    return render_template('admin.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))


# ================= GET POSTS (ALL CATEGORY PAGES) =================
@app.route("/get_posts")
def get_posts():
    try:
        posts = supabase.table("posts").select("*").execute().data or []

        for post in posts:
            post["time_ago"] = time_ago(post.get("created_at", ""))

        posts.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )

        return jsonify(posts)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= HOME POSTS =================
@app.route("/get_home_posts")
def get_home_posts():
    try:
        all_posts = supabase.table("posts").select("*").execute().data or []

        for post in all_posts:
            post["time_ago"] = time_ago(post.get("created_at", ""))

        # FEATURED
        featured = sorted(
            [p for p in all_posts if p.get("is_featured")],
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )[:4]

        featured_ids = {p["id"] for p in featured}

        # SPONSORED
        sponsored = [
            p for p in all_posts
            if p.get("is_sponsored")
        ]

        sponsored_ids = {p["id"] for p in sponsored}

        # TRENDING
        def trending_score(p):
            views = p.get("views", 0)
            likes = p.get("likes", 0)

            if views < 50:
                return 0

            return (views * 0.5) + (likes * 2)

        trending = sorted(all_posts, key=trending_score, reverse=True)

        trending = [
            p for p in trending
            if p["id"] not in featured_ids
            and p["id"] not in sponsored_ids
        ][:6]

        trending_ids = {p["id"] for p in trending}

        # RECENT
        recent = [
            p for p in all_posts
            if p["id"] not in featured_ids
            and p["id"] not in trending_ids
            and p["id"] not in sponsored_ids
        ]

        recent.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )

        return jsonify({
            "featured": featured,
            "sponsored": sponsored,
            "trending": trending,
            "recent": recent
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= ADD POST =================
@app.route('/add_post', methods=['POST'])
def add_post():

    category = request.form.get('category')
    title = request.form.get('title')
    image_file = request.files.get('image')
    description = request.form.get('description')

    image_url = None

    if image_file and image_file.filename:
        upload_result = cloudinary.uploader.upload(image_file)
        image_url = upload_result.get("secure_url")

    new_post = {
        "category": category,
        "title": title,
        "image_url": image_url,
        "description": description,
        "likes": 0,
        "views": 0,
        "created_at": datetime.utcnow().isoformat(),
        "is_featured": True if request.form.get("is_featured") else False,
        "is_sponsored": True if request.form.get("is_sponsored") else False
    }

    response = supabase.table("posts").insert(new_post).execute()

    return jsonify({"success": bool(response.data)})


# ================= SINGLE POST =================
@app.route('/post/<int:post_id>')
def single_post(post_id):
    response = supabase.table("posts").select("*").eq("id", post_id).execute()

    if not response.data:
        return "Post not found", 404

    return render_template("single_post.html", post=response.data[0])


# ================= LIKE =================
@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    try:
        response = supabase.table("posts").select("likes").eq("id", post_id).execute()

        if not response.data:
            return jsonify({"success": False}), 404

        current = response.data[0]["likes"] or 0

        supabase.table("posts").update({
            "likes": current + 1
        }).eq("id", post_id).execute()

        return jsonify({"success": True, "likes": current + 1})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ================= VIEW =================
@app.route('/view/<int:post_id>', methods=['POST'])
def view_post(post_id):
    try:
        if 'viewed_posts' not in session:
            session['viewed_posts'] = []

        response = supabase.table("posts").select("views").eq("id", post_id).execute()

        if not response.data:
            return jsonify({"success": False}), 404

        current = response.data[0]["views"] or 0

        if post_id not in session['viewed_posts']:
            supabase.table("posts").update({
                "views": current + 1
            }).eq("id", post_id).execute()

            session['viewed_posts'].append(post_id)
            current += 1

        return jsonify({"success": True, "views": current})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ================= CONTACT =================
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        email = request.form.get('email')
        message = request.form.get('text')

        msg = EmailMessage()
        msg['Subject'] = f'Motteck Contact {firstname} {lastname}'
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg.set_content(f"{firstname} {lastname}\n{email}\n{message}")

        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)

        return jsonify({"status": "success"})

    return render_template('contact.html')


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)