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

    score = (views * 0.7) + (likes * 2)

    # rotation boost
    score += random.uniform(1, 5)

    return score
# ========= adimn dashboard ===============
@app.route("/admin-dashboard")
def admin_dashboard():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template(
        "admin_dashboard.html",
        logged_in=True
    )

# ================= HOME =================
@app.route('/')
@app.route('/home')
def home():
    return render_template(
        'index.html',
        logged_in=session.get('logged_in', False)
    )


# ================= STATIC PAGES =================
@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/service')
def service():
    return render_template(
        'service.html',
        logged_in=session.get('logged_in', False)
    )


@app.route('/car')
def car():
    return render_template(
        'car.html',
        logged_in=session.get('logged_in', False)
    )


@app.route('/truck')
def truck():
    return render_template(
        'truck.html',
        logged_in=session.get('logged_in', False)
    )


@app.route('/motobike')
def motobike():
    return render_template(
        'motobike.html',
        logged_in=session.get('logged_in', False)
    )


@app.route('/plane')
def plane():
    return render_template(
        'plane.html',
        logged_in=session.get('logged_in', False)
    )


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

    if ip in FAILED_ATTEMPTS:
        if FAILED_ATTEMPTS[ip]["locked_until"] > time.time():
            return render_template(
                "admin.html",
                error="Too many attempts. Try later."
            )

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]
        recaptcha_token = request.form.get("g-recaptcha-response")

        if not verify_recaptcha(recaptcha_token):
            return render_template(
                "admin.html",
                error="reCAPTCHA failed."
            )

        if username == ADMIN_USER and bcrypt.checkpw(
            password.encode(),
            ADMIN_PASS_HASH
        ):
            session["logged_in"] = True
            FAILED_ATTEMPTS.pop(ip, None)
            return redirect(url_for("admin_dashboard"))

        FAILED_ATTEMPTS.setdefault(
            ip,
            {"count": 0, "locked_until": 0}
        )

        FAILED_ATTEMPTS[ip]["count"] += 1

        if FAILED_ATTEMPTS[ip]["count"] >= 5:
            FAILED_ATTEMPTS[ip]["locked_until"] = time.time() + LOCK_TIME

        return render_template(
            "admin.html",
            error="Invalid login"
        )

    return render_template("admin.html")


@app.route('/logout')
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("home"))


# ================= GET POSTS =================
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

