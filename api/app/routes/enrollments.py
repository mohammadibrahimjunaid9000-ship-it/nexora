"""
Nexora API - Course Enrollment Endpoints
Provides authenticated course enrollment and enrollment status retrieval for learners.
Strictly reuses existing EnrollmentService, require_learner / get_current_user dependencies,
and live Supabase columns without schema mutations.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.app.auth.dependencies import get_current_user, require_learner
from api.app.auth.schemas import UserResponse
from api.app.schemas.enrollments import (
    EnrollmentResponse,
    EnrollmentStatusResponse,
    CreateEnrollmentRequest,
)
from api.app.services.enrollments import (
    get_enrollment_service,
    EnrollmentService,
    CourseNotFoundError,
    DuplicateEnrollmentError,
)

logger = logging.getLogger("nexora.api.enrollments")

router = APIRouter(tags=["Enrollments"])


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


@router.post(
    "/api/v1/courses/{course_id}/enroll",
    status_code=status.HTTP_201_CREATED,
    response_model=EnrollmentResponse,
    summary="Enroll authenticated learner in a course"
)
def enroll_in_course(
    course_id: str = Path(..., description="Target course identifier (positive integer)"),
    current_user: UserResponse = Depends(require_learner),
    enrollment_service: EnrollmentService = Depends(get_enrollment_service),
) -> EnrollmentResponse:
    """
    Enrolls the currently authenticated learner in the specified course.
    - Requires authenticated session (HttpOnly cookie).
    - Requires 'learner' role.
    - Anti-IDOR: Derives student user ID strictly from the authenticated token context.
    - Validates course existence.
    - Deterministically rejects duplicate enrollments with HTTP 409 Conflict.
    """
    parsed_course_id = _parse_course_id(course_id)
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]

    try:
        enrollment = enrollment_service.create_enrollment(
            user_id=user_id,
            course_id=parsed_course_id,
        )
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found."
        )
    except DuplicateEnrollmentError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already enrolled in this course."
        )
    except Exception as e:
        logger.error(f"Database error during course enrollment: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    return EnrollmentResponse(**enrollment)


@router.get(
    "/api/v1/courses/{course_id}/enrollment-status",
    status_code=status.HTTP_200_OK,
    response_model=EnrollmentStatusResponse,
    summary="Check enrollment status for current authenticated user"
)
@router.get(
    "/api/v1/courses/{course_id}/enrollment",
    status_code=status.HTTP_200_OK,
    response_model=EnrollmentStatusResponse,
    summary="Check enrollment status for current authenticated user (alias)",
    include_in_schema=False
)
def get_enrollment_status(
    course_id: str = Path(..., description="Target course identifier (positive integer)"),
    current_user: UserResponse = Depends(get_current_user),
    enrollment_service: EnrollmentService = Depends(get_enrollment_service),
) -> EnrollmentStatusResponse:
    """
    Checks whether the currently authenticated user is enrolled in the specified course.
    - Requires authenticated session.
    - Anti-IDOR: Derives student user ID strictly from the authenticated token context.
    - Returns is_enrolled: true/false with enrollment details if enrolled.
    """
    parsed_course_id = _parse_course_id(course_id)
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]

    try:
        status_data = enrollment_service.get_enrollment_status(
            user_id=user_id,
            course_id=parsed_course_id,
        )
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found."
        )
    except Exception as e:
        logger.error(f"Database error during enrollment status check: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    enrollment_rec = status_data.get("enrollment")
    return EnrollmentStatusResponse(
        is_enrolled=status_data["is_enrolled"],
        course_id=parsed_course_id,
        enrollment=EnrollmentResponse(**enrollment_rec) if enrollment_rec else None,
    )


@router.post(
    "/api/v1/enrollments",
    status_code=status.HTTP_201_CREATED,
    response_model=EnrollmentResponse,
    summary="Enroll authenticated learner in a course (body-based endpoint)"
)
def enroll_in_course_body(
    payload: CreateEnrollmentRequest,
    current_user: UserResponse = Depends(require_learner),
    enrollment_service: EnrollmentService = Depends(get_enrollment_service),
) -> EnrollmentResponse:
    """
    Alternative endpoint to enroll via JSON body payload containing course_id.
    """
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]

    try:
        enrollment = enrollment_service.create_enrollment(
            user_id=user_id,
            course_id=payload.course_id,
        )
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found."
        )
    except DuplicateEnrollmentError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already enrolled in this course."
        )
    except Exception as e:
        logger.error(f"Database error during course enrollment: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    return EnrollmentResponse(**enrollment)
