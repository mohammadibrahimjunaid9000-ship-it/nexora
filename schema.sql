-- =========================================================
-- Nexora Learning Platform - Production Database Schema
-- Compatible with PostgreSQL (Supabase) and SQLite
-- =========================================================

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    google_id VARCHAR(255) UNIQUE,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(256),
    role VARCHAR(20) CHECK (role IN ('learner', 'creator', 'admin')),
    points INT DEFAULT 0,
    avatar_url VARCHAR(500),
    headline VARCHAR(200),
    bio TEXT,
    skills VARCHAR(500),
    profile_banner VARCHAR(500),
    social_links TEXT,
    reset_token VARCHAR(255),
    reset_token_expiry TIMESTAMP,
    google_access_token TEXT,
    google_refresh_token TEXT,
    google_token_expiry TIMESTAMP,
    is_google_connected BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Courses Table
CREATE TABLE IF NOT EXISTS courses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    instructor VARCHAR(100) NOT NULL,
    category VARCHAR(50) DEFAULT 'General',
    level VARCHAR(30) DEFAULT 'Beginner',
    duration VARCHAR(50) DEFAULT 'Self-paced',
    thumbnail_url VARCHAR(500),
    price INT DEFAULT 0,
    points_price INT DEFAULT 0,
    is_published BOOLEAN DEFAULT FALSE,
    is_single_video BOOLEAN DEFAULT FALSE,
    tags VARCHAR(300),
    views_count INT DEFAULT 0,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. Lessons / Videos Table
CREATE TABLE IF NOT EXISTS lessons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    video_url VARCHAR(500) NOT NULL,
    thumbnail_url VARCHAR(500),
    tags VARCHAR(300),
    duration_seconds INT DEFAULT 0,
    order_index INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

-- 4. Enrollments Table
CREATE TABLE IF NOT EXISTS enrollments (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    last_lesson_id INT REFERENCES lessons(id) ON DELETE SET NULL,
    last_timestamp INT DEFAULT 0,
    progress_percentage INT DEFAULT 0,
    completed_lessons_count INT DEFAULT 0,
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id)
);

-- 5. Lesson Progress Tracking Table
CREATE TABLE IF NOT EXISTS lesson_progress (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    timestamp INT DEFAULT 0,
    is_completed BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, lesson_id)
);

-- 6. Live Sessions Table
CREATE TABLE IF NOT EXISTS live_sessions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    topic VARCHAR(100) NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    duration_minutes INT DEFAULT 60,
    max_students INT DEFAULT 50,
    price INT DEFAULT 0,
    meeting_link VARCHAR(500),
    google_event_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'scheduled',
    creator_started BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMP,
    is_published BOOLEAN DEFAULT TRUE,
    created_by INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Bookings Table
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id INT NOT NULL REFERENCES live_sessions(id) ON DELETE CASCADE,
    booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, session_id)
);

-- 8. Student 1-on-1 Live Requests Table
CREATE TABLE IF NOT EXISTS session_requests (
    id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    creator_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    preferred_date DATE NOT NULL,
    preferred_time TIME NOT NULL,
    duration_minutes INT DEFAULT 45,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'suggested')),
    suggested_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Collaboration Posts Table
CREATE TABLE IF NOT EXISTS collaboration_posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    required_skills VARCHAR(300) NOT NULL,
    members_needed INT DEFAULT 1,
    contact_info VARCHAR(200) NOT NULL,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Reviews Table
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