# ================= GET SINGLE POST (EDIT) =================
@app.route("/get_post/<int:post_id>")
def get_post(post_id):

    if not session.get("logged_in"):
        return jsonify({"error": "unauthorized"}), 403

    try:
        post = supabase.table("posts") \
            .select("*") \
            .eq("id", post_id) \
            .execute().data

        if not post:
            return jsonify({"error": "not found"}), 404

        return jsonify(post[0])

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================= HOME POSTS =================
@app.route("/get_home_posts")
def get_home_posts():

    try:
        all_posts = supabase.table("posts").select("*").execute().data or []

        for post in all_posts:
            post["time_ago"] = time_ago(post.get("created_at", ""))

        # ==========================================
        # FEATURED (manual picks only, max 4)
        # ==========================================
        featured = sorted(
            [p for p in all_posts if p.get("is_featured")],
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )[:4]

        featured_ids = {p["id"] for p in featured}

        # ==========================================
        # ACTIVE SPONSORED POSTS ONLY
        # ==========================================
        sponsored = []

        for post in all_posts:

            if not post.get("is_sponsored"):
                continue

            expiry = post.get("sponsored_until")

            if not expiry:
                sponsored.append(post)
                continue

            try:
                expiry_date = datetime.fromisoformat(
                    expiry.replace("Z", "")
                )

                if expiry_date > datetime.utcnow():
                    sponsored.append(post)

            except:
                sponsored.append(post)

        sponsored = sorted(
            sponsored,
            key=sponsored_score,
            reverse=True
        )

        sponsored_ids = {p["id"] for p in sponsored}

        # ==========================================
        # ORGANIC POSTS ONLY
        # (not featured, not sponsored)
        # ==========================================
        organic_posts = [
            p for p in all_posts
            if p["id"] not in featured_ids
            and p["id"] not in sponsored_ids
        ]

        # ==========================================
        # STRICT TRENDING SCORE
        # only real engagement wins
        # ==========================================
        def trending_score(post):

            views = post.get("views", 0) or 0
            likes = post.get("likes", 0) or 0
            clicks = post.get("clicks", 0) or 0

            score = (
                (views * 0.20) +
                (likes * 5) +
                (clicks * 3)
            )

            return score

        # only posts with enough activity can trend
        trending_candidates = []

        for post in organic_posts:

            views = post.get("views", 0) or 0
            likes = post.get("likes", 0) or 0
            clicks = post.get("clicks", 0) or 0

            score = trending_score(post)

            if (
                views >= 30 and
                (likes >= 2 or clicks >= 3) and
                score >= 25
            ):
                trending_candidates.append(post)

        trending = sorted(
            trending_candidates,
            key=trending_score,
            reverse=True
        )[:5]

        trending_ids = {p["id"] for p in trending}

        # ==========================================
        # RECENT POSTS
        # remaining organic posts only
        # ==========================================
        recent = [
            p for p in organic_posts
            if p["id"] not in trending_ids
        ]

        recent.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )

        # ==========================================
        # INSERT SPONSORED INTO RECENT FEED
        # after every 3 posts
        # ==========================================
        mixed_recent = []
        sponsor_index = 0

        for i, post in enumerate(recent):

            mixed_recent.append(post)

            if (i + 1) % 3 == 0:
                if sponsor_index < len(sponsored):
                    mixed_recent.append(
                        sponsored[sponsor_index]
                    )
                    sponsor_index += 1

        while sponsor_index < len(sponsored):
            mixed_recent.append(
                sponsored[sponsor_index]
            )
            sponsor_index += 1

        return jsonify({
            "featured": featured,
            "trending": trending,
            "recent": mixed_recent,
            "sponsored": sponsored
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# ================= ADD POST =================
@app.route('/add_post', methods=['POST'])
def add_post():

    category = request.form.get("category")
    title = request.form.get("title")
    image_file = request.files.get("image")
    description = request.form.get("description")

    image_url = None

    if image_file and image_file.filename:
        upload_result = cloudinary.uploader.upload(image_file)
        image_url = upload_result.get("secure_url")

    is_sponsored = True if request.form.get("is_sponsored") else False

    sponsored_until = None

    # default 30 days ad
    if is_sponsored:
        sponsored_until = (
            datetime.utcnow() + timedelta(days=30)
        ).isoformat()

    new_post = {
        "category": category,
        "title": title,
        "image_url": image_url,
        "description": description,
        "likes": 0,
        "views": 0,
        "created_at": datetime.utcnow().isoformat(),
        "is_featured": True if request.form.get("is_featured") else False,
        "is_sponsored": is_sponsored,
        "sponsored_until": sponsored_until,
        "ad_clicks": 0,
        "ad_views": 0,
        "ad_earnings": 0
    }

    response = supabase.table("posts").insert(new_post).execute()

    return jsonify({
        "success": bool(response.data)
    })

    
# ================= ANALYTICS DASHBOARD DATA =================
@app.route("/analytics")
def analytics():

    if not session.get("logged_in"):
        return jsonify({"error": "unauthorized"}), 403

    try:
        posts = supabase.table("posts").select("*").execute().data or []

        total_posts = len(posts)
        total_views = sum(p.get("views", 0) for p in posts)
        total_likes = sum(p.get("likes", 0) for p in posts)

        top_posts = sorted(
            posts,
            key=lambda x: (x.get("views", 0) + x.get("likes", 0)),
            reverse=True
        )[:5]

        category_stats = {}

        for p in posts:
            cat = p.get("category", "unknown")
            category_stats[cat] = category_stats.get(cat, 0) + 1

        return jsonify({
            "total_posts": total_posts,
            "total_views": total_views,
            "total_likes": total_likes,
            "top_posts": top_posts,
            "category_stats": category_stats
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================= EDIT POST =================
@app.route('/edit_post/<int:post_id>', methods=['POST'])
def edit_post(post_id):

    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "unauthorized"}), 403

    try:
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")

        is_featured = True if request.form.get("is_featured") else False
        is_sponsored = True if request.form.get("is_sponsored") else False

        image_file = request.files.get("image")

        update_data = {
            "title": title,
            "description": description,
            "category": category,
            "is_featured": is_featured,
            "is_sponsored": is_sponsored
        }

        # optional image update
        if image_file and image_file.filename:
            upload_result = cloudinary.uploader.upload(image_file)
            update_data["image_url"] = upload_result.get("secure_url")

        supabase.table("posts") \
            .update(update_data) \
            .eq("id", post_id) \
            .execute()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ================= SINGLE POST =================
@app.route('/post/<int:post_id>')
def single_post(post_id):

    response = supabase.table("posts")\
        .select("*")\
        .eq("id", post_id)\
        .execute()

    if not response.data:
        return "Post not found", 404

    post = response.data[0]

    return render_template(
        "single_post.html",
        post=post
    )


# ================= LIKE =================
@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):

    try:
        response = supabase.table("posts")\
            .select("likes")\
            .eq("id", post_id)\
            .execute()

        if not response.data:
            return jsonify({"success": False}), 404

        current = response.data[0]["likes"] or 0

        supabase.table("posts").update({
            "likes": current + 1
        }).eq("id", post_id).execute()

        return jsonify({
            "success": True,
            "likes": current + 1
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


# ================= VIEW =================
@app.route('/view/<int:post_id>', methods=['POST'])
def view_post(post_id):

    try:
        if "viewed_posts" not in session:
            session["viewed_posts"] = []

        response = supabase.table("posts")\
            .select("views,is_sponsored,ad_views")\
            .eq("id", post_id)\
            .execute()

        if not response.data:
            return jsonify({"success": False}), 404

        row = response.data[0]

        current_views = row["views"] or 0
        ad_views = row.get("ad_views", 0) or 0

        if post_id not in session["viewed_posts"]:

            update_data = {
                "views": current_views + 1
            }

            if row.get("is_sponsored"):
                update_data["ad_views"] = ad_views + 1

            supabase.table("posts")\
                .update(update_data)\
                .eq("id", post_id)\
                .execute()

            session["viewed_posts"].append(post_id)
            current_views += 1

        return jsonify({
            "success": True,
            "views": current_views
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


# ================= DELETE POST =================
@app.route('/delete_post/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):

    if not session.get("logged_in"):
        return jsonify({"success": False}), 403

    try:
        supabase.table("posts")\
            .delete()\
            .eq("id", post_id)\
            .execute()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


# ================= CONTACT =================
@app.route('/contact', methods=['GET', 'POST'])
def contact():

    if request.method == "POST":

        firstname = request.form.get("firstname")
        lastname = request.form.get("lastname")
        email = request.form.get("email")
        message = request.form.get("text")

        msg = EmailMessage()
        msg["Subject"] = f"Motteck Contact {firstname} {lastname}"
        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_USER

        msg.set_content(
            f"{firstname} {lastname}\n"
            f"{email}\n\n"
            f"{message}"
        )

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(
                GMAIL_USER,
                GMAIL_APP_PASSWORD
            )
            smtp.send_message(msg)

        return jsonify({"status": "success"})

    return render_template("contact.html")


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)