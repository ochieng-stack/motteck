from flask import Flask, render_template,request, redirect, url_for, session, flash
from flask import Flask, jsonify, request
import smtplib
import time
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials,firestore, storage
from email.message import EmailMessage

from flask import send_from_directory
import json, os
from firebase_admin import storage

# Initialize Flask app
app = Flask(__name__)
POSTS_FILE = os.path.join(os.path.dirname(__file__),'posts.json')
load_dotenv() # loads Gmail credentials from .env file

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

#firebase setup
firebase_key_raw = os.getenv("FIREBASE_KEY")
if not firebase_key_raw:
    raise Exception("FIREBASE_KEY not found in environment")

firebase_key = json.loads(firebase_key_raw)

cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred, { "storageBucket": "motteck-f5aa2.appspot.com"})

bucket = storage.bucket()
db = firestore.client()



app.secret_key = 'motteck_super_secret_key'

CONTACT_FILE = 'contacts.json'

# ---- Routes ----

# Homepage
@app.route('/')
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
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']               

        #Replace this with your real admin credentials
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['logged_in'] = True      
            return redirect(url_for('home'))            
        else:
            return render_template('admin.html', error="Invalid username or password")

    return render_template('admin.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

#create post
@app.route('/add_post' , methods=['POST'])
def add_post():
    category = request.form.get('category')
    title = request.form.get('title')
    image = request.files.get('image')
    description = request.form.get('description')
    
    # UPLOAD FILE TO FIREBASE STORAGE
    image_url = None
    if image and image.filename != "":
     bucket = storage.bucket()
    blob  = bucket.blob(f"posts/{image.filename}")
    blob.upload_from_file(image, content_type=image.content_type)
    blob.make_public()
    image_url = blob.public_url

    new_post = {
        "category": category,
        "title": title,
        "image": image_url,
        "description": description,
        "likes": 0,
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    # save to firestore
    db.collection("posts").add(new_post)

    return jsonify({"success": True})


@app.route('/get_posts')
def get_posts():
    posts_ref = db.collection("posts").order_by("timestamp", direction=firestore.Query.DESCENDING)
    docs = posts_ref.stream()

    posts = []
    for doc in docs:
        post = doc.to_dict()
        post["id"] = doc.id # firestore document ID
        posts.append(post)

    return jsonify(posts)  

@app.route('/posts.json')
def get_posts_json():
    return send_from_directory('.','posts.json')       

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    try:
        post_ref = db.collection("posts") .document(post_id)
        post = post_ref.get()

        if not post.exists:
            return jsonify({"error": "Post not found"}), 404
        
        # get current likes
        current_likes = post.to_dict().get("likes", 0)

        # Increment likes
        post_ref.update({"likes": current_likes + 1})

        return jsonify({"success": True, "likes": current_likes + 1})
    
    except Exception as e:
        return jsonify({"error": str(e)}),500

# delete post
@app.route('/delete_post/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    try:
        post_ref = db.collection('posts').document(post_id)
        post_ref.delete()

        return jsonify({"success": True})
    except Exception as e:

        return jsonify({"error": str(e)}), 500   

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        email = request.form.get('email')
        message = request.form.get('text')
        # Validate fields
        if not all([firstname, lastname, email, message]):
            return jsonify({'error': 'please fill out all fields'}), 400
        
        # Create the email content
        msg = EmailMessage()
        msg['Subject'] = f'Contact form message from {firstname} {lastname}'
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER # send to yourself
        msg.set_content(f""" Name: {firstname} {lastname} Email: {email} message: {message}""")

        for attempt in range(3):
            try:
                with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                    smtp.starttls()
                    smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                    smtp.send_message(msg)
                return jsonify({'success': 'Message sent successfully!'})
            except Exception as e:
                print(f"Email send error(attempt {attempt+1}):", e)
                time.sleep(2)

            return jsonify({'error': 'Failed to send message'}), 500
        
    return render_template ('contact.html')   
                 


# Run app
if __name__ == "__main__" :
    app.run(host="0.0.0.0", port=5000)