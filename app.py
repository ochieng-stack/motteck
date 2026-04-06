from flask import Flask, render_template,request, redirect, url_for, session, flash
from flask import Flask, jsonify, request
import smtplib
import time
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from email.message import EmailMessage
from flask import redirect, url_for
from datetime import datetime
from supabase import create_client
from flask import session
import bcrypt
import requests
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from flask import send_from_directory
import json, os


# Initialize Flask app
app = Flask(__name__)
POSTS_FILE = os.path.join(os.path.dirname(__file__),'posts.json')
load_dotenv() # loads Gmail credentials from .env file

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

#cloudinary setup
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

#supabase setup
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)



app.secret_key = 'motteck_super_secret_key'

CONTACT_FILE = 'contacts.json'

# ---- Routes ----

# Homepage
@app.route('/')
@app.route('/home')
def home():
    logged_in = session.get('logged_in', False)
    return render_template('index.html', logged_in=logged_in)

# all pages
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    logged_in = session.get('logged_in', False)
    return render_template('services.html',logged_in=logged_in, active_page='services')


@app.route('/cars')
def cars():
    logged_in = session.get('logged_in', False)
    return render_template('cars.html',logged_in=logged_in, active_page='cars')

@app.route('/trucks')
def trucks():
    logged_in = session.get('logged_in', False)
    return render_template('trucks.html',logged_in=logged_in, active_page='trucks')

@app.route('/motobikes')
def motobikes():
    logged_in = session.get('logged_in', False)
    return render_template('motobikes.html',logged_in=logged_in, active_page='motobikes')

@app.route('/trains')
def trains():
    logged_in = session.get('logged_in', False)
    return render_template('trains.html',logged_in=logged_in, active_page='trains')

@app.route('/plane')
def plane():
    logged_in = session.get('logged_in', False)
    return render_template('plane.html',logged_in=logged_in, active_page='plane')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/Terms')
def Terms():
    return render_template('Terms.html')


# Admin login page

# Rate limiter
limiter = Limiter(get_remote_address, app=app)

# Example admin credentials (hashed password)
ADMIN_USER = "admin"
# Generate once: bcrypt.hashpw("yourpassword".encode(), bcrypt.gensalt())
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH").encode()

# Track failed login attempts
FAILED_ATTEMPTS = {}
LOCK_TIME = 600  # seconds (10 minutes)

# reCAPTCHA secret key
RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")

def verify_recaptcha(token):
    response = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={"secret": RECAPTCHA_SECRET, "response": token}
    )
    return response.json().get("success", False)

@app.route('/login-goodwill254@', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # max 5 attempts per minute per IP
def login():
    ip = get_remote_address()

    # Check lockout
    if ip in FAILED_ATTEMPTS and FAILED_ATTEMPTS[ip]['locked_until'] > time.time():
        return render_template('admin.html', error="Too many failed attempts. Try again later.")

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        recaptcha_token = request.form.get("g-recaptcha-response")

        # Verify reCAPTCHA
        if not verify_recaptcha(recaptcha_token):
            return render_template('admin.html', error="reCAPTCHA verification failed.")

        # Check credentials
        if username == ADMIN_USER and bcrypt.checkpw(password.encode(), ADMIN_PASS_HASH):
            session['logged_in'] = True
            if ip in FAILED_ATTEMPTS:
                FAILED_ATTEMPTS.pop(ip)  # reset attempts after successful login
            return redirect(url_for('home'))
        else:
            # Track failed attempts
            if ip not in FAILED_ATTEMPTS:
                FAILED_ATTEMPTS[ip] = {'count': 1, 'locked_until': 0}
            else:
                FAILED_ATTEMPTS[ip]['count'] += 1
                if FAILED_ATTEMPTS[ip]['count'] >= 5:
                    FAILED_ATTEMPTS[ip]['locked_until'] = time.time() + LOCK_TIME
            return render_template('admin.html', error="Invalid username or password")

    return render_template('admin.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

from flask import jsonify

@app.route("/get_home_posts")
def get_home_posts():
    try:
        all_posts = supabase.table("posts").select("*").execute().data or []

        if not all_posts:
            return jsonify({"trending": [], "recent": []})

        # Sort all posts by likes descending
        sorted_by_likes = sorted(all_posts, key=lambda x: x.get("likes", 0), reverse=True)

        # Top 6 are trending
        trending = sorted_by_likes[:6]
        trending_ids = {post["id"] for post in trending}

        # Remaining posts go to recent, sorted by created_at descending
        recent = [post for post in all_posts if post["id"] not in trending_ids]
        recent.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return jsonify({"trending": trending, "recent": recent})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

#create post
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
        "created_at": datetime.utcnow().isoformat()
    }

    response = supabase.table("posts").insert(new_post).execute()

    if response.data:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False})

