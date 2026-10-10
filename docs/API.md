# Nexora API Documentation

Base URL: `/api`

## Authentication
- `POST /api/auth/register`: Create a new user account (`learner` or `creator`).
- `POST /api/auth/login`: Authenticate an existing user.
- `POST /api/auth/logout`: End active user session.
- `GET /api/auth/me`: Retrieve current logged-in user profile.

## Courses & Playlists
- `GET /api/courses`: Fetch list of courses with optional search/category filters.
- `POST /api/courses`: Create a new course (Creator privileges required).
- `DELETE /api/courses/<id>`: Delete a course (Creator privileges required).

## Live Sessions & Bookings
- `GET /api/live`: Fetch available live sessions.
- `POST /api/live`: Schedule a new live session (Creator only).
- `POST /api/live/book/<id>`: Book a seat for a live session.
- `GET /api/bookings/my`: Retrieve user's live session bookings.

## Enrollment & Collaboration
- `POST /api/enroll/<id>`: Enroll in a free course.
- `POST /api/purchase-points/<id>`: Purchase course with points.
- `GET /api/collaboration`: Fetch AI-ranked collaboration feed.
- `POST /api/collaboration`: Create a project collaboration request.
