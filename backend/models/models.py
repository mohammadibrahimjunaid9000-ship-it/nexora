"""
Nexora Learning Platform - Production Database Models
Defines User, Course, Lesson, Enrollment, LessonProgress, LiveSession, Booking, SessionRequest, CollaborationPost, and Review tables.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


import urllib.parse

class User(db.Model):
    """Represents a registered user (Learner, Creator, or Admin)."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=True)  # NULL for Google users
    role = db.Column(db.String(20), nullable=True)       # NULL until onboarding selection: 'learner', 'creator', 'admin'
    points = db.Column(db.Integer, default=0)
    avatar_url = db.Column(db.String(500), nullable=True)
    
    # Custom Profile Customization Fields
    headline = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    skills = db.Column(db.String(500), nullable=True)
    profile_banner = db.Column(db.String(500), nullable=True)
    social_links = db.Column(db.Text, nullable=True)

    # Reset Password Tokens
    reset_token = db.Column(db.String(255), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Google OAuth & Calendar Token Fields
    google_access_token = db.Column(db.Text, nullable=True)
    google_refresh_token = db.Column(db.Text, nullable=True)
    google_token_expiry = db.Column(db.DateTime, nullable=True)
    is_google_connected = db.Column(db.Boolean, default=False)

    # Relationships
    enrollments = db.relationship('Enrollment', back_populates='user', cascade='all, delete-orphan')
    created_courses = db.relationship('Course', back_populates='creator')
    live_sessions = db.relationship('LiveSession', back_populates='creator')
    bookings = db.relationship('Booking', back_populates='user', cascade='all, delete-orphan')
    collab_posts = db.relationship('CollaborationPost', back_populates='author', cascade='all, delete-orphan')
    student_requests = db.relationship('SessionRequest', foreign_keys='SessionRequest.student_id', back_populates='student', cascade='all, delete-orphan')
    creator_requests = db.relationship('SessionRequest', foreign_keys='SessionRequest.creator_id', back_populates='creator', cascade='all, delete-orphan')
    reviews = db.relationship('Review', back_populates='user', cascade='all, delete-orphan')

    def to_dict(self):
        completed_categories = [e.course.category for e in self.enrollments if e.progress_percentage == 100] if self.enrollments else []
        default_avatar = f"https://ui-avatars.com/api/?name={urllib.parse.quote(self.name or 'Nexora User')}&background=8b5cf6&color=fff"
        
        parsed_skills = [s.strip() for s in self.skills.split(',')] if self.skills else list(set(completed_categories))

        return {
            'id': self.id,
            'google_id': self.google_id,
            'name': self.name,
            'full_name': self.name,
            'email': self.email,
            'role': self.role,
            'points': self.points,
            'avatar_url': self.avatar_url or default_avatar,
            'profile_picture': self.avatar_url or default_avatar,
            'headline': self.headline or '',
            'bio': self.bio or '',
            'skills': parsed_skills,
            'skills_text': self.skills or '',
            'profile_banner': self.profile_banner or '',
            'is_google_connected': bool(self.is_google_connected and self.google_access_token),
            'google_calendar_connected': bool(self.is_google_connected and self.google_access_token),
            'google_email': self.email,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'created_at': self.joined_at.isoformat() if self.joined_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Course(db.Model):
    """Represents a course playlist or single video."""
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    instructor = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), default='General')
    level = db.Column(db.String(30), default='Beginner')
    duration = db.Column(db.String(50), default='Self-paced')
    thumbnail_url = db.Column(db.String(500), nullable=True)
    price = db.Column(db.Integer, default=0)
    points_price = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=False)
    is_single_video = db.Column(db.Boolean, default=False)
    tags = db.Column(db.String(300), nullable=True)
    views_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', back_populates='created_courses')
    lessons = db.relationship('Lesson', back_populates='course', cascade='all, delete-orphan', order_by='Lesson.order_index')
    enrollments = db.relationship('Enrollment', back_populates='course', cascade='all, delete-orphan')
    reviews = db.relationship('Review', back_populates='course', cascade='all, delete-orphan')

    def to_dict(self):
        avg_rating = 0.0
        if self.reviews:
            avg_rating = round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)

        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'instructor': self.instructor,
            'category': self.category,
            'level': self.level,
            'duration': self.duration,
            'thumbnail': self.thumbnail_url or 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&q=80&w=400&h=400',
            'price': self.price,
            'points_price': self.points_price,
            'is_published': self.is_published,
            'is_single_video': self.is_single_video,
            'tags': self.tags or '',
            'views_count': self.views_count,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'enrolled_count': len(self.enrollments),
            'lessons_count': len(self.lessons),
            'rating': avg_rating,
            'lessons': [l.to_dict() for l in self.lessons]
        }


