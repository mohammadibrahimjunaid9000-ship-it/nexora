"""
Nexora API - Course Enrollment Pydantic Schemas
Strictly validated request and response models for Stage 9 Course Enrollment operations.
Adheres strictly to the authoritative live database columns in Supabase:
id, user_id, course_id, progress, completed_lessons, enrolled_at.
"""

from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class EnrollmentResponse(BaseModel):
    """
    Authoritative representation of a course enrollment record.
    Exposes only verified live columns.
    Never exposes passwords, tokens, or private credentials.
    """
    model_config = ConfigDict(extra="ignore")

    id: int
    user_id: int
    course_id: int
    progress: int = 0
    completed_lessons: int = 0
    enrolled_at: Optional[Union[str, datetime]] = None


class EnrollmentStatusResponse(BaseModel):
    """
    Status response indicating whether the current authenticated user is enrolled in the course.
    """
    model_config = ConfigDict(extra="ignore")

    is_enrolled: bool
    course_id: int
    enrollment: Optional[EnrollmentResponse] = None


class CreateEnrollmentRequest(BaseModel):
    """
    Request model for body-based enrollment operations.
    """
    model_config = ConfigDict(extra="forbid")

    course_id: int = Field(..., gt=0, description="Course ID to enroll in")
