import os
import uuid
import traceback
import urllib.parse
from flask import Blueprint, request, jsonify, session, current_app, redirect
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta

from models import (
    db, User, Course, Lesson, Enrollment, 
    LessonProgress, LiveSession, Booking, 
    SessionRequest, CollaborationPost, Review
)
from utils.google_calendar import (
    get_google_auth_url, exchange_code_for_tokens,
    create_google_calendar_event, delete_google_calendar_event,
    send_notification_email
)
from utils.auth import (
    hash_password, check_password, is_valid_email,
    generate_google_auth_url, exchange_google_code,
    fetch_google_user_info, generate_reset_token
)

api_blueprint = Blueprint('api', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'mp4', 'webm', 'mov', 'mkv'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── Decorators ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def creator_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        user = User.query.get(session['user_id'])
        if not user or user.role != 'creator':
            return jsonify({'error': 'Creator privileges required'}), 403
        return f(*args, **kwargs)
    return decorated


# ─── Authentication Routes ───────────────────────────────────────────────────

@api_blueprint.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = (data.get('full_name') or data.get('name') or '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not name:
        return jsonify({'error': 'Full Name is required.'}), 400
    if not email:
        return jsonify({'error': 'Email address is required.'}), 400
    if not is_valid_email(email):
        return jsonify({'error': 'Please enter a valid email address.'}), 400
    if not password:
        return jsonify({'error': 'Password is required.'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long.'}), 400
    if confirm_password and password != confirm_password:
        return jsonify({'error': 'Passwords do not match.'}), 400

    if User.query.filter(User.email.ilike(email)).first():
        return jsonify({'error': 'An account with this email already exists. Please log in.'}), 409

    role = (data.get('role') or '').strip().lower()
    if role not in ['creator', 'learner']:
        role = 'learner'

    user = User(
        name=name,
        email=email,
        password=hash_password(password),
        role=role,
        points=0
    )
    db.session.add(user)
    db.session.commit()

    session['user_id'] = user.id
    session.permanent = True

    return jsonify({
        'message': 'Account created successfully.',
        'user': user.to_dict(),
        'requires_role_selection': False
    }), 201


@api_blueprint.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email_or_name = (data.get('email') or data.get('name') or '').strip().lower()
    password = data.get('password', '')

    if not email_or_name:
        return jsonify({'error': 'Email address is required.'}), 400
    if not password:
        return jsonify({'error': 'Password is required.'}), 400

    user = User.query.filter(
        db.or_(User.email.ilike(email_or_name), User.name.ilike(email_or_name))
    ).first()

    if not user:
        return jsonify({'error': 'Invalid email or password.'}), 401

    if not user.password and user.google_id:
        return jsonify({'error': 'This account was registered using Google. Please click "Continue with Google".'}), 400

    if not check_password(password, user.password):
        return jsonify({'error': 'Invalid email or password.'}), 401

    # Upgrade legacy werkzeug password hash to bcrypt if needed
    if user.password and not (user.password.startswith('$2b$') or user.password.startswith('$2a$')):
        user.password = hash_password(password)
        db.session.commit()

    session['user_id'] = user.id
    session.permanent = True

    requires_role = not bool(user.role)

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'requires_role_selection': requires_role
    })


@api_blueprint.route('/auth/set-role', methods=['POST'])
@login_required
def set_role():
    data = request.get_json() or {}
    role = data.get('role', '').strip().lower()

    if role not in ['learner', 'creator']:
        return jsonify({'error': 'Invalid role selection. Please choose Learner or Creator.'}), 400

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found.'}), 404

    # Save role permanently
    user.role = role
    user.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'message': f'Role updated to {role.capitalize()} permanently.',
        'user': user.to_dict()
    })


@api_blueprint.route('/auth/google/url', methods=['GET'])
@api_blueprint.route('/auth/google/login', methods=['GET'])
def get_google_oauth_url():
    url = generate_google_auth_url()
    if not url:
        return jsonify({'error': 'Google OAuth credentials missing in configuration.'}), 500
    return jsonify({'url': url, 'auth_url': url})


@api_blueprint.route('/auth/google/status', methods=['GET'])
def google_auth_status():
    user_id = session.get('user_id')
    auth_url = generate_google_auth_url()
    if not user_id:
        return jsonify({
            'is_connected': False,
            'google_calendar_connected': False,
            'auth_url': auth_url
        })

    user = User.query.get(user_id)
    if not user:
        return jsonify({
            'is_connected': False,
            'google_calendar_connected': False,
            'auth_url': auth_url
        })

    is_conn = bool(user.is_google_connected and user.google_access_token)
    return jsonify({
        'is_connected': is_conn,
        'google_calendar_connected': is_conn,
        'google_email': user.email,
        'last_synced': user.updated_at.isoformat() if user.updated_at else None,
        'auth_url': auth_url
    })