#get post
@app.route('/get_posts')
def get_posts():
    response = (
        supabase
        .table("posts")
        .select("*")
        .order("id", desc=True)
        .execute()
    )

    if response.data:
        return jsonify(response.data)
    else:
        return jsonify([]), 500
    
# like post
@app.route('/like/<int:post_id>', methods=['POST', 'GET'])
def like_post(post_id):
    try:
        # GET → return current likes
        if request.method == "GET":
            response = supabase.table("posts").select("likes").eq("id", post_id).execute()

            if response.data:
                return jsonify({"likes": response.data[0]["likes"] or 0})
            return jsonify({"likes": 0})

        # POST → increment likes
        response = supabase.table("posts").select("likes").eq("id", post_id).execute()

        if not response.data:
            return jsonify({"success": False, "error": "Post not found"}), 404

        current_likes = response.data[0]["likes"] or 0

        supabase.table("posts").update({
            "likes": current_likes + 1
        }).eq("id", post_id).execute()

        return jsonify({
            "success": True,
            "likes": current_likes + 1
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route('/post/<int:post_id>')
def single_post(post_id):
    try:
        response = supabase.table("posts").select("*").eq("id", post_id).execute()

        if not response.data:
            return "Post not found", 404

        post = response.data[0]

        return render_template("single_post.html", post=post)

    except Exception as e:
        return f"Error: {str(e)}", 500
       
   # View post 
@app.route('/view/<int:post_id>', methods=['POST'])
def view_post(post_id):
    try:
        if 'viewed_posts' not in session:
            session['viewed_posts'] = []

        response = supabase.table("posts").select("views").eq("id", post_id).execute()

        if not response.data:
            return jsonify({"success": False}), 404

        current_views = response.data[0]["views"] or 0

        # Only increment if not viewed this session
        if post_id not in session['viewed_posts']:
            supabase.table("posts").update({
                "views": current_views + 1
            }).eq("id", post_id).execute()

            session['viewed_posts'].append(post_id)
            current_views += 1  # reflect increment

        return jsonify({
            "success": True,
            "views": current_views
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
# delete post
@app.route('/delete_post/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    try:
        response = supabase.table("posts").delete().eq("id", post_id).execute()
        if response.error:
            return jsonify({"error": response.error}), 500
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}),500  
    
#contact form
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        try:
            firstname = request.form.get('firstname')
            lastname = request.form.get('lastname')
            email = request.form.get('email')
            message = request.form.get('text')

            # Validate fields
            if not all([firstname, lastname, email, message]):
                return jsonify({'error': 'Please fill out all fields'}), 400

            msg = EmailMessage()
            msg['Subject'] = f'Motteck Contact {firstname} {lastname}'
            msg['From'] = GMAIL_USER
            msg['To'] = GMAIL_USER
            msg.set_content(
                f"Name: {firstname} {lastname}\nEmail: {email}\nMessage: {message}"
            )

            with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                smtp.starttls()
                smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                smtp.send_message(msg)

            return jsonify({'success': 'Message sent successfully!'})

        except Exception as e:
            print("Contact form error:", e)
            return jsonify({'error': 'Server error sending message'}), 500

    return render_template('contact.html')
                 


# Run app
if __name__ == "__main__" :
    app.run(host="0.0.0.0", port=5000)