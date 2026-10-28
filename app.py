from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import time
import resend
import random
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from email.message import EmailMessage
from flask import flash
from supabase import AuthApiError
import uuid
from urllib.parse import quote
import boto3


from supabase import create_client

import bcrypt
import requests

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address



# ================= INIT =================
app = Flask(__name__)
app.secret_key = 'motteck_super_secret_key'

load_dotenv()




# ================= CLOUDFLARE R2 =================
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "motteck-images")
R2_ENDPOINT = os.environ.get("R2_ENDPOINT")

r2_client = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto"
)

# ================= SUPABASE =================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ================= EMAIL =================
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
resend.api_key = RESEND_API_KEY

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

# ================= USER REGISTRATION =================
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        # ================= BASIC ACCOUNT INFORMATION =================

        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        account_type = request.form.get("account_type", "").strip().lower()


        # ================= BUSINESS INFORMATION =================
        # These fields will only be used when account_type == "business"

        business_name = request.form.get("business_name", "").strip()
        business_category = request.form.get("business_category", "").strip()
        business_representative = request.form.get(
            "business_representative", ""
        ).strip()
        business_phone = request.form.get("business_phone", "").strip()
        business_location = request.form.get("business_location", "").strip()
        business_town = request.form.get("business_town", "").strip()
        business_description = request.form.get(
            "business_description", ""
        ).strip()
        business_years = request.form.get("business_years", "").strip()
        business_website = request.form.get(
            "business_website", ""
        ).strip()
        business_social_media = request.form.get(
            "business_social_media", ""
        ).strip()


        # ================= BASIC VALIDATION =================

        if not full_name or not email or not password or not confirm_password:

            flash(
                "Please fill in all required fields.",
                "error"
            )

            return redirect(url_for("register"))


        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return redirect(url_for("register"))


        if len(password) < 6:

            flash(
                "Your password must be at least 6 characters long.",
                "error"
            )

            return redirect(url_for("register"))


        if account_type not in ["individual", "business"]:

            flash(
                "Please choose an account type.",
                "error"
            )

            return redirect(url_for("register"))


        # ================= BUSINESS VALIDATION =================

        if account_type == "business":

            if not business_name:
                flash(
                    "Please enter your business name.",
                    "error"
                )
                return redirect(url_for("register"))


            if not business_category:
                flash(
                    "Please choose your business category.",
                    "error"
                )
                return redirect(url_for("register"))


            if not business_representative:
                flash(
                    "Please enter the business owner or representative.",
                    "error"
                )
                return redirect(url_for("register"))


            if not business_phone:
                flash(
                    "Please enter your business phone number.",
                    "error"
                )
                return redirect(url_for("register"))


            if not business_location:
                flash(
                    "Please enter your physical business location.",
                    "error"
                )
                return redirect(url_for("register"))


            if not business_town:
                flash(
                    "Please enter your town or city.",
                    "error"
                )
                return redirect(url_for("register"))


            if not business_description:
                flash(
                    "Please describe your business.",
                    "error"
                )
                return redirect(url_for("register"))


            if not business_years:
                flash(
                    "Please tell us how long the business has operated.",
                    "error"
                )
                return redirect(url_for("register"))


        try:

            # ================= CREATE AUTH USER =================

            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_redirect_to": url_for("login_user", _external=True)
                }
            })

            user = auth_response.user


            if not user:

                flash(
                    "We couldn't create your account. Please try again.",
                    "error"
                )

                return redirect(url_for("register"))


            # ================= CREATE PROFILE =================

            profile_data = {
                "id": user.id,
                "full_name": full_name,
                "account_type": account_type,

                # Every new account starts unverified.
                # Individual accounts do not require verification,
                # while business accounts can be manually verified later.
                "is_verified": False
            }


            # ================= ADD BUSINESS DATA =================

            if account_type == "business":

                profile_data.update({

                    "business_name": business_name,
                    "business_category": business_category,
                    "business_representative": business_representative,
                    "business_phone": business_phone,
                    "business_location": business_location,
                    "business_town": business_town,
                    "business_description": business_description,
                    "business_years": business_years,
                    "business_website": business_website or None,
                    "business_social_media": business_social_media or None

                })


            # ================= SAVE PROFILE =================

            profile_response = supabase.table(
                "profiles"
            ).insert(profile_data).execute()


            if not profile_response.data:

                flash(
                    "Your account could not be completed. Please try again.",
                    "error"
                )

                return redirect(url_for("register"))


            # ================= SUCCESS =================

            if account_type == "business":

                flash(
                    "Business account created successfully! "
                    "Your account is pending verification. "
                    "Please check your email to verify your account.",
                    "success"
                )

            else:

                flash(
                    "Account created successfully! "
                    "Please check your email to verify your account.",
                    "success"
                )


            return redirect(url_for("login_user"))


        except Exception as e:

            # Technical error goes to Render logs,
            # NOT directly to the user.

            print("REGISTRATION ERROR:", str(e))

            error_message = str(e).lower()


            # ================= DUPLICATE EMAIL =================

            if (
                "already registered" in error_message
                or "already exists" in error_message
                or "user_already_exists" in error_message
            ):

                flash(
                    "An account with this email already exists. "
                    "Please log in instead.",
                    "error"
                )


            else:

                flash(
                    "We couldn't create your account right now. "
                    "Please try again.",
                    "error"
                )


            return redirect(url_for("register"))


    return render_template("register.html")

# ================= USER LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login_user():

    if request.method == "POST":

        login = request.form.get("login", "").strip().lower()
        password = request.form.get("password", "")

        if not login or not password:
            flash("Please enter your email and password.", "error")
            return render_template("login.html")

        # ================= AUTHENTICATION =================

        try:

            response = supabase.auth.sign_in_with_password({
                "email": login,
                "password": password
            })

        except Exception as e:

            print("LOGIN AUTH ERROR:", repr(e))

            flash(
                "Invalid email or password.",
                "error"
            )

            return render_template("login.html")


        user = response.user

        if not user:

            flash(
                "Unable to sign you in. Please try again.",
                "error"
            )

            return render_template("login.html")


        # ================= GET PROFILE =================

        try:

            profile_response = supabase.table("profiles") \
                .select("*") \
                .eq("id", user.id) \
                .execute()

            profile_data = profile_response.data

            if not profile_data:

                print(
                    "LOGIN PROFILE ERROR: "
                    f"No profile found for user {user.id}"
                )

                # The authentication succeeded, but the MOTTECK
                # profile does not exist.

                flash(
                    "Your account was authenticated, but your MOTTECK "
                    "profile could not be found. Please contact support.",
                    "error"
                )

                return render_template("login.html")


            profile = profile_data[0]


        except Exception as e:

            print("LOGIN PROFILE ERROR:", repr(e))

            flash(
                "We couldn't load your MOTTECK profile. "
                "Please try again.",
                "error"
            )

            return render_template("login.html")


        # ================= CREATE LOGIN SESSION =================

        session["user_logged_in"] = True
        session["user_id"] = user.id
        session["email"] = user.email
        session["full_name"] = profile.get("full_name")
        session["account_type"] = profile.get("account_type")

        flash("Welcome back!", "success")

        return redirect(url_for("home"))


    return render_template("login.html")


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
# =========================================================
# ADMIN - LOAD PENDING SUBMISSIONS
# =========================================================

@app.route("/admin/submissions")
def admin_submissions():
    if not session.get("logged_in"):
        return jsonify({
            "error": "Unauthorized"
        }), 403

    try:
        response = (
            supabase
            .table("post_submissions")
            .select("*")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )

        submissions = response.data or []

        # Get submitter information
        for submission in submissions:

            user_id = submission.get("user_id")

            if user_id:
                try:
                    profile_response = (
                        supabase
                        .table("profiles")
                        .select("full_name,email")
                        .eq("id", user_id)
                        .single()
                        .execute()
                    )

                    profile = profile_response.data or {}

                    submission["submitter_name"] = (
                        profile.get("full_name")
                        or "Unknown user"
                    )

                    submission["submitter_email"] = (
                        profile.get("email")
                        or "Not available"
                    )

                except Exception:
                    submission["submitter_name"] = "Unknown user"
                    submission["submitter_email"] = "Not available"

            else:
                submission["submitter_name"] = "Unknown user"
                submission["submitter_email"] = "Not available"

        return jsonify({
            "success": True,
            "submissions": submissions
        })

    except Exception as e:
        print("ADMIN SUBMISSIONS ERROR:", e)

        return jsonify({
            "error": str(e)
        }), 500
# =========================================================
# ADMIN - MOTTECK LEADS
# =========================================================