@api_blueprint.route('/auth/google/callback', methods=['GET', 'POST'])
def google_auth_callback():
    code = request.args.get('code') or (request.get_json() or {}).get('code')
    error = request.args.get('error')

    if error:
        print(f"[OAUTH ERROR] Google OAuth callback error: {error}")
        return redirect(f'/?auth_error=Google+OAuth+Error:+{urllib.parse.quote(error)}')

    if not code:
        print("[OAUTH ERROR] No authorization code provided in Google OAuth callback URL.")
        return redirect('/?auth_error=No+authorization+code+provided+by+Google')

    print(f"[OAUTH LOG] Received Google OAuth authorization code. Exchanging for tokens...")
    tokens = exchange_google_code(code)
    if not tokens or 'access_token' not in tokens:
        print("[OAUTH ERROR] Token exchange failed or missing access_token in payload.")
        return redirect('/?auth_error=Failed+to+exchange+Google+authorization+code')

    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    expires_in = tokens.get('expires_in', 3600)

    user_info = fetch_google_user_info(access_token)
    if not user_info or not user_info.get('email'):
        print("[OAUTH ERROR] Could not fetch Google user profile.")
        return redirect('/?auth_error=Failed+to+retrieve+user+profile+from+Google')

    google_id = user_info.get('sub')
    email = user_info.get('email', '').strip().lower()
    name = user_info.get('name') or email.split('@')[0]
    picture = user_info.get('picture')

    print(f"[OAUTH LOG] Google User Profile: Email={email}, Sub ID={google_id}")

    user = None
    # 1. Check if user is currently logged in via Flask session
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            print(f"[OAUTH LOG] Currently logged in user found: ID {user.id} ({user.email}). Attaching Google tokens...")

    # 2. If no session user, find user by email or google_id
    if not user:
        user = User.query.filter(db.or_(User.email.ilike(email), User.google_id == google_id)).first()
        if user:
            print(f"[OAUTH LOG] Found existing user in DB matching email/google_id: ID {user.id} ({user.email})")

    if user:
        # Update existing user record with OAuth tokens and connection state
        if not user.google_id:
            user.google_id = google_id
        if picture and not user.avatar_url:
            user.avatar_url = picture
        
        user.google_access_token = access_token
        if refresh_token:
            user.google_refresh_token = refresh_token
            print(f"[OAUTH LOG] Updated google_refresh_token for user {user.id}")
            
        user.google_token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        user.is_google_connected = True
        user.updated_at = datetime.utcnow()
        db.session.commit()
        print(f"[OAUTH LOG] SUCCESS: Saved Google OAuth tokens & marked google_calendar_connected=True for user {user.id}")
    else:
        # Create new user record from Google OAuth
        user = User(
            google_id=google_id,
            name=name,
            email=email,
            password=None,
            role=None,
            avatar_url=picture,
            is_google_connected=True,
            google_access_token=access_token,
            google_refresh_token=refresh_token,
            google_token_expiry=datetime.utcnow() + timedelta(seconds=expires_in)
        )
        db.session.add(user)
        db.session.commit()
        print(f"[OAUTH LOG] SUCCESS: Created new user {user.id} ({user.email}) with Google tokens connected.")

    session['user_id'] = user.id
    session.permanent = True

    return redirect('/?google_auth=success')


