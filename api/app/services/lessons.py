"""
Nexora API - Lesson Service
Encapsulates database operations for lessons conforming strictly to the live database boundary.
Handles graceful fallback when the live Supabase schema does not have a lessons table.
"""

from typing import Optional, Dict, Any, List, Union
import logging

from api.app.services.supabase import get_supabase_service, SupabaseService
from api.app.services.courses import get_course_service, CourseService

logger = logging.getLogger("nexora.api.lessons")


class CourseNotFoundError(Exception):
    """Raised when the target course does not exist."""
    pass


class LessonNotFoundError(Exception):
    """Raised when the target lesson does not exist."""
    pass


class LessonService:
    """Service layer for authoritative lesson operations on Supabase."""

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

    def get_course_lessons(self, course_id: Union[int, str]) -> List[Dict[str, Any]]:
        """
        Retrieves all available lessons for a specific course.
        - Verifies that the course exists (raises CourseNotFoundError if missing).
        - Queries Supabase 'lessons' table.
        - If 'lessons' table is absent in live schema (e.g. PGRST205), returns [] gracefully.
        - Preserves database ordering if available.
        - Exposes only safe verified fields.
        """
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        try:
            cid = int(course_id)
            if cid <= 0:
                raise CourseNotFoundError("Course not found.")
        except (ValueError, TypeError):
            raise CourseNotFoundError("Course not found.")

        # 1. Verify course existence
        course = self._course_service.get_by_id(cid)
        if not course:
            raise CourseNotFoundError("Course not found.")

        # 2. Query lessons from Supabase table
        try:
            res = (
                self.client.table("lessons")
                .select("id,course_id,title,description")
                .eq("course_id", cid)
                .execute()
            )
            raw_lessons = res.data or []
            return [
                {
                    "id": item["id"],
                    "course_id": item["course_id"],
                    "title": item["title"],
                    "description": item.get("description"),
                }
                for item in raw_lessons
            ]
        except Exception as e:
            err_str = str(e).lower()
            if "pgrst205" in err_str or "could not find the table" in err_str or "schema cache" in err_str:
                logger.info(f"Lessons table not found in live schema. Returning empty lessons list for course {cid}.")
                return []
            logger.error(f"Error querying lessons for course {cid}: {type(e).__name__}")
            raise

    def get_lesson_by_id(
        self,
        lesson_id: Union[int, str],
        course_id: Union[int, str],
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a single lesson by ID scoped to its parent course.
        - Verifies that lesson belongs to the specified course.
        - If 'lessons' table is absent in live schema, returns None.
        - Returns safe lesson dict or None if not found.
        """
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        try:
            lid = int(lesson_id)
            if lid <= 0:
                return None
        except (ValueError, TypeError):
            return None

        try:
            target_cid = int(course_id)
            if target_cid <= 0:
                return None
        except (ValueError, TypeError):
            return None

        try:
            res = (
                self.client.table("lessons")
                .select("id,course_id,title,description")
                .eq("id", lid)
                .eq("course_id", target_cid)
                .limit(1)
                .execute()
            )
            if not res.data:
                return None

            item = res.data[0]
            return {
                "id": item["id"],
                "course_id": item["course_id"],
                "title": item["title"],
                "description": item.get("description"),
            }
        except Exception as e:
            err_str = str(e).lower()
            if "pgrst205" in err_str or "could not find the table" in err_str or "schema cache" in err_str:
                logger.info(f"Lessons table not found in live schema. Lesson {lid} not found.")
                return None
            logger.error(f"Error fetching lesson {lid} for course {target_cid}: {type(e).__name__}")
            raise


# Singleton accessor
_lesson_service_instance: Optional[LessonService] = None


def get_lesson_service() -> LessonService:
    """Dependency provider / singleton accessor for LessonService."""
    global _lesson_service_instance
    if _lesson_service_instance is None:
        _lesson_service_instance = LessonService()
    return _lesson_service_instance
