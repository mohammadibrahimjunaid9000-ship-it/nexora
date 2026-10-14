"""
Nexora API - Course Catalog Endpoints
Provides public course catalog listing and detail retrieval.
Strictly reuses existing CourseService and Supabase live columns without schema mutations.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from api.app.schemas.courses import (
    CourseListItem,
    CourseDetailResponse,
    CourseListResponse,
)
from api.app.services.courses import get_course_service, CourseService

logger = logging.getLogger("nexora.api.courses")

router = APIRouter(prefix="/api/v1/courses", tags=["Courses"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=CourseListResponse,
    summary="List courses with optional search and filters"
)
def list_courses(
    search: Optional[str] = Query(None, max_length=100, description="Optional search query matching title or description"),
    category: Optional[str] = Query(None, max_length=50, description="Optional category filter"),
    level: Optional[str] = Query(None, max_length=30, description="Optional level filter"),
    course_service: CourseService = Depends(get_course_service),
) -> CourseListResponse:
    """
    Retrieves public course catalog listing.
    Supports search query and category / level filters.
    Does not require authentication.
    Returns safe course representations only.
    """
    try:
        courses = course_service.list_courses(
            search=search,
            category=category,
            level=level,
        )
    except Exception as e:
        logger.error(f"Database error during list_courses: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    items = [CourseListItem(**c) for c in courses]
    return CourseListResponse(courses=items, total=len(items))


@router.get(
    "/{course_id}",
    status_code=status.HTTP_200_OK,
    response_model=CourseDetailResponse,
    summary="Get course detail by ID"
)
def get_course_detail(
    course_id: str = Path(..., description="Target course identifier (positive integer)"),
    course_service: CourseService = Depends(get_course_service),
) -> CourseDetailResponse:
    """
    Retrieves public course detail information.
    Does not require authentication.
    Returns 404 if course does not exist or if course_id is invalid.
    """
    try:
        parsed_id = int(course_id)
        if parsed_id <= 0:
            raise ValueError("course_id must be a positive integer.")
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found."
        )

    try:
        course = course_service.get_by_id(parsed_id)
    except Exception as e:
        logger.error(f"Database error during get_course_detail: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found."
        )

    return CourseDetailResponse(**course)