class Lesson(db.Model):
    """Represents a video lesson inside a course/playlist or a single video content."""
    __tablename__ = 'lessons'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    video_url = db.Column(db.String(500), nullable=False)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    tags = db.Column(db.String(300), nullable=True)
    duration_seconds = db.Column(db.Integer, default=0)
    order_index = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship('Course', back_populates='lessons')
    progress_records = db.relationship('LessonProgress', back_populates='lesson', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'title': self.title,
            'description': self.description or '',
            'video_url': self.video_url,
            'thumbnail': self.thumbnail_url or '',
            'tags': self.tags or '',
            'duration_seconds': self.duration_seconds,
            'order_index': self.order_index,
            'created_at': self.created_at.isoformat()
        }


class Enrollment(db.Model):
    """Tracks learner course enrollment and progress state."""
    __tablename__ = 'enrollments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    last_lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=True)
    last_timestamp = db.Column(db.Integer, default=0)
    progress_percentage = db.Column(db.Integer, default=0)
    completed_lessons_count = db.Column(db.Integer, default=0)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='enrollments')
    course = db.relationship('Course', back_populates='enrollments')
    last_lesson = db.relationship('Lesson')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'course': self.course.to_dict(),
            'last_lesson_id': self.last_lesson_id,
            'last_timestamp': self.last_timestamp,
            'progress_percentage': self.progress_percentage,
            'completed_lessons_count': self.completed_lessons_count,
            'total_lessons': len(self.course.lessons),
            'enrolled_at': self.enrolled_at.isoformat()
        }


class LessonProgress(db.Model):
    """Tracks video timestamp and completion per lesson."""
    __tablename__ = 'lesson_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=False)
    timestamp = db.Column(db.Integer, default=0)
    is_completed = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lesson = db.relationship('Lesson', back_populates='progress_records')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'lesson_id': self.lesson_id,
            'timestamp': self.timestamp,
            'is_completed': self.is_completed,
            'updated_at': self.updated_at.isoformat()
        }


class LiveSession(db.Model):
    """Represents a creator live session slot."""
    __tablename__ = 'live_sessions'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    topic = db.Column(db.String(100), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    max_students = db.Column(db.Integer, default=50)
    price = db.Column(db.Integer, default=0)
    meeting_link = db.Column(db.String(500), nullable=True)
    google_event_id = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default='scheduled')
    creator_started = db.Column(db.Boolean, default=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    is_published = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', back_populates='live_sessions')
    bookings = db.relationship('Booking', back_populates='session', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description or '',
            'topic': self.topic,
            'scheduled_at': self.scheduled_at.isoformat(),
            'duration_minutes': self.duration_minutes,
            'max_students': self.max_students,
            'price': self.price,
            'meeting_link': self.meeting_link,
            'google_event_id': self.google_event_id or '',
            'status': self.status or 'scheduled',
            'creator_started': bool(self.creator_started),
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_published': self.is_published,
            'creator_name': self.creator.name if self.creator else 'Creator',
            'created_by': self.created_by,
            'booking_count': len(self.bookings),
            'students': [{'id': b.user.id, 'name': b.user.name, 'email': b.user.email, 'booked_at': b.booked_at.isoformat()} for b in self.bookings if b.user]
        }


class Booking(db.Model):
    """Tracks live session bookings."""
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('live_sessions.id'), nullable=False)
    booked_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='bookings')
    session = db.relationship('LiveSession', back_populates='bookings')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session': self.session.to_dict(),
            'booked_at': self.booked_at.isoformat()
        }


class SessionRequest(db.Model):
    """Tracks 1-on-1 live session requests from learners to creators."""
    __tablename__ = 'session_requests'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    preferred_date = db.Column(db.String(50), nullable=False)
    preferred_time = db.Column(db.String(50), nullable=False)
    duration_minutes = db.Column(db.Integer, default=45)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'declined', 'suggested'
    suggested_time = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User', foreign_keys=[student_id], back_populates='student_requests')
    creator = db.relationship('User', foreign_keys=[creator_id], back_populates='creator_requests')

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name,
            'creator_id': self.creator_id,
            'creator_name': self.creator.name,
            'topic': self.topic,
            'description': self.description,
            'preferred_date': self.preferred_date,
            'preferred_time': self.preferred_time,
            'duration_minutes': self.duration_minutes,
            'status': self.status,
            'suggested_time': self.suggested_time,
            'created_at': self.created_at.isoformat()
        }


class CollaborationPost(db.Model):
    """Represents project collaboration post."""
    __tablename__ = 'collaboration_posts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.String(300), nullable=False)
    members_needed = db.Column(db.Integer, default=1)
    contact_info = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', back_populates='collab_posts')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'required_skills': [s.strip() for s in self.required_skills.split(',')],
            'members_needed': self.members_needed,
            'contact_info': self.contact_info,
            'author_name': self.author.name,
            'created_at': self.created_at.isoformat()
        }


class Review(db.Model):
    """Represents a course review."""
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship('Course', back_populates='reviews')
    user = db.relationship('User', back_populates='reviews')

    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'user_name': self.user.name,
            'rating': self.rating,
            'comment': self.comment,
            'created_at': self.created_at.isoformat()
        }
