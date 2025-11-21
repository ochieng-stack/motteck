from flask import Flask, render_template,request, redirect, url_for, session, flash
from flask import Flask, jsonify, request
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from flask import send_from_directory
import json, os

# Initialize Flask app
app = Flask(__name__)
POSTS_FILE = os.path.join(os.path.dirname(__file__),'posts.json')
load_dotenv() # loads Gmail credentials from .env file

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

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
        if username == 'Brian_Ochieng215' and password == 'Ochiengb215@g':
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
    data = request.get_json()

        # Load existing posts
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, 'r') as f:
            posts = json.load(f)
    else:
        posts = []


    new_post = {
        "id": len(posts) + 1,
        "category": data.get('category'),
        "title": data.get('title'),
        "image": data.get('image'),
        "description": data.get('description'),
        "likes": 0
    }

    #Add to list
    posts.append(new_post)

    # save back to file
    with open(POSTS_FILE, 'w') as f:
        json.dump(posts, f, indent=4)

    return jsonify({"success": True})  

# Route to handle likes 
def load_posts():
    with open(POSTS_FILE,'r') as f:
        return json.load(f)   

def save_posts(posts):
    with open(POSTS_FILE,'w') as f:
        json.dump(posts, f, indent=4)


@app.route('/get_posts')
def get_posts():
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, 'r') as f:
            posts = json.load(f)
    else:
        posts = []
    return jsonify(posts)  

@app.route('/posts.json')
def get_posts_json():
    return send_from_directory('.','posts.json')       

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    posts = load_posts()
    #load posts
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, 'r') as f:
            posts = json.load(f)
    else:
        return jsonify({"error": "No posts found"}), 404
    # Find the post by ID
    for post in posts:
        if post["id"] == post_id:
            post["likes"] = post.get("likes", 0) + 1

            # Save updated posts back to posts.json
            with open(POSTS_FILE, 'w') as f:
                json.dump(posts, f, indent=4)
            #Return json response
            return jsonify({"success": True, "likes": post["likes"]})
    # If no post found
    return jsonify({"error": "Post not found"}), 404      
        
@app.route('/like/<int:post_id>')
def get_likes(post_id):
    posts = load_posts()
    for post in posts:
        if int(post['id']) == int(post_id):
            return jsonify({'likes': post.get('likes', 0)})
        return jsonify({'likes': 0})




# delete post
@app.route('/delete_post/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    with open(POSTS_FILE, 'r') as f:
        posts = json.load(f)

    updated_posts = [p for p in posts if p['id'] != post_id]            

    with open(POSTS_FILE, 'w') as f:
        json.dump(updated_posts, f, indent=4)

    return jsonify({"success": True})    

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

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                smtp.send_message(msg)
            return jsonify({'success': 'Message sent successfully!'})
        except Exception as e:
            print("Error sending email:", e)

            return jsonify({'error': 'Failed to send message'}), 500
        
    return render_template ('contact.html')   
                 


# Run app
if __name__ == "__main__" :
    app.run(host="0.0.0.0", port=5000)