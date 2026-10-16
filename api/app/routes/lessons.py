"""
Nexora API - Lesson Endpoints
Provides public course curriculum lesson discovery and course-scoped lesson detail retrieval.
Strictly reuses existing LessonService and Supabase live boundary without schema mutations.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.app.schemas.lessons import (
    LessonItem,
    LessonDetail,
    CourseLessonsResponse,
)
from api.app.services.lessons import (
    get_lesson_service,
    LessonService,
    CourseNotFoundError,
)
from api.app.services.courses import get_course_service, CourseService

logger = logging.getLogger("nexora.api.lessons")

router = APIRouter(tags=["Lessons"])


def _parse_course_id(course_id: str) -> int:
    """Safely validate course ID as a positive integer."""
    try:
        parsed_id = int(course_id)
        if parsed_id <= 0:
            raise ValueError("course_id must be a positive integer.")
        return parsed_id
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found."
        )


def _parse_lesson_id(lesson_id: str) -> int:
    """Safely validate lesson ID as a positive integer."""
    try:
        parsed_id = int(lesson_id)
        if parsed_id <= 0:
            raise ValueError("lesson_id must be a positive integer.")
        return parsed_id
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found."
        )


@router.get(
    "/api/v1/courses/{course_id}/lessons",
    status_code=status.HTTP_200_OK,
    response_model=CourseLessonsResponse,
    summary="Get course lessons list"
)
def get_course_lessons(
    course_id: str = Path(..., description="Target course identifier (positive integer)"),
    lesson_service: LessonService = Depends(get_lesson_service),
) -> CourseLessonsResponse:
    """
    Retrieves public curriculum lessons for a specific course.
    - Verifies course exists (returns 404 if not found).
    - Returns safe lesson list conforming to live database schema.
    - Controlled 503 if database service is unavailable.
    """
    parsed_course_id = _parse_course_id(course_id)

    try:
        raw_lessons = lesson_service.get_course_lessons(parsed_course_id)
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found."
        )
    except Exception as e:
        logger.error(f"Database error during get_course_lessons: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    items = [LessonItem(**item) for item in raw_lessons]
    return CourseLessonsResponse(
        course_id=parsed_course_id,
        lessons=items,
        total=len(items)
    )


@router.get(
    "/api/v1/courses/{course_id}/lessons/{lesson_id}",
    status_code=status.HTTP_200_OK,
    response_model=LessonDetail,
    summary="Get course-specific lesson detail"
)
def get_course_lesson_detail(
    course_id: str = Path(..., description="Target course identifier (positive integer)"),
    lesson_id: str = Path(..., description="Target lesson identifier (positive integer)"),
    course_service: CourseService = Depends(get_course_service),
    lesson_service: LessonService = Depends(get_lesson_service),
) -> LessonDetail:
    """
    Retrieves lesson detail under a specific course path.
    - Verifies course existence (controlled 404 if missing).
    - Verifies lesson belongs to the course (controlled 404 if mismatch or absent).
    - Controlled 503 if database service is unavailable.
    """
    parsed_course_id = _parse_course_id(course_id)
    parsed_lesson_id = _parse_lesson_id(lesson_id)

    try:
        course = course_service.get_by_id(parsed_course_id)
    except Exception as e:
        logger.error(f"Database error checking course during get_course_lesson_detail: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found."
        )

    try:
        lesson = lesson_service.get_lesson_by_id(parsed_lesson_id, parsed_course_id)
    except Exception as e:
        logger.error(f"Database error checking lesson during get_course_lesson_detail: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found in specified course."
        )

    return LessonDetail(**lesson)
