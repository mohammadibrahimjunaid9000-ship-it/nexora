# Nexora Architecture Documentation

## Overview
Nexora is a futuristic, AI-driven learning platform built with Flask, SQLAlchemy, and a decoupled modern Web UI.

## Modular Directory Layout

- `backend/`: Flask application, models, routes, configuration, database schemas, services, and utilities.
- `frontend/`: User interface templates and static assets (CSS, JS, fonts, icons, images).
- `uploads/`: Dedicated directory for user-uploaded media (course thumbnails, avatars, temporary files).
- `docs/`: System architecture guidelines and API endpoint reference documentation.
- `tests/`: Automated unit and integration test suite.

## Tech Stack
- **Backend Framework**: Python Flask 3.0+
- **Database / ORM**: SQLite / PostgreSQL (Supabase) via Flask-SQLAlchemy
- **Frontend Stack**: Vanilla HTML5, Modern CSS3 (Glassmorphism design system), Vanilla ES6 JS
- **Authentication**: Role-based session management (`learner` and `creator` roles)
