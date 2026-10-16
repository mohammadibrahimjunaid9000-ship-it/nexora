"""
Nexora API - Enrollment Service
Encapsulates database operations on the existing Supabase enrollments table.
Strictly reuses the 6 authoritative live columns:
id, user_id, course_id, progress, completed_lessons, enrolled_at.
"""

from typing import Optional, Dict, Any
import logging
from api.app.services.supabase import get_supabase_service, SupabaseService
from api.app.services.courses import get_course_service, CourseService

logger = logging.getLogger("nexora.api.enrollments")

ENROLLMENT_COLUMNS = "id,user_id,course_id,progress,completed_lessons,enrolled_at"


class CourseNotFoundError(Exception):
    """Raised when the target course does not exist."""
    pass


class DuplicateEnrollmentError(Exception):
    """Raised when a learner is already enrolled in the specified course."""
    pass


class EnrollmentService:
    """Service layer for authoritative course enrollment operations on Supabase."""

    def __init__(
        self,
        supabase_service: Optional[SupabaseService] = None,
        course_service: Optional[CourseService] = None,
    ) -> None:
        self._supabase = supabase_service or get_supabase_service()
        self._course_service = course_service or get_course_service()

    @property
    def client(self):
        return self._supabase.client

    def get_enrollment(self, user_id: int, course_id: int) -> Optional[Dict[str, Any]]:
        """
        Check if a user is enrolled in a specific course.
        Returns the enrollment record dict or None if not found.
        """
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        try:
            res = (
                self.client.table("enrollments")
                .select(ENROLLMENT_COLUMNS)
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .limit(1)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Error checking enrollment: {type(e).__name__}")
            raise

    def create_enrollment(self, user_id: int, course_id: int) -> Dict[str, Any]:
        """
        Enroll an authenticated learner in a course.
        Validates course existence and uniqueness before inserting.
        Prevents duplicate enrollment deterministically.
        """
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        # 1. Verify course existence
        course = self._course_service.get_by_id(course_id)
        if not course:
            raise CourseNotFoundError("Course not found.")

        # 2. Check for existing enrollment
        existing = self.get_enrollment(user_id, course_id)
        if existing:
            raise DuplicateEnrollmentError("Already enrolled in this course.")

        # 3. Insert new enrollment record with live verified columns
        payload = {
            "user_id": user_id,
            "course_id": course_id,
            "progress": 0,
            "completed_lessons": 0,
        }

        try:
            res = self.client.table("enrollments").insert(payload).execute()
            if not res.data:
                raise RuntimeError("Failed to record enrollment in database.")
            return res.data[0]
        except Exception as e:
            err_str = str(e).lower()
            if "unique" in err_str or "duplicate" in err_str or "23505" in err_str:
                logger.info(f"Uniqueness constraint triggered on duplicate enrollment: user {user_id}, course {course_id}")
                raise DuplicateEnrollmentError("Already enrolled in this course.")
            logger.error(f"Error creating enrollment: {type(e).__name__}")
            raise

    def get_enrollment_status(self, user_id: int, course_id: int) -> Dict[str, Any]:
        """
        Get enrollment status for an authenticated user on a specific course.
        """
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        course = self._course_service.get_by_id(course_id)
        if not course:
            raise CourseNotFoundError("Course not found.")

        enrollment = self.get_enrollment(user_id, course_id)
        return {
            "is_enrolled": enrollment is not None,
            "course_id": course_id,
            "enrollment": enrollment,
        }


# Singleton accessor
_enrollment_service_instance: Optional[EnrollmentService] = None


def get_enrollment_service() -> EnrollmentService:
    """Dependency provider / singleton accessor for EnrollmentService."""
    global _enrollment_service_instance
    if _enrollment_service_instance is None:
        _enrollment_service_instance = EnrollmentService()
    return _enrollment_service_instance