@app.route("/admin/leads")
def admin_leads():

    if not session.get("logged_in"):

        return jsonify({
            "error": "Unauthorized"
        }), 403

    try:

        # =========================================
        # GET LEADS
        # =========================================

        response = (
            supabase
            .table("leads")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        leads = response.data or []

        # =========================================
        # ENRICH LEADS
        # =========================================

        for lead in leads:

            # -------------------------------------
            # GET POST
            # -------------------------------------

            post_id = lead.get("post_id")

            if post_id:

                try:

                    post_response = (
                        supabase
                        .table("posts")
                        .select(
                            "id,title,user_id"
                        )
                        .eq("id", post_id)
                        .single()
                        .execute()
                    )

                    post = (
                        post_response.data
                        or {}
                    )

                    lead["post_title"] = (
                        post.get("title")
                        or "Untitled post"
                    )

                except Exception:

                    lead["post_title"] = (
                        "Post unavailable"
                    )

            else:

                lead["post_title"] = (
                    "Unknown post"
                )

            # -------------------------------------
            # SELLER / BUSINESS
            # -------------------------------------

            seller_id = lead.get(
                "seller_id"
            )

            if seller_id:

                try:

                    seller_response = (
                        supabase
                        .table("profiles")
                        .select(
                            "id,full_name,email,"
                            "account_type,business_name"
                        )
                        .eq("id", seller_id)
                        .single()
                        .execute()
                    )

                    seller = (
                        seller_response.data
                        or {}
                    )

                    lead["seller_name"] = (
                        seller.get("business_name")
                        or seller.get("full_name")
                        or "Unknown seller"
                    )

                    lead["seller_email"] = (
                        seller.get("email")
                        or ""
                    )

                    lead["seller_account_type"] = (
                        seller.get("account_type")
                        or "individual"
                    )

                except Exception:

                    lead["seller_name"] = (
                        "Unknown seller"
                    )

                    lead["seller_email"] = ""
                    lead["seller_account_type"] = ""

            else:

                lead["seller_name"] = (
                    "Unknown seller"
                )

                lead["seller_email"] = ""
                lead["seller_account_type"] = ""

            # -------------------------------------
            # INTERESTED USER
            # -------------------------------------

            interested_user_id = lead.get(
                "interested_user_id"
            )

            if interested_user_id:

                try:

                    interested_response = (
                        supabase
                        .table("profiles")
                        .select(
                            "id,full_name,email,"
                            "account_type"
                        )
                        .eq(
                            "id",
                            interested_user_id
                        )
                        .single()
                        .execute()
                    )

                    interested_user = (
                        interested_response.data
                        or {}
                    )

                    lead["interested_user_name"] = (
                        interested_user.get(
                            "full_name"
                        )
                        or "Unknown user"
                    )

                    lead["interested_user_email"] = (
                        interested_user.get(
                            "email"
                        )
                        or ""
                    )

                except Exception:

                    lead["interested_user_name"] = (
                        "Unknown user"
                    )

                    lead["interested_user_email"] = ""

            else:

                lead["interested_user_name"] = (
                    "Unknown user"
                )

                lead["interested_user_email"] = ""

        # =========================================
        # SUMMARY
        # =========================================

        total = len(leads)

        seller_leads = sum(
            1
            for lead in leads
            if lead.get("lead_type")
            == "contact_seller"
        )

        business_leads = sum(
            1
            for lead in leads
            if lead.get("lead_type")
            == "contact_business"
        )

        motteck_requests = sum(
            1
            for lead in leads
            if lead.get("lead_type")
            == "request_motteck"
        )

        new_leads = sum(
            1
            for lead in leads
            if lead.get("status", "new")
            == "new"
        )

        return jsonify({

            "success": True,

            "leads": leads,

            "summary": {

                "total": total,

                "contact_seller":
                    seller_leads,

                "contact_business":
                    business_leads,

                "request_motteck":
                    motteck_requests,

                "new":
                    new_leads
            }
        })

    except Exception as e:

        print(
            "ADMIN LEADS ERROR:",
            repr(e)
        )

        return jsonify({
            "error": str(e)
        }), 500

# =========================================================
# ADMIN - UPDATE LEAD STATUS
# =========================================================

@app.route(
    "/admin/leads/<int:lead_id>/status",
    methods=["POST"]
)
def update_lead_status(lead_id):

    if not session.get("logged_in"):

        return jsonify({
            "success": False,
            "error": "Unauthorized"
        }), 403

    try:

        data = request.get_json(
            silent=True
        ) or {}

        status = (
            data.get("status")
            or ""
        ).strip().lower()

        allowed_statuses = [
            "new",
            "contacted",
            "converted",
            "closed"
        ]

        if status not in allowed_statuses:

            return jsonify({
                "success": False,
                "error": "Invalid lead status."
            }), 400

        response = (
            supabase
            .table("leads")
            .update({
                "status": status
            })
            .eq("id", lead_id)
            .execute()
        )

        if not response.data:

            return jsonify({
                "success": False,
                "error": "Lead not found."
            }), 404

        return jsonify({
            "success": True,
            "message": "Lead status updated."
        })

    except Exception as e:

        print(
            "UPDATE LEAD STATUS ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
# ================= ADMIN: APPROVE SUBMISSION =================

@app.route(
    "/admin/submissions/<int:submission_id>/approve",
    methods=["POST"]
)
def approve_submission(submission_id):

    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        result = (
            supabase.table("post_submissions")
            .select("*")
            .eq("id", submission_id)
            .single()
            .execute()
        )

        submission = result.data

        if not submission:
            return jsonify({
                "success": False,
                "error": "Submission not found."
            }), 404

        if submission.get("status") != "pending":
            return jsonify({
                "success": False,
                "error": "This submission has already been processed."
            }), 400

        post_type = submission.get("post_type") or "normal"
        is_sponsored = post_type == "sponsored"
        is_featured = post_type == "featured"

        images = submission.get("image_urls") or []
        if not isinstance(images, list):
            images = []

        # Calculate promotion expiry correctly.
        sponsored_until = None

        if is_sponsored:
            duration = submission.get("promotion_duration")

            duration_days = {
                "24_hours": 1,
                "3_days": 3,
                "7_days": 7,
                "1_month": 30
            }.get(duration)

            if duration_days:
                sponsored_until = (
                    datetime.utcnow() + timedelta(days=duration_days)
                ).isoformat()

        post_data = {
            "user_id": submission.get("user_id"),
            "title": submission.get("title"),
            "category": submission.get("category"),
            "description": submission.get("description"),
            "image_url": images[0] if images else None,
            "post_type": post_type,
            "sale_method": submission.get("sale_method"),
            "listing_duration": submission.get("listing_duration"),
            "commission_agreed": submission.get("commission_agreed") or False,
            "likes": 0,
            "views": 0,
            "is_featured": is_featured,
            "is_sponsored": is_sponsored,
            "sponsored_until": sponsored_until,
            "ad_clicks": 0,
            "ad_views": 0,
            "ad_earnings": 0
        }

        # Transfer extra fields added by the submission form.
        extra_fields = (
            "price",
            "vehicle_type",
            "year",
            "mileage",
            "condition",
            "product_name",
            "brand",
            "part_number",
            "compatibility",
            "location"
        )

        for field in extra_fields:
            if field in submission:
                post_data[field] = submission[field]

        # Publish the post first.
        published = (
            supabase.table("posts")
            .insert(post_data)
            .execute()
        )

        if not published.data:
            return jsonify({
                "success": False,
                "error": "Unable to publish the post."
            }), 500

        # Mark the submission approved only after publishing succeeds.
        supabase.table("post_submissions").update({
            "status": "approved"
        }).eq("id", submission_id).execute()

        return jsonify({
            "success": True,
            "message": "Post approved and published.",
            "post": published.data[0]
        })

    except Exception as e:
        print("APPROVE SUBMISSION ERROR:", repr(e))
        return jsonify({
            "success": False,
            "error": "Unable to approve this submission. Check the server logs."
        }), 500

# =========================================================
# ADMIN - REJECT SUBMISSION
# =========================================================

@app.route(
    "/admin/submissions/<int:submission_id>/reject",
    methods=["POST"]
)
def reject_submission(submission_id):

    if not session.get("logged_in"):
        return jsonify({
            "error": "Unauthorized"
        }), 403

    try:

        # Make sure submission exists
        response = (
            supabase
            .table("post_submissions")
            .select("id,status")
            .eq("id", submission_id)
            .single()
            .execute()
        )

        submission = response.data

        if not submission:
            return jsonify({
                "error": "Submission not found."
            }), 404

        if submission.get("status") != "pending":
            return jsonify({
                "error": "This submission has already been processed."
            }), 400

        # Mark as rejected
        (
            supabase
            .table("post_submissions")
            .update({
                "status": "rejected"
            })
            .eq("id", submission_id)
            .execute()
        )

        return jsonify({
            "success": True,
            "message": "Submission rejected."
        })

    except Exception as e:

        print(
            "REJECT SUBMISSION ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500
    
# ================= HOME =================
@app.route('/')
@app.route('/home')
def home():
    return render_template(
        'index.html',
        logged_in=session.get('user_logged_in', False),
        full_name=session.get("full_name")
    )

    
# ================= USER LOGOUT =================
@app.route("/user/logout")
def user_logout():

    supabase.auth.sign_out()

    session.pop("user_logged_in", None)
    session.pop("user_id", None)
    session.pop("email", None)
    session.pop("full_name", None)
    session.pop("account_type", None)

    flash("You have been logged out.", "success")

    return redirect(url_for("home"))


# ================= USER PROFILE =================
@app.route("/profile")
def profile():

    if not session.get("user_logged_in"):
        flash("Please log in first.", "error")
        return redirect(url_for("login_user"))

    user_id = session.get("user_id")

    try:

        # ================= GET PROFILE =================

        profile_response = (
            supabase
            .table("profiles")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        profile_data = (
            profile_response.data[0]
            if profile_response.data
            else {}
        )

        # ================= COUNT POSTS =================

        posts_response = (
            supabase
            .table("posts")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )

        posts_count = (
            len(posts_response.data)
            if posts_response.data
            else 0
        )

        # ================= COUNT FOLLOWERS =================

        followers_response = (
            supabase
            .table("follows")
            .select("id")
            .eq("following_id", user_id)
            .execute()
        )

        followers_count = (
            len(followers_response.data)
            if followers_response.data
            else 0
        )

        # ================= COUNT FOLLOWING =================

        following_response = (
            supabase
            .table("follows")
            .select("id")
            .eq("follower_id", user_id)
            .execute()
        )

        following_count = (
            len(following_response.data)
            if following_response.data
            else 0
        )

        # ================= PROFILE INFORMATION =================

        full_name = (
            profile_data.get("full_name")
            or session.get("full_name")
            or "MOTTECK User"
        )

        email = (
            session.get("email")
            or ""
        )

        account_type = (
            profile_data.get("account_type")
            or session.get("account_type")
            or "individual"
        )

        profile_picture = profile_data.get(
            "profile_image"
        )

        return render_template(
            "profile.html",

            full_name=full_name,

            email=email,

            account_type=account_type,

            profile_picture=profile_picture,

            posts_count=posts_count,

            followers_count=followers_count,

            following_count=following_count
        )

    except Exception as e:

        print(
            "PROFILE PAGE ERROR:",
            repr(e)
        )

        flash(
            "We couldn't load your profile right now.",
            "error"
        )

        return redirect(url_for("home"))
# ================= PUBLIC PROFILE =================
@app.route('/profile/<user_id>')
def public_profile(user_id):
    try:
        # =========================================
        # GET PROFILE
        # =========================================
        profile_response = (
            supabase
            .table("profiles")
            .select("*")
            .eq("id", user_id)
            .execute()
        )

        if not profile_response.data:
            return "Profile not found", 404

        profile = profile_response.data[0]

        # =========================================
        # GET USER POSTS
        # =========================================
        posts_response = (
            supabase
            .table("posts")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        all_posts = posts_response.data or []

        # =========================================
        # ONLY SHOW ACTIVE LISTINGS
        # =========================================
        from datetime import datetime, timezone

        active_posts = []

        for post in all_posts:

            # -----------------------------------------
            # SPARE PARTS STAY ACTIVE
            # -----------------------------------------
            if post.get("category") == "spare_part":
                active_posts.append(post)
                continue

            # -----------------------------------------
            # NO LISTING DURATION = ACTIVE
            # -----------------------------------------
            listing_duration = post.get("listing_duration")

            if not listing_duration:
                active_posts.append(post)
                continue

            # -----------------------------------------
            # CALCULATE EXPIRY
            # -----------------------------------------
            created_at = post.get("created_at")

            if not created_at:
                active_posts.append(post)
                continue

            try:
                created_dt = datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                )

                now = datetime.now(timezone.utc)

                if listing_duration == "1_day":
                    expiry_seconds = 24 * 60 * 60

                elif listing_duration == "1_week":
                    expiry_seconds = 7 * 24 * 60 * 60

                elif listing_duration == "1_month":
                    expiry_seconds = 30 * 24 * 60 * 60

                else:
                    # Unknown duration — keep visible
                    active_posts.append(post)
                    continue

                expiry_time = created_dt.timestamp() + expiry_seconds

                if now.timestamp() < expiry_time:
                    active_posts.append(post)

            except Exception:
                # If the date cannot be read, don't accidentally hide
                # the listing.
                active_posts.append(post)

        # =========================================
        # ENRICH POSTS WITH PROFILE INFORMATION
        # =========================================
        viewer_id = session.get("user_id")

        active_posts = enrich_posts_with_profiles(
            active_posts,
            viewer_id
        )

        # =========================================
        # FOLLOWER COUNT
        # =========================================
        followers_response = (
            supabase
            .table("follows")
            .select("id", count="exact")
            .eq("following_id", user_id)
            .execute()
        )

        followers_count = followers_response.count or 0

        # =========================================
        # FOLLOWING COUNT
        # =========================================
        following_response = (
            supabase
            .table("follows")
            .select("id", count="exact")
            .eq("follower_id", user_id)
            .execute()
        )

        following_count = following_response.count or 0

        # =========================================
        # CHECK IF CURRENT VIEWER FOLLOWS THIS USER
        # =========================================
        is_following = False

        if viewer_id and str(viewer_id) != str(user_id):

            follow_response = (
                supabase
                .table("follows")
                .select("id")
                .eq("follower_id", viewer_id)
                .eq("following_id", user_id)
                .execute()
            )

            is_following = bool(follow_response.data)

        # =========================================
        # DISPLAY NAME
        # =========================================
        if (
            profile.get("account_type") == "business"
            and profile.get("business_name")
        ):
            display_name = profile.get("business_name")

        else:
            display_name = (
                profile.get("full_name")
                or "MOTTECK User"
            )

        # =========================================
        # RENDER PUBLIC PROFILE
        # =========================================
        return render_template(
            "public_profile.html",
            profile=profile,
            display_name=display_name,
            posts=active_posts,
            posts_count=len(active_posts),
            followers_count=followers_count,
            following_count=following_count,
            is_following=is_following,
            viewer_id=viewer_id
        )

    except Exception as e:
        print("PUBLIC PROFILE ERROR:", repr(e))
        return "Unable to load profile", 500
        
# ================= PROFILE PHOTO UPLOAD =================

@app.route("/upload-profile-picture", methods=["POST"])
def upload_profile_picture():

    # User must be logged in
    if not session.get("user_logged_in") or not session.get("user_id"):
        flash("Please log in first.", "error")
        return redirect(url_for("login_user"))

    user_id = session.get("user_id")
    profile_photo = request.files.get("profile_photo")

    # Make sure a file was selected
    if not profile_photo or not profile_photo.filename:
        flash("Please choose a profile photo.", "error")
        return redirect(url_for("profile"))

    # Allowed image extensions
    allowed_extensions = {"jpg", "jpeg", "png", "webp"}
    filename = profile_photo.filename.lower()

    if "." not in filename:
        flash("Invalid image file.", "error")
        return redirect(url_for("profile"))

    extension = filename.rsplit(".", 1)[1]

    if extension not in allowed_extensions:
        flash(
            "Please upload a JPG, JPEG, PNG or WEBP image.",
            "error"
        )
        return redirect(url_for("profile"))

    try:
        # ================= CLOUDFLARE R2 UPLOAD =================

        profile_photo.seek(0)

        profile_image_key = (
            f"motteck/profiles/{uuid.uuid4().hex}.{extension}"
        )

        content_type = (
            profile_photo.mimetype or "image/jpeg"
        )

        r2_client.upload_fileobj(
            profile_photo,
            R2_BUCKET_NAME,
            profile_image_key,
            ExtraArgs={"ContentType": content_type}
        )

        # Build the publicly accessible image URL
        public_base_url = os.environ.get(
            "R2_PUBLIC_BASE_URL", ""
        ).rstrip("/")

        if not public_base_url:
            app.logger.error(
                "R2_PUBLIC_BASE_URL is missing from environment variables."
            )
            flash(
                "Photo storage is not fully configured. Please contact support.",
                "error"
            )
            return redirect(url_for("profile"))

        profile_image_url = (
            f"{public_base_url}/{profile_image_key}"
        )

        # ================= SAVE TO PROFILE =================

        update_response = (
            supabase
            .table("profiles")
            .update({
                "profile_image": profile_image_url
            })
            .eq("id", user_id)
            .execute()
        )

        if not update_response.data:
            app.logger.error(
                "Profile photo database update returned no rows for user %s",
                user_id
            )

            flash(
                "Your photo uploaded but could not be saved to your profile.",
                "error"
            )
            return redirect(url_for("profile"))

        flash(
            "Your profile photo has been updated successfully!",
            "success"
        )

        return redirect(url_for("profile"))

    except Exception:
        app.logger.exception("Cloudflare R2 profile photo upload failed")

        flash(
            "We couldn't update your profile photo. Please try again.",
            "error"
        )

        return redirect(url_for("profile"))

    
# ================= USER SETTINGS =================
@app.route("/settings")
def settings():

    if not session.get("user_logged_in"):
        flash("Please log in first.", "error")
        return redirect(url_for("login_user"))

    return render_template(
        "settings.html",
        full_name=session.get("full_name"),
        email=session.get("email"),
        account_type=session.get("account_type")
    )

# ================= STATIC PAGES =================
@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/spare_part')
def spare_part():
    return render_template(
        'spare_part.html',
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


@app.route('/accessorie')
def accessorie():
    return render_template(
        'accessorie.html',
        logged_in=session.get('logged_in', False)
    )


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/term')
def term():
    return render_template('term.html')

@app.route('/partner_with_us')
def partner_with_us():
    return render_template('partner_with_us.html')


@app.route('/advertise')
def advertise():
    return render_template('advertise.html')


@app.route('/cookies')
def cookies():
    return render_template('cookies.html')

@app.route("/payment-success")
# ================= ADMIN LOGIN =================
@app.route('/login-goodwill254@', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():

    ip = get_remote_address()

    if ip in FAILED_ATTEMPTS:
        if FAILED_ATTEMPTS[ip]["locked_until"] > time.time():
            return render_template(
                "admin.html",
                error="Too many attempts. Try later.",
                recaptcha_site_key=os.getenv("RECAPTCHA_SITE_KEY")
            )

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]
        recaptcha_token = request.form.get("g-recaptcha-response")

        if not verify_recaptcha(recaptcha_token):
            return render_template(
                "admin.html",
                error="reCAPTCHA expired or was already used. Please complete the reCAPTCHA again.",
                recaptcha_site_key=os.getenv("RECAPTCHA_SITE_KEY")
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
            error="Invalid login",
            recaptcha_site_key=os.getenv("RECAPTCHA_SITE_KEY")
        )

    return render_template(
        "admin.html",
        recaptcha_site_key=os.getenv("RECAPTCHA_SITE_KEY")
    )

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

# ================= FORGOT PASSWORD =================
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email", "").strip()

        if not email:
            flash("Please enter your email address.", "error")
            return redirect(url_for("forgot_password"))

        try:
            supabase.auth.reset_password_for_email(
                email,
                options={
                    "redirect_to": url_for(
                        "reset_password",
                        _external=True
                    )
                }
            )

            flash(
                "If an account exists with that email, a password reset link has been sent.",
                "success"
            )

            return redirect(url_for("login_user"))

        except Exception as e:
            print("PASSWORD RESET ERROR:", str(e))

            flash(
                "Unable to send the password reset email. Please try again.",
                "error"
            )

    return render_template("forgot_password.html")

# ================= PASSWORD RECOVERY CONFIRM =================
@app.route("/auth/confirm")
def auth_confirm():

    token_hash = request.args.get("token_hash")
    auth_type = request.args.get("type")

    if not token_hash or auth_type != "recovery":
        flash(
            "This password reset link is invalid or has expired.",
            "error"
        )
        return redirect(url_for("forgot_password"))

    try:

        response = supabase.auth.verify_otp({
            "token_hash": token_hash,
            "type": "recovery"
        })

        session_data = response.session

        if not session_data:
            flash(
                "This password reset link is invalid or has expired.",
                "error"
            )
            return redirect(url_for("forgot_password"))

        # Store the recovery session in the server-side Flask session.
        session["password_reset_access_token"] = (
            session_data.access_token
        )

        session["password_reset_refresh_token"] = (
            session_data.refresh_token
        )

        session["password_reset_user_id"] = (
            session_data.user.id
        )

        return redirect(url_for("reset_password"))

    except Exception as e:

        print(
            "PASSWORD RECOVERY CONFIRM ERROR:",
            repr(e)
        )

        flash(
            "This password reset link is invalid or has expired.",
            "error"
        )

        return redirect(url_for("forgot_password"))

# ================= RESET PASSWORD =================
@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():

    # User must arrive here through a valid password recovery link.
    if not session.get("password_reset_user_id"):
        flash(
            "Please request a new password reset link.",
            "error"
        )
        return redirect(url_for("forgot_password"))

    if request.method == "POST":

        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not password or not confirm_password:

            flash(
                "Please fill in both password fields.",
                "error"
            )

            return redirect(url_for("reset_password"))

        if len(password) < 6:

            flash(
                "Your password must be at least 6 characters long.",
                "error"
            )

            return redirect(url_for("reset_password"))

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return redirect(url_for("reset_password"))

        try:

            access_token = session.get(
                "password_reset_access_token"
            )

            refresh_token = session.get(
                "password_reset_refresh_token"
            )

            if not access_token or not refresh_token:

                flash(
                    "Your password reset session has expired. "
                    "Please request a new reset link.",
                    "error"
                )

                return redirect(url_for("forgot_password"))

            # Restore the Supabase recovery session.
            supabase.auth.set_session(
                access_token,
                refresh_token
            )

            # Update password.
            supabase.auth.update_user({
                "password": password
            })

            # Remove the recovery session immediately.
            session.pop(
                "password_reset_access_token",
                None
            )

            session.pop(
                "password_reset_refresh_token",
                None
            )

            session.pop(
                "password_reset_user_id",
                None
            )

            # Make sure the user is NOT left logged in
            # after changing their password.
            session.pop("user_logged_in", None)
            session.pop("user_id", None)
            session.pop("email", None)
            session.pop("full_name", None)
            session.pop("account_type", None)

            flash(
                "Your password has been changed successfully. "
                "Please log in with your new password.",
                "success"
            )

            return redirect(url_for("login_user"))

        except Exception as e:

            print(
                "PASSWORD UPDATE ERROR:",
                repr(e)
            )

            flash(
                "Unable to update your password. "
                "Please request a new reset link and try again.",
                "error"
            )

            return redirect(url_for("reset_password"))

    return render_template("reset_password.html")

 # ================= GOOGLE =================================

@app.route("/auth/google")
def google_login():
    try:
        redirect_url = url_for("google_callback", _external=True)

        return supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_url
            }
        }).url

    except Exception as e:
        print("GOOGLE LOGIN ERROR:", repr(e))
        return f"Google login failed: {str(e)}", 500
        
 # ================= GOOGLE CALLBACK =================
@app.route("/auth/callback")
def google_callback():
    try:
        code = request.args.get("code")

        if not code:
            return "Google login failed: no authorization code received.", 400

        # Exchange Google's authorization code with Supabase
        auth_response = supabase.auth.exchange_code_for_session(code)

        supabase_session = auth_response.session

        if not supabase_session:
            return "Google login failed: no session returned.", 400

        user = supabase_session.user

        if not user:
            return "Google login failed: no user returned.", 400

        email = user.email

        if not email:
            return "Google login failed: no email returned.", 400

        # Find the MOTTECK profile belonging to this Google user
        profile_response = (
            supabase
            .table("profiles")
            .select("id, full_name, account_type")
            .eq("id", user.id)
            .execute()
        )

        profile = profile_response.data

        if not profile:
            supabase.auth.sign_out()
            return redirect(url_for("login_user"))

        profile = profile[0]

        # Your normal Flask login session
        session["user_logged_in"] = True
        session["user_id"] = str(user.id)
        session["email"] = email
        session["full_name"] = profile["full_name"]
        session["account_type"] = profile["account_type"]

        print("GOOGLE LOGIN SUCCESS:", email)

        return redirect(url_for("home"))

    except Exception as e:
        print("GOOGLE CALLBACK ERROR:", repr(e))
        return f"Google login failed: {str(e)}", 500

# ================= CHOOSE GOOGLE ACCOUNT TYPE =================
@app.route("/choose-account-type", methods=["GET", "POST"])
def choose_account_type():

    # Make sure this came from Google login
    if not session.get("google_user_id"):
        return redirect(url_for("login_user"))

    if request.method == "POST":

        account_type = request.form.get("account_type")

        if account_type not in ["individual", "business"]:
            flash("Please choose an account type.", "error")
            return redirect(url_for("choose_account_type"))

        user_id = session.get("google_user_id")
        email = session.get("google_email")
        full_name = session.get("google_full_name")

        try:
            # Create MOTTECK profile
            supabase.table("profiles").insert({
                "id": user_id,
                "full_name": full_name,
                "account_type": account_type
            }).execute()

            # Create normal MOTTECK login session
            session["user_logged_in"] = True
            session["user_id"] = user_id
            session["email"] = email
            session["full_name"] = full_name
            session["account_type"] = account_type

            # Remove temporary Google information
            session.pop("google_user_id", None)
            session.pop("google_email", None)
            session.pop("google_full_name", None)

            flash("Welcome to MOTTECK!", "success")

            return redirect(url_for("home"))

        except Exception as e:
            print("PROFILE CREATION ERROR:", str(e))

            flash("Unable to create your MOTTECK account.", "error")
            return redirect(url_for("choose_account_type"))

    return render_template("choose_account_type.html")

# ================= SUBMIT POST =================


@app.route("/submit-post", methods=["GET", "POST"])
def submit_post():

    if not session.get("user_logged_in") or not session.get("user_id"):
        flash("Please log in first.", "error")
        return redirect(url_for("login_user"))

    user_id = session["user_id"]
    account_type = session.get("account_type", "").strip().lower()

    if account_type not in ("individual", "business"):
        flash("Unable to determine your account type.", "error")
        return redirect(url_for("profile"))

    PROMOTION_PRICES = {
        "sponsored": {
            "24_hours": 200,
            "3_days": 500,
            "7_days": 1000,
            "1_month": 3000
        },
        "featured": {
            "24_hours": 400,
            "3_days": 700,
            "7_days": 1200,
            "1_month": 3200
        }
    }

    if request.method == "GET":
        return render_template(
            "submit_post.html",
            account_type=account_type
        )

    # ---------------- COMMON FIELDS ----------------

    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()

    if not title or not category or not description:
        flash(
            "Please complete the title, category and description.",
            "error"
        )
        return redirect(url_for("submit_post"))

    price_raw = (
        request.form.get("price")
        or request.form.get("product_price")
        or ""
    ).strip().replace(",", "").replace("KSh", "").strip()

    price = None

    if price_raw:
        try:
            price = float(price_raw)

            if price < 0:
                raise ValueError("Negative price")

        except (ValueError, TypeError):
            flash("Please enter a valid price.", "error")
            return redirect(url_for("submit_post"))

    vehicle_type = (
        request.form.get("vehicle_type")
        or request.form.get("car_type")
        or request.form.get("bike_type")
        or request.form.get("truck_type")
        or ""
    ).strip()

    year_raw = request.form.get("year", "").strip()
    mileage_raw = request.form.get("mileage", "").strip()

    condition = (
        request.form.get("condition")
        or request.form.get("vehicle_condition")
        or ""
    ).strip()

    year = None
    mileage = None

    if year_raw:
        try:
            year = int(year_raw)

            if year < 1886 or year > datetime.utcnow().year + 2:
                raise ValueError("Invalid year")

        except (ValueError, TypeError):
            flash("Please enter a valid vehicle year.", "error")
            return redirect(url_for("submit_post"))

    if mileage_raw:
        try:
            mileage = int(
                mileage_raw.lower()
                .replace("km", "")
                .replace(",", "")
                .strip()
            )

            if mileage < 0:
                raise ValueError("Negative mileage")

        except (ValueError, TypeError):
            flash("Please enter a valid mileage.", "error")
            return redirect(url_for("submit_post"))

    # ---------------- PRODUCT DETAILS ----------------

    product_name = (
        request.form.get("product_name")
        or request.form.get("part_name")
        or ""
    ).strip()

    brand = request.form.get("brand", "").strip()
    part_number = request.form.get("part_number", "").strip()

    compatibility = (
        request.form.get("compatibility")
        or request.form.get("fits")
        or ""
    ).strip()

    location = (
        request.form.get("location")
        or request.form.get("town")
        or ""
    ).strip()

    # ---------------- ACCOUNT / POST RULES ----------------

    requested_type = request.form.get(
        "post_type", ""
    ).strip().lower()

    sale_method = ""
    listing_duration = ""
    commission_agreed = False
    promotion_duration = ""
    promotion_price = None

    if account_type == "individual":

        # Individuals can submit For Sale posts.
        post_type = "for_sale"

        sale_method = request.form.get(
            "sale_method", ""
        ).strip().lower()

        listing_duration = request.form.get(
            "listing_duration", ""
        ).strip().lower()

        commission_agreed = (
            request.form.get("commission_agreed", "").lower()
            in ("true", "1", "yes", "on")
        )

        if sale_method not in (
            "direct_sale",
            "sell_through_motteck"
        ):
            flash(
                "Please choose how you want to sell your item.",
                "error"
            )
            return redirect(url_for("submit_post"))

        if sale_method == "direct_sale":

            if listing_duration not in (
                "1_day", "1_week", "1_month"
            ):
                flash("Please choose a listing duration.", "error")
                return redirect(url_for("submit_post"))

            commission_agreed = False

        elif sale_method == "sell_through_motteck":

            if not commission_agreed:
                flash(
                    "Please agree to the MOTTECK sale terms.",
                    "error"
                )
                return redirect(url_for("submit_post"))

            # No direct listing duration for MOTTECK Sale.
            listing_duration = ""

    else:
        # Businesses can choose Listing, Sponsored or Featured.
        post_type = requested_type or "normal"

        if post_type not in ("normal", "sponsored", "featured"):
            flash("Invalid business post type.", "error")
            return redirect(url_for("submit_post"))

        sale_method = ""
        listing_duration = ""
        commission_agreed = False

        # Accessories and spare parts have no normal listing fee.
        normalized_category = (
            category.lower().strip().replace("-", "_").replace(" ", "_")
        )

        if normalized_category in (
            "spare_part",
            "spare_parts",
            "accessorie",
            "accessory",
            "accessories"
        ):
            if post_type == "normal":
                promotion_duration = ""
                promotion_price = None

        if post_type in ("sponsored", "featured"):

            promotion_duration = request.form.get(
                "promotion_duration", ""
            ).strip().lower()

            valid_durations = PROMOTION_PRICES[post_type]

            if promotion_duration not in valid_durations:
                flash(
                    "Please choose a valid promotion duration.",
                    "error"
                )
                return redirect(url_for("submit_post"))

            promotion_price = valid_durations[promotion_duration]

    # ---------------- COLLECT IMAGE FILES ----------------

    image_files = [
        image for image in request.files.getlist("images")
        if image and image.filename
    ]

    max_images = 5 if account_type == "individual" else 10

    if len(image_files) > max_images:
        flash(
            f"You can upload a maximum of {max_images} photos.",
            "error"
        )
        return redirect(url_for("submit_post"))

    # ---------------- CLOUDFLARE R2 IMAGE UPLOAD ----------------

    image_urls = []

    r2_public_base_url = os.environ.get(
        "R2_PUBLIC_BASE_URL", ""
    ).rstrip("/")

    if image_files and not r2_public_base_url:
        app.logger.error(
            "R2_PUBLIC_BASE_URL is missing from Render environment variables."
        )
        flash(
            "Image storage is not configured. Please try again later.",
            "error"
        )
        return redirect(url_for("submit_post"))

    try:
        allowed_extensions = {
            ".jpg", ".jpeg", ".png", ".webp"
        }

        for image_file in image_files:

            filename = image_file.filename or ""
            extension = os.path.splitext(filename)[1].lower()

            if extension not in allowed_extensions:
                raise ValueError(
                    f"Unsupported image extension: {extension}"
                )

            image_key = (
                f"motteck/submissions/{uuid.uuid4().hex}{extension}"
            )

            content_type = (
                image_file.mimetype or "image/jpeg"
            )

            image_file.seek(0)

            r2_client.upload_fileobj(
                image_file,
                R2_BUCKET_NAME,
                image_key,
                ExtraArgs={
                    "ContentType": content_type
                }
            )

            image_url = (
                f"{r2_public_base_url}/{image_key}"
            )

            image_urls.append(image_url)

    except Exception:
        app.logger.exception(
            "CLOUDFLARE R2 SUBMISSION IMAGE UPLOAD ERROR"
        )

        flash(
            "We couldn't upload your images. Please try again.",
            "error"
        )
        return redirect(url_for("submit_post"))

    # ---------------- SUBMISSION DATA ----------------

    submission_data = {
        "user_id": user_id,
        "account_type": account_type,
        "title": title,
        "category": category,
        "description": description,
        "image_urls": image_urls,
        "post_type": post_type,
        "sale_method": sale_method or None,
        "listing_duration": listing_duration or None,
        "commission_agreed": commission_agreed,
        "promotion_duration": promotion_duration or None,
        "promotion_price": promotion_price,
        "status": "pending"
    }

    optional_fields = {
        "price": price,
        "vehicle_type": vehicle_type or None,
        "year": year,
        "mileage": mileage,
        "condition": condition or None,
        "product_name": product_name or None,
        "brand": brand or None,
        "part_number": part_number or None,
        "compatibility": compatibility or None,
        "location": location or None
    }

    submission_data.update(optional_fields)

    # ---------------- SAVE TO SUPABASE ----------------

    try:
        response = (
            supabase.table("post_submissions")
            .insert(submission_data)
            .execute()
        )

        if not response.data:
            flash(
                "Your submission could not be saved. Please try again.",
                "error"
            )
            return redirect(url_for("submit_post"))

        if (
            account_type == "business"
            and post_type in ("sponsored", "featured")
        ):
            flash(
                f"Your {post_type} submission is awaiting review. "
                f"Promotion price: KSh {promotion_price:,}.",
                "success"
            )
        else:
            flash(
                "Your submission has been sent for admin approval.",
                "success"
            )

        return redirect(url_for("my_submissions"))

    except Exception:
        app.logger.exception("POST SUBMISSION DATABASE ERROR")

        flash(
            "Your submission could not be saved. Check the server logs "
            "for the database error.",
            "error"
        )
        return redirect(url_for("submit_post"))

    
# ================= MY SUBMISSIONS =================
@app.route("/my-submissions")
def my_submissions():

    # User must be logged in
    if not session.get("user_logged_in"):
        flash("Please log in first.", "error")
        return redirect(url_for("login_user"))

    user_id = session.get("user_id")

    try:

        # Get only submissions belonging to this user
        response = supabase.table("post_submissions") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()

        submissions = response.data or []

        return render_template(
            "my_submissions.html",
            submissions=submissions,
            account_type=session.get("account_type")
        )

    except Exception as e:

        print("MY SUBMISSIONS ERROR:", repr(e))

        flash(
            "We couldn't load your submissions. Please try again.",
            "error"
        )

        return redirect(url_for("profile"))


# ================= SPONSORED POSTS PAGE =================

@app.route("/sponsored-posts")
def sponsored_posts():

    if not session.get("user_logged_in"):
        flash("Please log in first.", "error")
        return redirect(url_for("login_user"))

    user_id = session.get("user_id")

    try:

        response = (
            supabase
            .table("posts")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_sponsored", True)
            .order("created_at", desc=True)
            .execute()
        )

        posts = response.data or []

        # ================= TOTALS =================

        total_ad_views = sum(
            int(post.get("ad_views") or 0)
            for post in posts
        )

        total_ad_clicks = sum(
            int(post.get("ad_clicks") or 0)
            for post in posts
        )

        total_likes = sum(
            int(post.get("likes") or 0)
            for post in posts
        )

        # Current time for Active / Expired status
        now = datetime.utcnow().isoformat()

        return render_template(
            "sponsored_posts.html",
            posts=posts,
            total_ad_views=total_ad_views,
            total_ad_clicks=total_ad_clicks,
            total_likes=total_likes,
            now=now
        )

    except Exception as e:

        print("SPONSORED POSTS PAGE ERROR:", repr(e))

        flash(
            "We couldn't load your sponsored posts right now.",
            "error"
        )

        return redirect(url_for("profile"))


# ================= FEATURED POSTS PAGE =================

@app.route("/featured-posts")
def featured_posts():

    if not session.get("user_logged_in"):
        flash("Please log in first.", "error")
        return redirect(url_for("login_user"))

    user_id = session.get("user_id")

    try:

        response = (
            supabase
            .table("posts")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_featured", True)
            .order("created_at", desc=True)
            .execute()
        )

        posts = response.data or []

        # ================= TOTALS =================

        total_views = sum(
            int(post.get("views") or 0)
            for post in posts
        )

        total_likes = sum(
            int(post.get("likes") or 0)
            for post in posts
        )

        return render_template(
            "featured_posts.html",
            posts=posts,
            total_views=total_views,
            total_likes=total_likes,
        )

    except Exception as e:

        print("FEATURED POSTS PAGE ERROR:", repr(e))

        flash(
            "We couldn't load your featured posts right now.",
            "error"
        )

        return redirect(url_for("profile"))


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    # Make sure user is logged in
    if "user_id" not in session:
        return redirect(url_for("login_user"))

    user_id = session["user_id"]

    # Get account type
    account_type = session.get("account_type", "individual")

    try:

        # Get the user's posts
        response = (
            supabase
            .table("posts")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        posts = response.data or []

        # Calculate totals
        total_views = sum(
            int(post.get("views") or 0)
            for post in posts
        )

        total_likes = sum(
            int(post.get("likes") or 0)
            for post in posts
        )

        total_comments = sum(
            int(post.get("comments_count") or 0)
            for post in posts
        )

        # Business-only values
        # Followers will be connected later
        total_followers_gained = 0

        # Total interactions currently available
        total_interactions = (
            total_likes +
            total_comments
        )

        return render_template(
            "dashboard.html",
            posts=posts,
            total_views=total_views,
            total_likes=total_likes,
            total_comments=total_comments,
            total_followers_gained=total_followers_gained,
            total_interactions=total_interactions,
            account_type=account_type
        )

    except Exception as e:

        print("Dashboard error:", repr(e))

        return render_template(
            "dashboard.html",
            posts=[],
            total_views=0,
            total_likes=0,
            total_comments=0,
            total_followers_gained=0,
            total_interactions=0,
            account_type=account_type
        )


# ============= DELETE POST FROM DASHBOARD ============

@app.route("/delete-post/<post_id>", methods=["POST"])
def delete_post(post_id):

    if "user_id" not in session:
        return redirect(url_for("login_user"))

    user_id = session["user_id"]

    try:

        # Delete ONLY the user's own post
        supabase.table("posts") \
            .delete() \
            .eq("id", post_id) \
            .eq("user_id", user_id) \
            .execute()

        return redirect(url_for("dashboard"))

    except Exception as e:

        print("Delete post error:", repr(e))

        return redirect(url_for("dashboard"))
           

    
 # =========================================================
# ENRICH POSTS WITH AUTHOR PROFILE INFORMATION
# =========================================================

def enrich_posts_with_profiles(posts, viewer_id=None):
    """
    Adds public author information to every post.

    Uses:
        posts.user_id
            ↓
        profiles.id

    Adds:
        full_name
        business_name
        account_type
        profile_image
        is_following
        viewer_is_author
        time_ago
    """

    if not posts:
        return posts

    # ---------------------------------------
    # GET AUTHOR IDS
    # ---------------------------------------

    author_ids = list({
        str(post["user_id"])
        for post in posts
        if post.get("user_id")
    })

    # ---------------------------------------
    # GET AUTHOR PROFILES
    # ---------------------------------------

    profiles_map = {}

    if author_ids:
        profile_response = (
            supabase
            .table("profiles")
            .select(
                "id,full_name,account_type,"
                "profile_image,business_name,bio,is_verified"
            )
            .in_("id", author_ids)
            .execute()
        )

        for profile in profile_response.data or []:
            profiles_map[str(profile["id"])] = profile

    # ---------------------------------------
    # GET WHO VIEWER IS FOLLOWING
    # ---------------------------------------

    following_ids = set()

    if viewer_id and author_ids:

        follow_response = (
            supabase
            .table("follows")
            .select("following_id")
            .eq("follower_id", viewer_id)
            .in_("following_id", author_ids)
            .execute()
        )

        following_ids = {
            str(row["following_id"])
            for row in (follow_response.data or [])
        }

    # ---------------------------------------
    # ENRICH EACH POST
    # ---------------------------------------

    for post in posts:

        author_id = (
            str(post["user_id"])
            if post.get("user_id")
            else None
        )

        profile = profiles_map.get(author_id, {})

        post["full_name"] = profile.get("full_name")
        post["business_name"] = profile.get("business_name")
        post["account_type"] = profile.get("account_type")
        post["profile_image"] = profile.get("profile_image")

        # Optional public profile information
        post["bio"] = profile.get("bio")
        post["is_verified"] = profile.get("is_verified", False)

        # Follow information
        post["is_following"] = (
            author_id in following_ids
            if author_id
            else False
        )

        post["viewer_is_author"] = (
            viewer_id is not None
            and author_id == viewer_id
        )

        post["time_ago"] = time_ago(
            post.get("created_at", "")
        )

    return posts    
# =========================================================
# GET POSTS
# =========================================================

@app.route("/get_posts")
def get_posts():

    try:

        posts = (
            supabase
            .table("posts")
            .select("*")
            .execute()
            .data
            or []
        )

        # Current logged-in user
        viewer_id = None

        if (
            session.get("user_logged_in")
            and session.get("user_id")
        ):
            viewer_id = str(session["user_id"])

        # Add author/profile information
        posts = enrich_posts_with_profiles(
            posts,
            viewer_id
        )

        # Newest first
        posts.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )

        return jsonify(posts)

    except Exception as e:

        print(
            "GET POSTS ERROR:",
            repr(e)
        )

        return jsonify({
            "error": str(e)
        }), 500

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
        all_posts = (
            supabase
            .table("posts")
            .select("*")
            .execute()
            .data
            or []
        )

        viewer_id = None

        if session.get("user_logged_in") and session.get("user_id"):
            viewer_id = str(session["user_id"])

        all_posts = enrich_posts_with_profiles(all_posts, viewer_id)

        # ==========================================
        # FEATURED POSTS - MANUAL PICKS, MAX 8
        # ==========================================
        featured = sorted(
            [p for p in all_posts if p.get("is_featured")],
            key=lambda p: p.get("created_at") or "",
            reverse=True
        )[:8]

        featured_ids = {str(p["id"]) for p in featured}

        # ==========================================
        # ACTIVE SPONSORED POSTS
        # ==========================================
        active_sponsored = []

        for post in all_posts:
            if not post.get("is_sponsored"):
                continue

            expiry = post.get("sponsored_until")

            if not expiry:
                active_sponsored.append(post)
                continue

            try:
                expiry_date = datetime.fromisoformat(
                    expiry.replace("Z", "+00:00")
                )

                # Compare timezone-aware dates safely.
                if expiry_date.tzinfo is None:
                    expiry_date = expiry_date.replace(
                        tzinfo=timezone.utc
                    )

                if expiry_date > datetime.now(timezone.utc):
                    active_sponsored.append(post)

            except (ValueError, TypeError, AttributeError):
                # Preserve the existing behavior for invalid expiry data.
                active_sponsored.append(post)

        active_sponsored.sort(
            key=sponsored_score,
            reverse=True
        )

        # Don't show a featured post a second time in the feed.
        sponsored = [
            p for p in active_sponsored
            if str(p["id"]) not in featured_ids
        ]

        sponsored_ids = {
            str(p["id"]) for p in active_sponsored
        }

        # ==========================================
        # ORGANIC POSTS - NEWEST FIRST
        # No trending filter; every eligible organic
        # post remains in the normal feed.
        # ==========================================
        recent = [
            p for p in all_posts
            if str(p["id"]) not in featured_ids
            and str(p["id"]) not in sponsored_ids
        ]

        recent.sort(
            key=lambda p: p.get("created_at") or "",
            reverse=True
        )

        # ==========================================
        # MIX SPONSORED POSTS INTO THE MAIN FEED
        # One sponsored post after every 3 organic
        # posts, then append any remaining sponsors.
        # ==========================================
        mixed_recent = []
        sponsor_index = 0

        for index, post in enumerate(recent):
            mixed_recent.append(post)

            if (index + 1) % 3 == 0:
                if sponsor_index < len(sponsored):
                    mixed_recent.append(sponsored[sponsor_index])
                    sponsor_index += 1

        while sponsor_index < len(sponsored):
            mixed_recent.append(sponsored[sponsor_index])
            sponsor_index += 1

        return jsonify({
            "featured": featured,
            "recent": mixed_recent,
            "sponsored": sponsored,

            # Temporary compatibility with existing homepage JS.
            # We'll remove the old Trending section from the HTML/JS next.
            "trending": []
        })

    except Exception as e:
        print("HOME POSTS ERROR:", repr(e))

        return jsonify({
            "error": "Unable to load homepage posts",
            "featured": [],
            "recent": [],
            "sponsored": [],
            "trending": []
        }), 500



# ================= ADD POST =================
@app.route('/add_post', methods=['POST'])
def add_post():

    import os
    import requests

    if not session.get("logged_in"):
        return jsonify({
            "success": False,
            "error": "unauthorized"
        }), 403

    try:
        category = request.form.get("category")
        title = request.form.get("title")
        description = request.form.get("description")

        image_file = request.files.get("image")
        image_url = None

        # ================= CLOUDFLARE IMAGES UPLOAD =================
        if image_file and image_file.filename:

            cloudflare_account_id = os.getenv(
                "CLOUDFLARE_ACCOUNT_ID"
            )
            cloudflare_api_token = os.getenv(
                "CLOUDFLARE_IMAGES_API_TOKEN"
            )
            delivery_url = os.getenv(
                "CLOUDFLARE_IMAGES_DELIVERY_URL"
            )

            if not all([
                cloudflare_account_id,
                cloudflare_api_token,
                delivery_url
            ]):
                return jsonify({
                    "success": False,
                    "error": "Cloudflare Images is not configured."
                }), 500

            upload_url = (
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{cloudflare_account_id}/images/v1"
            )

            headers = {
                "Authorization": f"Bearer {cloudflare_api_token}"
            }

            upload_response = requests.post(
                upload_url,
                headers=headers,
                files={
                    "file": (
                        image_file.filename,
                        image_file.stream,
                        image_file.mimetype
                    )
                },
                timeout=60
            )

            upload_response.raise_for_status()
            upload_result = upload_response.json()

            if not upload_result.get("success"):
                app.logger.error(
                    "Cloudflare upload failed: %s",
                    upload_result.get("errors")
                )

                return jsonify({
                    "success": False,
                    "error": "Image upload failed."
                }), 500

            image_id = upload_result["result"]["id"]

            image_url = (
                f"{delivery_url.rstrip('/')}/{image_id}"
            )

        # ================= SPONSORED POST SETTINGS =================
        is_sponsored = bool(
            request.form.get("is_sponsored")
        )

        sponsored_until = None

        # Default sponsored duration: 30 days
        if is_sponsored:
            sponsored_until = (
                datetime.utcnow() + timedelta(days=30)
            ).isoformat()

        # ================= CREATE POST =================
        new_post = {
            "user_id": session.get("user_id"),
            "category": category,
            "title": title,
            "image_url": image_url,
            "description": description,
            "likes": 0,
            "views": 0,
            "created_at": datetime.utcnow().isoformat(),
            "is_featured": bool(
                request.form.get("is_featured")
            ),
            "is_sponsored": is_sponsored,
            "sponsored_until": sponsored_until,
            "ad_clicks": 0,
            "ad_views": 0,
            "ad_earnings": 0
        }

        response = (
            supabase.table("posts")
            .insert(new_post)
            .execute()
        )

        return jsonify({
            "success": bool(response.data)
        })

    except Exception:
        app.logger.exception("Error adding post")

        return jsonify({
            "success": False,
            "error": "Unable to add post. Please try again."
        }), 500


    
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

# ================= EDIT POST =================
@app.route('/edit_post/<int:post_id>', methods=['POST'])
def edit_post(post_id):

    if not session.get("logged_in"):
        return jsonify({
            "success": False,
            "error": "unauthorized"
        }), 403

    try:
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")

        is_featured = bool(request.form.get("is_featured"))
        is_sponsored = bool(request.form.get("is_sponsored"))

        image_file = request.files.get("image")

        update_data = {
            "title": title,
            "description": description,
            "category": category,
            "is_featured": is_featured,
            "is_sponsored": is_sponsored
        }

        # Optional image update using Cloudflare Images
        if image_file and image_file.filename:

            import os
            import requests

            cloudflare_account_id = os.getenv(
                "CLOUDFLARE_ACCOUNT_ID"
            )
            cloudflare_api_token = os.getenv(
                "CLOUDFLARE_IMAGES_API_TOKEN"
            )

            if not cloudflare_account_id or not cloudflare_api_token:
                return jsonify({
                    "success": False,
                    "error": "Cloudflare Images is not configured."
                }), 500

            upload_url = (
                f"https://api.cloudflare.com/client/v4/accounts/"
                f"{cloudflare_account_id}/images/v1"
            )

            headers = {
                "Authorization": f"Bearer {cloudflare_api_token}"
            }

            upload_response = requests.post(
                upload_url,
                headers=headers,
                files={
                    "file": (
                        image_file.filename,
                        image_file.stream,
                        image_file.mimetype
                    )
                },
                timeout=60
            )

            upload_response.raise_for_status()
            upload_result = upload_response.json()

            if not upload_result.get("success"):
                return jsonify({
                    "success": False,
                    "error": "Cloudflare image upload failed."
                }), 500

            image_id = upload_result["result"]["id"]

            # Configure this delivery URL using your Cloudflare
            # Images delivery variant.
            delivery_url = os.getenv(
                "CLOUDFLARE_IMAGES_DELIVERY_URL"
            )

            if not delivery_url:
                return jsonify({
                    "success": False,
                    "error": (
                        "Set CLOUDFLARE_IMAGES_DELIVERY_URL "
                        "in your environment variables."
                    )
                }), 500

            update_data["image_url"] = (
                f"{delivery_url.rstrip('/')}/{image_id}"
            )

        supabase.table("posts") \
            .update(update_data) \
            .eq("id", post_id) \
            .execute()

        return jsonify({
            "success": True
        })

    except Exception as e:
        app.logger.exception("Error editing post")

        return jsonify({
            "success": False,
            "error": "Unable to update post. Please try again."
        }), 500


# =========================================================
# SINGLE POST
# =========================================================

@app.route("/post/<int:post_id>")
def single_post(post_id):

    try:

        # =========================================
        # GET POST
        # =========================================

        response = (
            supabase
            .table("posts")
            .select("*")
            .eq("id", post_id)
            .execute()
        )

        if not response.data:
            return "Post not found", 404

        post = response.data[0]


        # =========================================
        # GET AUTHOR / BUSINESS PROFILE
        # =========================================

        author_id = post.get("user_id")

        if author_id:

            profile_response = (
                supabase
                .table("profiles")
                .select(
                    "id,full_name,account_type,"
                    "profile_image,business_name,bio,"
                    "is_verified,business_phone,"
                    "business_location,business_town"
                )
                .eq("id", author_id)
                .limit(1)
                .execute()
            )

            profile = (
                profile_response.data[0]
                if profile_response.data
                else {}
            )

            post["full_name"] = profile.get("full_name")
            post["business_name"] = profile.get("business_name")
            post["account_type"] = profile.get("account_type")
            post["profile_image"] = profile.get("profile_image")
            post["bio"] = profile.get("bio")
            post["is_verified"] = profile.get("is_verified", False)

            post["business_phone"] = profile.get(
                "business_phone"
            )

            post["business_location"] = profile.get(
                "business_location"
            )

            post["business_town"] = profile.get(
                "business_town"
            )

        else:

            post["full_name"] = None
            post["business_name"] = None
            post["account_type"] = None
            post["profile_image"] = None
            post["bio"] = None
            post["is_verified"] = False
            post["business_phone"] = None
            post["business_location"] = None
            post["business_town"] = None


        # =========================================
        # TIME AGO
        # =========================================

        post["time_ago"] = time_ago(
            post.get("created_at", "")
        )


        # =========================================
        # BUY NOW
        #
        # Only spare_part and Accessorie
        # =========================================

        buy_action = request.args.get("buy")

        if buy_action == "now":

            category = (
                post.get("category")
                or ""
            ).strip()

            if category not in (
                "spare_part",
                "Accessorie"
            ):

                flash(
                    "Buy Now is only available for spare parts and accessories.",
                    "error"
                )

                return redirect(
                    url_for(
                        "single_post",
                        post_id=post_id
                    )
                )


            if not session.get("user_logged_in"):

                flash(
                    "Please log in to continue with your purchase.",
                    "error"
                )

                return redirect(
                    url_for(
                        "login_user",
                        next=request.full_path
                    )
                )


            return redirect(
                url_for(
                    "checkout",
                    post_id=post_id
                )
            )


        # =========================================
        # REQUEST MOTTECK
        #
        # Do NOT create a lead here.
        # Just open the request form.
        # =========================================

        request_action = request.args.get("request")

        if request_action == "motteck":

            if not session.get("user_logged_in"):

                flash(
                    "Please log in to send a MOTTECK request.",
                    "error"
                )

                return redirect(
                    url_for(
                        "login_user",
                        next=request.full_path
                    )
                )


            return redirect(
                url_for(
                    "request_motteck",
                    post_id=post_id
                )
            )


        # =========================================
        # NORMAL SINGLE POST PAGE
        # =========================================

        return render_template(
            "single_post.html",
            post=post
        )


    except Exception as e:

        print(
            "SINGLE POST ERROR:",
            repr(e)
        )

        return "Unable to load post.", 500

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


# =================ADMIN DELETE POST =================
@app.route('/delete_post/<int:post_id>', methods=['DELETE'])
def admin_delete_post(post_id):

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

# ================= NOTIFICATIONS =================
@app.route("/notifications")
def notifications():

    if not session.get("user_logged_in"):
        flash("Please log in first.", "error")
        return redirect(url_for("login_user"))

    user_id = session.get("user_id")

    try:

        response = (
            supabase
            .table("notifications")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        notification_list = response.data or []

        unread_count = sum(
            1
            for notification in notification_list
            if not notification.get("is_read")
        )

        return render_template(
            "notifications.html",
            notifications=notification_list,
            unread_count=unread_count
        )

    except Exception as e:

        print("NOTIFICATIONS ERROR:", repr(e))

        return render_template(
            "notifications.html",
            notifications=[],
            unread_count=0
        )
# ================= MARK NOTIFICATIONS AS READ =================
@app.route("/notifications/read/<int:notification_id>", methods=["POST"])
def mark_notification_read(notification_id):

    if not session.get("user_logged_in"):
        return jsonify({
            "success": False,
            "error": "Unauthorized"
        }), 403

    user_id = session.get("user_id")

    try:

        supabase.table("notifications") \
            .update({
                "is_read": True
            }) \
            .eq("id", notification_id) \
            .eq("user_id", user_id) \
            .execute()

        return jsonify({
            "success": True
        })

    except Exception as e:

        print("MARK NOTIFICATION READ ERROR:", repr(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/toggle-follow/<user_id>", methods=["POST"])
def toggle_follow(user_id):
    try:
        # User must be logged in
        if not session.get("user_logged_in") or not session.get("user_id"):
            return jsonify({
                "success": False,
                "login_required": True
            }), 401

        follower_id = str(session["user_id"])
        following_id = str(user_id)

        # Prevent following yourself
        if follower_id == following_id:
            return jsonify({
                "success": False,
                "error": "You cannot follow yourself."
            }), 400

        # Make sure the account exists
        target_response = (
            supabase
            .table("profiles")
            .select("id")
            .eq("id", following_id)
            .limit(1)
            .execute()
        )

        if not target_response.data:
            return jsonify({
                "success": False,
                "error": "User not found."
            }), 404

        # Check whether the relationship already exists
        existing_response = (
            supabase
            .table("follows")
            .select("id")
            .eq("follower_id", follower_id)
            .eq("following_id", following_id)
            .limit(1)
            .execute()
        )

        existing = (
            existing_response.data[0]
            if existing_response.data
            else None
        )

        # Already following -> UNFOLLOW
        if existing:
            (
                supabase
                .table("follows")
                .delete()
                .eq("id", existing["id"])
                .execute()
            )

            return jsonify({
                "success": True,
                "following": False
            })

        # Not following -> FOLLOW
        (
            supabase
            .table("follows")
            .insert({
                "follower_id": follower_id,
                "following_id": following_id
            })
            .execute()
        )

        return jsonify({
            "success": True,
            "following": True
        })

    except Exception as e:
        print("TOGGLE FOLLOW ERROR:", e)

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
 # =========================================================
# CHECKOUT
# =========================================================

@app.route(
    "/checkout/<int:post_id>",
    methods=["GET", "POST"]
)
def checkout(post_id):

    # =========================================
    # LOGIN REQUIRED
    # =========================================

    if not session.get("user_logged_in"):

        flash(
            "Please log in before checking out.",
            "error"
        )

        return redirect(
            url_for(
                "login_user",
                next=request.full_path
            )
        )


    # =========================================
    # GET POST
    # =========================================

    try:

        post_response = (
            supabase
            .table("posts")
            .select("*")
            .eq("id", post_id)
            .execute()
        )

        if not post_response.data:

            return "Product not found.", 404

        post = post_response.data[0]


        # =========================================
        # ONLY SPARE PART / ACCESSORY
        # =========================================

        category = (
            post.get("category")
            or ""
        ).strip()

        if category not in (
            "spare_part",
            "Accessorie"
        ):

            flash(
                "This product is not available through Buy Now.",
                "error"
            )

            return redirect(
                url_for(
                    "single_post",
                    post_id=post_id
                )
            )


        # =========================================
        # GET SELLER PROFILE
        # =========================================

        seller_id = post.get("user_id")

        seller = {}

        if seller_id:

            seller_response = (
                supabase
                .table("profiles")
                .select(
                    "id,full_name,email,"
                    "account_type,business_name,"
                    "business_phone,business_location,"
                    "business_town"
                )
                .eq("id", seller_id)
                .limit(1)
                .execute()
            )

            if seller_response.data:

                seller = seller_response.data[0]


        post["business_name"] = (
            seller.get("business_name")
            or seller.get("full_name")
            or "MOTTECK Seller"
        )

        post["business_phone"] = seller.get(
            "business_phone"
        )

        post["business_location"] = seller.get(
            "business_location"
        )

        post["business_town"] = seller.get(
            "business_town"
        )


        # =========================================
        # DISPLAY CHECKOUT
        # =========================================

        if request.method == "GET":

            return render_template(
                "checkout.html",
                post=post
            )


        # =========================================
        # CREATE ORDER
        # =========================================

        customer_id = session.get("user_id")

        customer_name = (
            request.form.get("customer_name")
            or session.get("full_name")
            or ""
        ).strip()

        customer_email = (
            request.form.get("customer_email")
            or session.get("email")
            or ""
        ).strip()

        customer_phone = (
            request.form.get("customer_phone")
            or ""
        ).strip()

        quantity_raw = (
            request.form.get("quantity")
            or "1"
        ).strip()


        # =========================================
        # VALIDATE QUANTITY
        # =========================================

        try:

            quantity = int(quantity_raw)

            if quantity < 1:
                raise ValueError

        except (ValueError, TypeError):

            flash(
                "Please enter a valid quantity.",
                "error"
            )

            return redirect(
                url_for(
                    "checkout",
                    post_id=post_id
                )
            )


        # =========================================
        # PRICE
        # =========================================

        try:

            unit_price = float(
                post.get("price") or 0
            )

        except (ValueError, TypeError):

            unit_price = 0


        if unit_price <= 0:

            flash(
                "This product does not have a valid price.",
                "error"
            )

            return redirect(
                url_for(
                    "single_post",
                    post_id=post_id
                )
            )


        total_amount = unit_price * quantity


        # =========================================
        # COMMON CUSTOMER / DELIVERY DETAILS
        # =========================================

        delivery_town = (
            request.form.get("delivery_town")
            or ""
        ).strip()

        delivery_area = (
            request.form.get("delivery_area")
            or ""
        ).strip()

        delivery_address = (
            request.form.get("delivery_address")
            or ""
        ).strip()


        # =========================================
        # PRODUCT-SPECIFIC INFORMATION
        # =========================================

        product_name = post.get(
            "product_name"
        ) or post.get(
            "title"
        )


        # -----------------------------------------
        # SPARE PART
        # -----------------------------------------

        if category == "spare_part":

            product_type = "spare_part"

            part_name = (
                request.form.get("part_name")
                or product_name
                or ""
            ).strip()

            part_number = (
                request.form.get("part_number")
                or post.get("part_number")
                or ""
            ).strip()

            vehicle_make = (
                request.form.get("vehicle_make")
                or ""
            ).strip()

            vehicle_model = (
                request.form.get("vehicle_model")
                or ""
            ).strip()

            vehicle_year = (
                request.form.get("vehicle_year")
                or ""
            ).strip()

            engine = (
                request.form.get("engine")
                or ""
            ).strip()

            specifications = (
                request.form.get("specifications")
                or ""
            ).strip()

            variant = None

            brand = (
                post.get("brand")
                or ""
            )


        # -----------------------------------------
        # ACCESSORY
        # -----------------------------------------

        else:

            product_type = "accessory"

            part_name = (
                request.form.get("accessory_name")
                or product_name
                or ""
            ).strip()

            part_number = None

            vehicle_make = (
                request.form.get("vehicle_make")
                or ""
            ).strip()

            vehicle_model = (
                request.form.get("vehicle_model")
                or ""
            ).strip()

            vehicle_year = (
                request.form.get("vehicle_year")
                or ""
            ).strip()

            engine = None

            variant = (
                request.form.get("variant")
                or ""
            ).strip()

            brand = (
                request.form.get("accessory_brand")
                or post.get("brand")
                or ""
            ).strip()

            specifications = (
                request.form.get("specifications")
                or ""
            ).strip()


        # =========================================
        # ORDER NUMBER
        # =========================================

        order_number = (
            "MTK-"
            + datetime.utcnow().strftime("%Y%m%d")
            + "-"
            + uuid.uuid4().hex[:8].upper()
        )


        # =========================================
        # ORDER DATA
        #
        # PAYMENT REMAINS PENDING.
        # =========================================

        order_data = {

            "order_number": order_number,

            "post_id": post_id,

            "customer_id": customer_id,

            "seller_id": seller_id,

            "product_type": product_type,

            "product_name": part_name,

            "quantity": quantity,

            "unit_price": unit_price,

            "total_amount": total_amount,

            "part_number": part_number,

            "brand": brand,

            "vehicle_make": vehicle_make,

            "vehicle_model": vehicle_model,

            "vehicle_year": vehicle_year,

            "engine": engine,

            "variant": variant,

            "specifications": specifications,

            "customer_name": customer_name,

            "customer_email": customer_email,

            "customer_phone": customer_phone,

            "delivery_town": delivery_town,

            "delivery_area": delivery_area,

            "delivery_address": delivery_address,

            "payment_status": "pending",

            "order_status": "awaiting_payment"

        }


        # =========================================
        # SAVE ORDER
        # =========================================

        order_response = (
            supabase
            .table("orders")
            .insert(order_data)
            .execute()
        )


        if not order_response.data:

            flash(
                "Unable to create your order. Please try again.",
                "error"
            )

            return redirect(
                url_for(
                    "checkout",
                    post_id=post_id
                )
            )


        order = order_response.data[0]


        # =========================================
        # PAYMENT RECORD
        #
        # NOT PAID YET
        # =========================================

        payment_data = {

            "order_id": order.get("id"),

            "amount": total_amount,

            "payment_method": (
                request.form.get("payment_method")
                or "mpesa"
            ),

            "payment_status": "pending",

            "payment_reference": None

        }


        try:

            supabase.table(
                "payments"
            ).insert(
                payment_data
            ).execute()

        except Exception as payment_error:

            print(
                "PAYMENT RECORD ERROR:",
                repr(payment_error)
            )


        # =========================================
        # REDIRECT TO PAYMENT
        #
        # We DO NOT mark the order as paid here.
        # =========================================

        return redirect(
            url_for(
                "order_payment",
                order_number=order_number
            )
        )


    except Exception as e:

        print(
            "CHECKOUT ERROR:",
            repr(e)
        )

        flash(
            "Unable to process checkout. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "single_post",
                post_id=post_id
            )
        )

# =========================================================
# ORDER PAYMENT
# =========================================================

@app.route(
    "/order/<order_number>/payment"
)
def order_payment(order_number):

    if not session.get("user_logged_in"):

        flash(
            "Please log in to continue.",
            "error"
        )

        return redirect(
            url_for("login_user")
        )


    try:

        response = (
            supabase
            .table("orders")
            .select("*")
            .eq(
                "order_number",
                order_number
            )
            .limit(1)
            .execute()
        )


        if not response.data:

            return "Order not found.", 404


        order = response.data[0]


        # =========================================
        # SECURITY
        # =========================================

        if str(
            order.get("customer_id")
        ) != str(
            session.get("user_id")
        ):

            return "Unauthorized.", 403


        # =========================================
        # ALREADY PAID
        # =========================================

        if order.get("payment_status") == "paid":

            if order.get("invoice_number"):

                return redirect(
                    url_for(
                        "invoice",
                        invoice_number=order.get(
                            "invoice_number"
                        )
                    )
                )


        return render_template(
            "checkout.html",
            post={
                "id": order.get("post_id"),
                "title": order.get("product_name"),
                "price": order.get("unit_price"),
                "category": (
                    "spare_part"
                    if order.get("product_type") == "spare_part"
                    else "Accessorie"
                ),
                "product_name": order.get(
                    "product_name"
                ),
                "part_number": order.get(
                    "part_number"
                ),
                "brand": order.get(
                    "brand"
                )
            },
            order=order,
            payment_stage=True
        )


    except Exception as e:

        print(
            "ORDER PAYMENT ERROR:",
            repr(e)
        )

        return "Unable to load payment.", 500
# =========================================================
# REQUEST MOTTECK
# =========================================================

@app.route(
    "/request-motteck/<int:post_id>",
    methods=["GET", "POST"]
)
def request_motteck(post_id):

    # =========================================
    # LOGIN
    # =========================================

    if not session.get("user_logged_in"):

        flash(
            "Please log in to send a MOTTECK request.",
            "error"
        )

        return redirect(
            url_for(
                "login_user",
                next=request.full_path
            )
        )


    try:

        # =========================================
        # GET POST
        # =========================================

        post_response = (
            supabase
            .table("posts")
            .select("*")
            .eq("id", post_id)
            .limit(1)
            .execute()
        )


        if not post_response.data:

            return "Post not found.", 404


        post = post_response.data[0]

        seller_id = post.get(
            "user_id"
        )

        customer_id = session.get(
            "user_id"
        )


        # =========================================
        # PREVENT SELF REQUEST
        # =========================================

        if (
            seller_id
            and customer_id
            and str(seller_id)
            == str(customer_id)
        ):

            flash(
                "You cannot request MOTTECK through your own listing.",
                "error"
            )

            return redirect(
                url_for(
                    "single_post",
                    post_id=post_id
                )
            )


        # =========================================
        # DISPLAY FORM
        # =========================================

        if request.method == "GET":

            return render_template(
                "request_motteck.html",
                post=post
            )


        # =========================================
        # FORM DATA
        # =========================================

        customer_name = (
            request.form.get("customer_name")
            or session.get("full_name")
            or ""
        ).strip()

        customer_email = (
            request.form.get("customer_email")
            or session.get("email")
            or ""
        ).strip()

        customer_phone = (
            request.form.get("customer_phone")
            or ""
        ).strip()

        town = (
            request.form.get("town")
            or ""
        ).strip()

        request_details = (
            request.form.get("request_details")
            or ""
        ).strip()

        preferred_location = (
            request.form.get("preferred_location")
            or ""
        ).strip()


        if not customer_name:

            flash(
                "Please enter your name.",
                "error"
            )

            return redirect(
                url_for(
                    "request_motteck",
                    post_id=post_id
                )
            )


        if not customer_phone:

            flash(
                "Please enter your phone number.",
                "error"
            )

            return redirect(
                url_for(
                    "request_motteck",
                    post_id=post_id
                )
            )


        if not request_details:

            flash(
                "Please describe what you need.",
                "error"
            )

            return redirect(
                url_for(
                    "request_motteck",
                    post_id=post_id
                )
            )


        # =========================================
        # CREATE REQUEST
        # =========================================

        request_number = (
            "REQ-"
            + datetime.utcnow().strftime("%Y%m%d")
            + "-"
            + uuid.uuid4().hex[:8].upper()
        )


        request_data = {

            "request_number": request_number,

            "post_id": post_id,

            "customer_id": customer_id,

            "seller_id": seller_id,

            "customer_name": customer_name,

            "customer_email": customer_email,

            "customer_phone": customer_phone,

            "town": town,

            "request_details": request_details,

            "preferred_location": preferred_location,

            "status": "new"

        }


        response = (
            supabase
            .table("motteck_requests")
            .insert(request_data)
            .execute()
        )


        if not response.data:

            flash(
                "Unable to send your request. Please try again.",
                "error"
            )

            return redirect(
                url_for(
                    "request_motteck",
                    post_id=post_id
                )
            )


        # =========================================
        # ALSO CREATE LEAD
        #
        # This keeps it visible in existing
        # admin/leads.
        # =========================================

        lead_data = {

            "post_id": post_id,

            "seller_id": seller_id,

            "interested_user_id": customer_id,

            "lead_type": "request_motteck",

            "status": "new"

        }


        try:

            supabase.table(
                "leads"
            ).insert(
                lead_data
            ).execute()

        except Exception as lead_error:

            print(
                "REQUEST LEAD ERROR:",
                repr(lead_error)
            )


        # =========================================
        # SUCCESS
        # =========================================

        flash(
            "Your request has been sent to MOTTECK successfully.",
            "success"
        )

        return redirect(
            url_for(
                "single_post",
                post_id=post_id
            )
        )


    except Exception as e:

        print(
            "REQUEST MOTTECK ERROR:",
            repr(e)
        )

        flash(
            "Unable to send your request. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "single_post",
                post_id=post_id
            )
        )   
# =========================================================
# CUSTOMER INVOICE
# =========================================================

@app.route(
    "/invoice/<invoice_number>"
)
def invoice(invoice_number):

    if not session.get("user_logged_in"):

        flash(
            "Please log in to view your invoice.",
            "error"
        )

        return redirect(
            url_for("login_user")
        )


    try:

        # =========================================
        # GET INVOICE
        # =========================================

        invoice_response = (
            supabase
            .table("invoices")
            .select("*")
            .eq(
                "invoice_number",
                invoice_number
            )
            .limit(1)
            .execute()
        )


        if not invoice_response.data:

            return "Invoice not found.", 404


        invoice_data = invoice_response.data[0]


        # =========================================
        # ONLY PAID INVOICES
        # =========================================

        if invoice_data.get(
            "payment_status"
        ) != "paid":

            return (
                "This invoice has not been paid.",
                403
            )


        customer_id = invoice_data.get(
            "customer_id"
        )

        seller_id = invoice_data.get(
            "seller_id"
        )

        logged_user = session.get(
            "user_id"
        )

        is_admin = session.get(
            "logged_in"
        )


        # =========================================
        # SECURITY
        #
        # Customer, seller or admin only.
        # =========================================

        if not is_admin:

            if (
                str(logged_user)
                != str(customer_id)
                and
                str(logged_user)
                != str(seller_id)
            ):

                return "Unauthorized.", 403


        # =========================================
        # GET ORDER
        # =========================================

        order_id = invoice_data.get(
            "order_id"
        )


        order_response = (
            supabase
            .table("orders")
            .select("*")
            .eq(
                "id",
                order_id
            )
            .limit(1)
            .execute()
        )


        if not order_response.data:

            return "Order not found.", 404


        order = order_response.data[0]


        # =========================================
        # GET PAYMENT
        # =========================================

        payment_response = (
            supabase
            .table("payments")
            .select("*")
            .eq(
                "order_id",
                order_id
            )
            .eq(
                "payment_status",
                "paid"
            )
            .order(
                "created_at",
                desc=True
            )
            .limit(1)
            .execute()
        )


        payment = (
            payment_response.data[0]
            if payment_response.data
            else {}
        )


        # =========================================
        # GET BUSINESS
        # =========================================

        seller_id = order.get(
            "seller_id"
        )

        business = {}


        if seller_id:

            business_response = (
                supabase
                .table("profiles")
                .select(
                    "id,full_name,email,"
                    "business_name,business_phone,"
                    "business_location,business_town"
                )
                .eq(
                    "id",
                    seller_id
                )
                .limit(1)
                .execute()
            )


            if business_response.data:

                business = (
                    business_response.data[0]
                )


        invoice_data["business_name"] = (
            business.get("business_name")
            or business.get("full_name")
            or "Seller"
        )

        invoice_data["business_phone"] = (
            business.get("business_phone")
        )

        invoice_data["business_location"] = (
            business.get("business_location")
        )


        return render_template(
            "invoice.html",
            invoice=invoice_data,
            order=order,
            payment=payment
        )


    except Exception as e:

        print(
            "INVOICE ERROR:",
            repr(e)
        )

        return "Unable to load invoice.", 500
# =========================================================
# ADMIN - ORDERS
# =========================================================

@app.route("/admin/orders")
def admin_orders():

    if not session.get("logged_in"):

        return jsonify({
            "error": "Unauthorized"
        }), 403


    try:

        response = (
            supabase
            .table("orders")
            .select("*")
            .order(
                "created_at",
                desc=True
            )
            .execute()
        )


        orders = response.data or []


        # =========================================
        # ENRICH ORDERS
        # =========================================

        for order in orders:

            # -------------------------------------
            # POST
            # -------------------------------------

            post_id = order.get(
                "post_id"
            )

            if post_id:

                try:

                    post_response = (
                        supabase
                        .table("posts")
                        .select(
                            "id,title,category"
                        )
                        .eq(
                            "id",
                            post_id
                        )
                        .limit(1)
                        .execute()
                    )

                    post = (
                        post_response.data[0]
                        if post_response.data
                        else {}
                    )

                    order["post_title"] = (
                        post.get("title")
                        or order.get("product_name")
                        or "Unknown"
                    )

                    order["category"] = (
                        post.get("category")
                        or order.get("product_type")
                    )

                except Exception:

                    order["post_title"] = (
                        order.get("product_name")
                        or "Unknown"
                    )

            else:

                order["post_title"] = (
                    order.get("product_name")
                    or "Unknown"
                )


            # -------------------------------------
            # CUSTOMER
            # -------------------------------------

            customer_id = order.get(
                "customer_id"
            )

            if customer_id:

                try:

                    customer_response = (
                        supabase
                        .table("profiles")
                        .select(
                            "id,full_name,email"
                        )
                        .eq(
                            "id",
                            customer_id
                        )
                        .limit(1)
                        .execute()
                    )

                    customer = (
                        customer_response.data[0]
                        if customer_response.data
                        else {}
                    )

                    order["customer_profile_name"] = (
                        customer.get("full_name")
                        or order.get("customer_name")
                    )

                    order["customer_profile_email"] = (
                        customer.get("email")
                        or order.get("customer_email")
                    )

                except Exception:

                    order["customer_profile_name"] = (
                        order.get("customer_name")
                    )

                    order["customer_profile_email"] = (
                        order.get("customer_email")
                    )


            # -------------------------------------
            # SELLER
            # -------------------------------------

            seller_id = order.get(
                "seller_id"
            )

            if seller_id:

                try:

                    seller_response = (
                        supabase
                        .table("profiles")
                        .select(
                            "id,full_name,email,"
                            "business_name"
                        )
                        .eq(
                            "id",
                            seller_id
                        )
                        .limit(1)
                        .execute()
                    )

                    seller = (
                        seller_response.data[0]
                        if seller_response.data
                        else {}
                    )

                    order["seller_name"] = (
                        seller.get("business_name")
                        or seller.get("full_name")
                        or "Unknown seller"
                    )

                    order["seller_email"] = (
                        seller.get("email")
                        or ""
                    )

                except Exception:

                    order["seller_name"] = (
                        "Unknown seller"
                    )

                    order["seller_email"] = ""

            else:

                order["seller_name"] = (
                    "Unknown seller"
                )

                order["seller_email"] = ""


        return jsonify({
            "success": True,
            "orders": orders
        })


    except Exception as e:

        print(
            "ADMIN ORDERS ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# =========================================================
# ADMIN - INVOICES
# =========================================================

@app.route("/admin/invoices")
def admin_invoices():

    if not session.get("logged_in"):

        return jsonify({
            "error": "Unauthorized"
        }), 403


    try:

        response = (
            supabase
            .table("invoices")
            .select("*")
            .order(
                "created_at",
                desc=True
            )
            .execute()
        )


        invoices = response.data or []


        return jsonify({
            "success": True,
            "invoices": invoices
        })


    except Exception as e:

        print(
            "ADMIN INVOICES ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
                        
# ================= CONTACT =================
@app.route('/contact', methods=['GET', 'POST'])
def contact():

    if request.method == "POST":

        firstname = request.form.get("firstname", "").strip()
        lastname = request.form.get("lastname", "").strip()
        email = request.form.get("email", "").strip()
        inquiry_type = request.form.get("inquiry_type", "").strip()
        message = request.form.get("text", "").strip()

        # ================= VALIDATION =================

        if not firstname or not email or not inquiry_type or not message:
            return jsonify({
                "status": "error",
                "message": "Please fill all required fields"
            })

        try:

            # ================= SEND EMAIL =================

            resend.Emails.send({
                "from": "contact@mottecknetwork.com",

                # YOUR MOTTECK CONTACT EMAIL
                "to": "mottecknetwork@gmail.com",

                "subject": f"MOTTECK Contact - {inquiry_type} - {firstname} {lastname}",

                # When you click Reply in your email,
                # the reply will go directly to the person who contacted you.
                "reply_to": email,

                "html": f"""
                    <div style="
                        font-family: Arial, sans-serif;
                        max-width: 650px;
                        margin: auto;
                        color: #222;
                    ">

                        <h2 style="
                            background: #111;
                            color: white;
                            padding: 18px;
                            margin: 0;
                        ">
                            New MOTTECK Contact Message
                        </h2>

                        <div style="padding: 20px;">

                            <p>
                                <strong>Inquiry Type:</strong>
                                {inquiry_type}
                            </p>

                            <p>
                                <strong>Name:</strong>
                                {firstname} {lastname}
                            </p>

                            <p>
                                <strong>Email:</strong>
                                {email}
                            </p>

                            <hr>

                            <p>
                                <strong>Message:</strong>
                            </p>

                            <p style="
                                white-space: pre-line;
                                line-height: 1.6;
                            ">
                                {message}
                            </p>

                        </div>

                    </div>
                """
            })

            return jsonify({
                "status": "success",
                "message": "Message sent successfully"
            })

        except Exception as e:

            print("CONTACT ERROR:", str(e))

            return jsonify({
                "status": "error",
                "message": "Failed to send message"
            })

    return render_template("contact.html")

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)