@api_blueprint.route('/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email or not is_valid_email(email):
        return jsonify({'error': 'Please enter a valid email address.'}), 400

    user = User.query.filter(User.email.ilike(email)).first()
    if not user:
        # For security, return success message even if email not found
        return jsonify({'message': 'If an account exists with this email, password reset instructions have been sent.'})

    reset_token = generate_reset_token()
    user.reset_token = reset_token
    user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()

    reset_link = f"{request.host_url}?reset_token={reset_token}&email={urllib.parse.quote(email)}"
    send_notification_email(
        email,
        "Nexora Password Reset Request",
        f"Hi {user.name},\n\nYou requested to reset your password on Nexora. Click the link below to set a new password:\n{reset_link}\n\nThis link will expire in 1 hour.\nIf you did not request this, please ignore this email."
    )

    return jsonify({
        'message': 'Password reset instructions have been sent to your email.',
        'reset_token': reset_token  # Provided for seamless frontend demo testing
    })


@api_blueprint.route('/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    token = data.get('token', '').strip()
    new_password = data.get('new_password', '')

    if not email or not token or not new_password:
        return jsonify({'error': 'All fields are required.'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long.'}), 400

    user = User.query.filter(User.email.ilike(email), User.reset_token == token).first()
    if not user or not user.reset_token_expiry or datetime.utcnow() > user.reset_token_expiry:
        return jsonify({'error': 'Invalid or expired password reset token.'}), 400

    user.password = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    user.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Password reset successfully. You can now log in with your new password.'})


@api_blueprint.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@api_blueprint.route('/auth/me', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'user': None})
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return jsonify({'user': None})

    if user.points == 500:
        user.points = 0
        db.session.commit()

    return jsonify({'user': user.to_dict()})


@api_blueprint.route('/auth/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.get_json() or {}
    user = User.query.get(session['user_id'])
    
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if 'name' in data or 'full_name' in data:
        user.name = (data.get('full_name') or data.get('name')).strip()
    if 'headline' in data:
        user.headline = data['headline'].strip()
    if 'bio' in data:
        user.bio = data['bio'].strip()
    if 'skills' in data:
        user.skills = data['skills'].strip() if isinstance(data['skills'], str) else ', '.join(data['skills'])
    if 'profile_banner' in data:
        user.profile_banner = data['profile_banner'].strip()
    if 'social_links' in data:
        user.social_links = json.dumps(data['social_links']) if isinstance(data['social_links'], dict) else str(data['social_links'])
    if 'avatar_url' in data or 'profile_picture' in data:
        user.avatar_url = (data.get('profile_picture') or data.get('avatar_url')).strip()

    user.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Profile updated successfully', 'user': user.to_dict()})


# ─── Media & File Upload Route ────────────────────────────────────────────────

@api_blueprint.route('/upload/file', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request.'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file.'}), 400

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        
        folder = 'course_thumbnails' if ext in {'png', 'jpg', 'jpeg', 'gif', 'svg'} else 'temp'
        save_path = os.path.join(current_app.config['UPLOADS_DIR'], folder, filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        file.save(save_path)

        file_url = f"/uploads/{folder}/{filename}"
        return jsonify({'message': 'File uploaded successfully', 'url': file_url}), 201

    return jsonify({'error': 'File type not allowed.'}), 400


# ─── Course Management Routes ─────────────────────────────────────────────────

@api_blueprint.route('/courses', methods=['GET'])
def get_courses():
    search = request.args.get('search', '').strip().lower()
    category = request.args.get('category', '').strip()
    level = request.args.get('level', '').strip()

    query = Course.query.filter_by(is_published=True)
    if search:
        query = query.filter(db.or_(Course.title.ilike(f'%{search}%'), Course.description.ilike(f'%{search}%')))
    if category:
        query = query.filter_by(category=category)
    if level:
        query = query.filter_by(level=level)

    courses = query.order_by(Course.created_at.desc()).all()
    return jsonify({'courses': [c.to_dict() for c in courses]})


@api_blueprint.route('/courses/featured', methods=['GET'])
def get_featured_courses():
    newest = Course.query.filter_by(is_published=True).order_by(Course.created_at.desc()).limit(6).all()
    trending = Course.query.filter_by(is_published=True).order_by(Course.created_at.asc()).limit(6).all()
    return jsonify({
        'newest': [c.to_dict() for c in newest],
        'trending': [c.to_dict() for c in trending]
    })


@api_blueprint.route('/courses/<int:course_id>', methods=['GET'])
def get_course_details(course_id):
    course = Course.query.get_or_404(course_id)
    return jsonify({'course': course.to_dict()})


@api_blueprint.route('/courses', methods=['POST'])
@creator_required
def create_course():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()

    if not title or not description:
        return jsonify({'error': 'Title and description are required.'}), 400

    creator = User.query.get(session['user_id'])
    course = Course(
        title=title,
        description=description,
        instructor=creator.name,
        category=data.get('category', 'General'),
        level=data.get('level', 'Beginner'),
        duration=data.get('duration', 'Self-paced'),
        thumbnail_url=data.get('thumbnail_url') or 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&q=80&w=400&h=400',
        price=int(data.get('price', 0)),
        points_price=int(data.get('points_price', 0)),
        is_published=bool(data.get('is_published', True)),
        is_single_video=bool(data.get('is_single_video', False)),
        tags=data.get('tags', ''),
        created_by=creator.id
    )
    db.session.add(course)
    db.session.commit()

    return jsonify({'message': 'Content created successfully', 'course': course.to_dict()}), 201


@api_blueprint.route('/upload/single-video', methods=['POST'])
@creator_required
def upload_single_video():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    video_url = data.get('video_url', '').strip()

    if not title or not description or not video_url:
        return jsonify({'error': 'Title, description, and video file/URL are required.'}), 400

    creator = User.query.get(session['user_id'])
    course = Course(
        title=title,
        description=description,
        instructor=creator.name,
        category=data.get('category', 'General'),
        level=data.get('level', 'Beginner'),
        duration='Single Video',
        thumbnail_url=data.get('thumbnail_url') or 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&q=80&w=400&h=400',
        price=int(data.get('price', 0)),
        points_price=int(data.get('points_price', 0)),
        is_published=bool(data.get('is_published', True)),
        is_single_video=True,
        tags=data.get('tags', ''),
        created_by=creator.id
    )
    db.session.add(course)
    db.session.flush()

    lesson = Lesson(
        course_id=course.id,
        title=title,
        description=description,
        video_url=video_url,
        thumbnail_url=data.get('thumbnail_url'),
        tags=data.get('tags', ''),
        duration_seconds=int(data.get('duration_seconds', 0)),
        order_index=1
    )
    db.session.add(lesson)
    db.session.commit()

    return jsonify({'message': 'Single video uploaded successfully', 'course': course.to_dict()}), 201


@api_blueprint.route('/playlists', methods=['POST'])
@creator_required
def create_playlist():
    return create_course()


@api_blueprint.route('/playlists/<int:course_id>/reorder', methods=['PUT'])
@creator_required
def reorder_playlist_lessons(course_id):
    course = Course.query.get_or_404(course_id)
    if course.created_by != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    lesson_ids = data.get('lesson_ids', [])

    for idx, lid in enumerate(lesson_ids):
        lesson = Lesson.query.filter_by(id=lid, course_id=course.id).first()
        if lesson:
            lesson.order_index = idx + 1

    db.session.commit()
    return jsonify({'message': 'Lessons reordered successfully', 'lessons': [l.to_dict() for l in course.lessons]})


@api_blueprint.route('/courses/<int:course_id>/publish', methods=['POST'])
@creator_required
def toggle_publish_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.created_by != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403

    course.is_published = not course.is_published
    db.session.commit()
    return jsonify({'message': 'Publish status updated', 'is_published': course.is_published})


@api_blueprint.route('/courses/<int:course_id>', methods=['DELETE'])
@creator_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.created_by != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(course)
    db.session.commit()
    return jsonify({'message': 'Course deleted successfully'})


# ─── Lesson / Video Management Routes ─────────────────────────────────────────

@api_blueprint.route('/courses/<int:course_id>/lessons', methods=['POST'])
@creator_required
def add_lesson(course_id):
    course = Course.query.get_or_404(course_id)
    if course.created_by != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    title = data.get('title', '').strip()
    video_url = data.get('video_url', '').strip()

    if not title or not video_url:
        return jsonify({'error': 'Lesson title and video URL are required.'}), 400

    order_index = len(course.lessons) + 1
    lesson = Lesson(
        course_id=course.id,
        title=title,
        description=data.get('description', ''),
        video_url=video_url,
        duration_seconds=int(data.get('duration_seconds', 0)),
        order_index=order_index
    )
    db.session.add(lesson)
    db.session.commit()

    return jsonify({'message': 'Lesson added successfully', 'lesson': lesson.to_dict()}), 201


@api_blueprint.route('/lessons/<int:lesson_id>', methods=['DELETE'])
@creator_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.course.created_by != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(lesson)
    db.session.commit()
    return jsonify({'message': 'Lesson deleted successfully'})


# ─── Enrollment & Progress Tracking ───────────────────────────────────────────

@api_blueprint.route('/enroll/<int:course_id>', methods=['POST'])
@login_required
def enroll(course_id):
    course = Course.query.get_or_404(course_id)
    user = User.query.get(session['user_id'])

    if Enrollment.query.filter_by(user_id=user.id, course_id=course_id).first():
        return jsonify({'error': 'Already enrolled in this course.'}), 409

    if course.price > 0:
        return jsonify({'error': 'This is a paid course. Please use purchase endpoint.'}), 403

    enrollment = Enrollment(user_id=user.id, course_id=course_id)
    db.session.add(enrollment)
    db.session.commit()

    return jsonify({'message': 'Enrolled successfully', 'enrollment': enrollment.to_dict()}), 201


@api_blueprint.route('/purchase-points/<int:course_id>', methods=['POST'])
@login_required
def purchase_with_points(course_id):
    course = Course.query.get_or_404(course_id)
    user = User.query.get(session['user_id'])

    if Enrollment.query.filter_by(user_id=user.id, course_id=course_id).first():
        return jsonify({'error': 'Already purchased this course.'}), 409

    if user.points < course.points_price:
        return jsonify({'error': f'Insufficient points. You need {course.points_price} points.'}), 402

    user.points -= course.points_price
    enrollment = Enrollment(user_id=user.id, course_id=course_id)
    db.session.add(enrollment)
    db.session.commit()

    return jsonify({'message': 'Course purchased with points!', 'points': user.points, 'enrollment': enrollment.to_dict()}), 201


@api_blueprint.route('/enrollments', methods=['GET'])
@login_required
def get_my_enrollments():
    enrollments = Enrollment.query.filter_by(user_id=session['user_id']).all()
    return jsonify({'enrollments': [e.to_dict() for e in enrollments]})


@api_blueprint.route('/progress/update', methods=['POST'])
@login_required
def update_progress():
    data = request.get_json() or {}
    lesson_id = data.get('lesson_id')
    timestamp = int(data.get('timestamp', 0))
    is_completed = bool(data.get('is_completed', False))

    if not lesson_id:
        return jsonify({'error': 'lesson_id is required.'}), 400

    lesson = Lesson.query.get_or_404(lesson_id)
    user_id = session['user_id']

    # Update or create LessonProgress
    lp = LessonProgress.query.filter_by(user_id=user_id, lesson_id=lesson_id).first()
    if not lp:
        lp = LessonProgress(user_id=user_id, lesson_id=lesson_id)
        db.session.add(lp)

    lp.timestamp = timestamp
    if is_completed:
        lp.is_completed = True
    db.session.flush()

    # Update Enrollment
    enrollment = Enrollment.query.filter_by(user_id=user_id, course_id=lesson.course_id).first()
    if enrollment:
        enrollment.last_lesson_id = lesson_id
        enrollment.last_timestamp = timestamp
        
        # Calculate percentage
        total_lessons = len(lesson.course.lessons)
        if total_lessons > 0:
            completed_count = LessonProgress.query.join(Lesson).filter(
                LessonProgress.user_id == user_id,
                LessonProgress.is_completed == True,
                Lesson.course_id == lesson.course_id
            ).count()
            enrollment.completed_lessons_count = completed_count
            enrollment.progress_percentage = int((completed_count / total_lessons) * 100)

    db.session.commit()
    return jsonify({'message': 'Progress saved', 'progress': lp.to_dict()})


@api_blueprint.route('/progress/<int:course_id>', methods=['GET'])
@login_required
def get_course_progress(course_id):
    user_id = session['user_id']
    enrollment = Enrollment.query.filter_by(user_id=user_id, course_id=course_id).first()
    if not enrollment:
        return jsonify({'enrolled': False})

    progress_list = LessonProgress.query.join(Lesson).filter(
        LessonProgress.user_id == user_id,
        Lesson.course_id == course_id
    ).all()

    return jsonify({
        'enrolled': True,
        'enrollment': enrollment.to_dict(),
        'lessons_progress': [p.to_dict() for p in progress_list]
    })


# ─── Google OAuth & Calendar Routes ──────────────────────────────────────────


@api_blueprint.route('/auth/google/disconnect', methods=['POST'])
@creator_required
def google_auth_disconnect():
    user = User.query.get(session['user_id'])
    user.is_google_connected = False
    user.google_access_token = None
    user.google_refresh_token = None
    user.google_token_expiry = None
    db.session.commit()
    return jsonify({'message': 'Disconnected from Google Calendar', 'user': user.to_dict()})


# ─── Live Session Management Routes ───────────────────────────────────────────

@api_blueprint.route('/live', methods=['GET'])
def get_live_sessions():
    sessions = LiveSession.query.filter(
        LiveSession.is_published == True,
        LiveSession.status.in_(['scheduled', 'live']),
        LiveSession.cancelled_at.is_(None)
    ).order_by(LiveSession.scheduled_at.asc()).all()
    return jsonify({'sessions': [s.to_dict() for s in sessions]})


@api_blueprint.route('/live', methods=['POST'])
@creator_required
def create_live_session():
    try:
        data = request.get_json() or {}
        title = data.get('title', '').strip()
        topic = data.get('topic', '').strip()
        scheduled_at_str = data.get('scheduled_at', '')

        if not title or not topic or not scheduled_at_str:
            return jsonify({'error': 'Title, topic, and scheduled date/time are required.'}), 400

        try:
            scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', ''))
        except Exception as dt_err:
            traceback.print_exc()
            return jsonify({'error': f'Invalid datetime format: {str(dt_err)}'}), 400

        creator = User.query.get(session['user_id'])
        if not creator:
            return jsonify({'error': 'Creator user account not found.'}), 404

        # Pre-validate Google OAuth Connection
        if not creator.is_google_connected or not creator.google_access_token:
            return jsonify({'error': 'Google Calendar authentication required. Please click "Connect Google Calendar" in Profile settings first.'}), 400

        duration_minutes = int(data.get('duration_minutes', 60))
        description = data.get('description', '')

        # Create Google Calendar Event & generate real Google Meet Link
        google_event_id, meet_link, error_msg = create_google_calendar_event(
            creator, db, title, description, scheduled_at, duration_minutes
        )

        if error_msg or not meet_link:
            current_app.logger.error(f"Google Calendar API Failure: {error_msg}")
            return jsonify({'error': error_msg or 'Failed to create Google Meet event.'}), 400

        new_session = LiveSession(
            title=title,
            description=description,
            topic=topic,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            max_students=int(data.get('max_students', 50)),
            price=int(data.get('price', 0)),
            meeting_link=meet_link,
            google_event_id=google_event_id,
            status='scheduled',
            creator_started=False,
            is_published=True,
            created_by=creator.id
        )

        try:
            db.session.add(new_session)
            db.session.commit()
        except Exception as db_err:
            db.session.rollback()
            traceback.print_exc()
            current_app.logger.error(f"Database insertion error: {db_err}")
            return jsonify({'error': f'Database error saving session: {str(db_err)}'}), 500

        return jsonify({'message': 'Live session published successfully with Google Meet link', 'session': new_session.to_dict()}), 201

    except Exception as exc:
        traceback.print_exc()
        current_app.logger.error(f"Unexpected error in create_live_session: {exc}")
        return jsonify({'error': f'Server error: {str(exc)}'}), 500


@api_blueprint.route('/live/<int:session_id>/status', methods=['POST'])
@creator_required
def update_live_session_status(session_id):
    live_sess = LiveSession.query.get_or_404(session_id)
    if live_sess.created_by != session['user_id']:
        return jsonify({'error': 'Only the creator who created this session can change its status.'}), 403

    data = request.get_json() or {}
    new_status = data.get('status', '').strip().lower()
    if new_status not in ['scheduled', 'live', 'ended', 'cancelled']:
        return jsonify({'error': 'Invalid status choice.'}), 400

    if new_status == 'live':
        live_sess.creator_started = True
    elif new_status == 'cancelled':
        live_sess.cancelled_at = datetime.utcnow()

    live_sess.status = new_status
    live_sess.updated_at = datetime.utcnow()
    db.session.commit()

    creator = User.query.get(session['user_id'])
    # Send email notifications on status change
    for b in live_sess.bookings:
        if b.user:
            if new_status == 'cancelled':
                send_notification_email(
                    recipient_email=b.user.email,
                    subject=f"Cancelled: {live_sess.title}",
                    message_body=f"Hi {b.user.name},\n\nThe live session '{live_sess.title}' scheduled for {live_sess.scheduled_at.isoformat()} has been cancelled by instructor {creator.name}.\n\nNexora Support"
                )
            elif new_status == 'live':
                send_notification_email(
                    recipient_email=b.user.email,
                    subject=f"LIVE NOW: {live_sess.title}",
                    message_body=f"Hi {b.user.name},\n\nInstructor {creator.name} has started the live session '{live_sess.title}'!\n\nJoin now: {live_sess.meeting_link}"
                )

    if new_status == 'cancelled' and live_sess.google_event_id:
        delete_google_calendar_event(creator, db, live_sess.google_event_id)

    return jsonify({
        'message': f'Session status updated to {new_status}',
        'session': live_sess.to_dict()
    })


@api_blueprint.route('/live/<int:session_id>', methods=['PUT'])
@creator_required
def edit_live_session(session_id):
    live_sess = LiveSession.query.get_or_404(session_id)
    if live_sess.created_by != session['user_id']:
        return jsonify({'error': 'Unauthorized to edit this session.'}), 403

    data = request.get_json() or {}
    if 'title' in data: live_sess.title = data['title'].strip()
    if 'topic' in data: live_sess.topic = data['topic'].strip()
    if 'description' in data: live_sess.description = data['description'].strip()
    if 'duration_minutes' in data: live_sess.duration_minutes = int(data['duration_minutes'])
    if 'max_students' in data: live_sess.max_students = int(data['max_students'])
    if 'price' in data: live_sess.price = int(data['price'])

    if 'scheduled_at' in data and data['scheduled_at']:
        try:
            live_sess.scheduled_at = datetime.fromisoformat(data['scheduled_at'].replace('Z', ''))
        except Exception:
            pass

    db.session.commit()
    return jsonify({'message': 'Session updated successfully', 'session': live_sess.to_dict()})


@api_blueprint.route('/live/<int:session_id>/students', methods=['GET'])
@creator_required
def get_live_session_students(session_id):
    live_sess = LiveSession.query.get_or_404(session_id)
    if live_sess.created_by != session['user_id']:
        return jsonify({'error': 'Unauthorized.'}), 403

    students = [{'id': b.user.id, 'name': b.user.name, 'email': b.user.email, 'booked_at': b.booked_at.isoformat()} for b in live_sess.bookings if b.user]
    return jsonify({'session': live_sess.to_dict(), 'students': students})


@api_blueprint.route('/live/book/<int:session_id>', methods=['POST'])
@login_required
def book_live_session(session_id):
    user = User.query.get(session['user_id'])
    live_sess = LiveSession.query.get_or_404(session_id)

    if Booking.query.filter_by(user_id=user.id, session_id=session_id).first():
        return jsonify({'error': 'You have already booked this live session.'}), 409

    booking = Booking(user_id=user.id, session_id=session_id)
    db.session.add(booking)
    db.session.commit()

    # Send Booking Confirmation Email
    send_notification_email(
        recipient_email=user.email,
        subject=f"Booking Confirmation: {live_sess.title}",
        message_body=f"Hi {user.name},\n\nYour seat for '{live_sess.title}' hosted by {live_sess.creator.name} is confirmed!\n\nDate & Time: {live_sess.scheduled_at.isoformat()}\nTopic: {live_sess.topic}\nGoogle Meet Link: {live_sess.meeting_link}\n\nHappy Learning!\nNexora Team"
    )

    return jsonify({'message': 'Session booked successfully', 'booking': booking.to_dict()}), 201


@api_blueprint.route('/bookings/my', methods=['GET'])
@login_required
def get_my_bookings():
    bookings = Booking.query.filter_by(user_id=session['user_id']).all()
    return jsonify({'bookings': [b.to_dict() for b in bookings]})


# ─── 1-on-1 Student Live Requests Routes ──────────────────────────────────────

@api_blueprint.route('/requests/live', methods=['POST'])
@login_required
def create_session_request():
    data = request.get_json() or {}
    creator_id = data.get('creator_id')
    topic = data.get('topic', '').strip()
    description = data.get('description', '').strip()
    preferred_date = data.get('preferred_date', '').strip()
    preferred_time = data.get('preferred_time', '').strip()

    if not creator_id or not topic or not description or not preferred_date or not preferred_time:
        return jsonify({'error': 'All request details are required.'}), 400

    req = SessionRequest(
        student_id=session['user_id'],
        creator_id=creator_id,
        topic=topic,
        description=description,
        preferred_date=preferred_date,
        preferred_time=preferred_time,
        duration_minutes=int(data.get('duration_minutes', 45)),
        status='pending'
    )
    db.session.add(req)
    db.session.commit()

    return jsonify({'message': '1-on-1 session request submitted to creator', 'request': req.to_dict()}), 201


@api_blueprint.route('/requests/creator', methods=['GET'])
@creator_required
def get_creator_requests():
    requests_list = SessionRequest.query.filter_by(creator_id=session['user_id']).order_by(SessionRequest.created_at.desc()).all()
    return jsonify({'requests': [r.to_dict() for r in requests_list]})


@api_blueprint.route('/requests/<int:request_id>/action', methods=['POST'])
@creator_required
def process_session_request(request_id):
    data = request.get_json() or {}
    action = data.get('action')  # 'accept', 'decline', 'suggest'

    req = SessionRequest.query.get_or_404(request_id)
    if req.creator_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403

    if action == 'accept':
        req.status = 'accepted'
        # Automatically create live session slot & booking
        try:
            sched_dt = datetime.strptime(f"{req.preferred_date} {req.preferred_time}", "%Y-%m-%d %H:%M")
        except Exception:
            sched_dt = datetime.utcnow()

        ls = LiveSession(
            title=f"1-on-1: {req.topic}",
            description=req.description,
            topic=req.topic,
            scheduled_at=sched_dt,
            duration_minutes=req.duration_minutes,
            max_students=1,
            meeting_link='https://meet.google.com/new',
            created_by=req.creator_id,
            is_published=False
        )
        db.session.add(ls)
        db.session.flush()

        booking = Booking(user_id=req.student_id, session_id=ls.id)
        db.session.add(booking)

    elif action == 'decline':
        req.status = 'declined'
    elif action == 'suggest':
        req.status = 'suggested'
        req.suggested_time = data.get('suggested_time', '')

    db.session.commit()
    return jsonify({'message': f'Request {req.status}', 'request': req.to_dict()})


# ─── Dashboard Stats & Analytics Routes ───────────────────────────────────────

@api_blueprint.route('/dashboard/learner', methods=['GET'])
@login_required
def learner_stats():
    user = User.query.get(session['user_id'])
    enrollments = Enrollment.query.filter_by(user_id=user.id).all()
    bookings = Booking.query.filter_by(user_id=user.id).all()

    active_bookings = [b for b in bookings if b.session and b.session.status != 'cancelled' and not b.session.cancelled_at]
    completed = [e for e in enrollments if e.progress_percentage == 100]
    continue_watching = [e for e in enrollments if 0 < e.progress_percentage < 100]

    return jsonify({
        'points': user.points,
        'enrolled_count': len(enrollments),
        'completed_count': len(completed),
        'continue_watching': [e.to_dict() for e in continue_watching],
        'enrolled_courses': [e.to_dict() for e in enrollments],
        'upcoming_bookings': [b.to_dict() for b in active_bookings]
    })


@api_blueprint.route('/dashboard/creator', methods=['GET'])
@creator_required
def creator_stats():
    user = User.query.get(session['user_id'])
    my_courses = Course.query.filter_by(created_by=user.id).all()
    my_sessions = LiveSession.query.filter(
        LiveSession.created_by == user.id,
        LiveSession.status != 'cancelled',
        LiveSession.cancelled_at.is_(None)
    ).all()
    my_requests = SessionRequest.query.filter_by(creator_id=user.id, status='pending').all()

    playlists = [c.to_dict() for c in my_courses if not c.is_single_video]
    single_videos = [c.to_dict() for c in my_courses if c.is_single_video]

    total_published = len([c for c in my_courses if c.is_published])
    total_students = sum(len(c.enrollments) for c in my_courses)
    revenue = sum(c.price * len(c.enrollments) for c in my_courses)
    points_earned = sum(c.points_price * len(c.enrollments) for c in my_courses) + (total_students * 100)

    # Average rating calculation
    all_reviews = []
    for c in my_courses:
        all_reviews.extend(c.reviews)
    avg_rating = round(sum(r.rating for r in all_reviews) / len(all_reviews), 1) if all_reviews else 0.0

    return jsonify({
        'published_courses_count': total_published,
        'total_students': total_students,
        'revenue': revenue,
        'points_earned': points_earned,
        'avg_rating': avg_rating,
        'pending_requests_count': len(my_requests),
        'my_courses': [c.to_dict() for c in my_courses],
        'playlists': playlists,
        'single_videos': single_videos,
        'my_sessions': [s.to_dict() for s in my_sessions],
        'recent_reviews': [r.to_dict() for r in all_reviews[-5:]]
    })


# ─── Collaboration & Community Feed ──────────────────────────────────────────

@api_blueprint.route('/collaboration', methods=['GET'])
@login_required
def get_collaboration_feed():
    posts = CollaborationPost.query.order_by(CollaborationPost.created_at.desc()).all()
    return jsonify({'posts': [p.to_dict() for p in posts]})


@api_blueprint.route('/collaboration', methods=['POST'])
@login_required
def create_collaboration_post():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    required_skills = data.get('required_skills', '').strip()
    contact_info = data.get('contact_info', '').strip()

    if not title or not description or not required_skills or not contact_info:
        return jsonify({'error': 'All fields are required.'}), 400

    post = CollaborationPost(
        title=title,
        description=description,
        required_skills=required_skills,
        members_needed=int(data.get('members_needed', 1)),
        contact_info=contact_info,
        user_id=session['user_id']
    )
    db.session.add(post)
    db.session.commit()
    return jsonify({'message': 'Collaboration request posted', 'post': post.to_dict()}), 201
