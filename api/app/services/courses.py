"""
Nexora API - Course Service
Encapsulates database operations on the existing Supabase courses table.
Strictly reuses the 14 authoritative live columns:
id, title, description, instructor, category, level, duration, thumbnail,
total_lessons, rating, price, points_price, created_by, created_at.
"""

from typing import Optional, Dict, Any, List, Union
import logging
import re
from api.app.services.supabase import get_supabase_service, SupabaseService

logger = logging.getLogger("nexora.api.courses")

COURSE_LIST_COLUMNS = "id,title,description,instructor,category,level,duration,thumbnail,total_lessons,rating,price,points_price,created_at"
COURSE_DETAIL_COLUMNS = "id,title,description,instructor,category,level,duration,thumbnail,total_lessons,rating,price,points_price,created_by,created_at"


class CourseService:
    """Service layer for authoritative course catalog operations on Supabase."""

    def __init__(self, supabase_service: Optional[SupabaseService] = None) -> None:
        self._supabase = supabase_service or get_supabase_service()

    @property
    def client(self):
        return self._supabase.client

    def list_courses(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List courses with optional search, category, and level filtering.
        Sorts descending by created_at.
        """
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        try:
            query = self.client.table("courses").select(COURSE_LIST_COLUMNS)

            if search:
                # Sanitize search term to prevent postgrest query syntax injection
                clean_search = re.sub(r'[,()"\\]', '', search.strip())
                if clean_search:
                    query = query.or_(f"title.ilike.%{clean_search}%,description.ilike.%{clean_search}%")

            if category:
                clean_cat = category.strip()
                if clean_cat:
                    query = query.ilike("category", clean_cat)

            if level:
                clean_lvl = level.strip()
                if clean_lvl:
                    query = query.ilike("level", clean_lvl)

            query = query.order("created_at", desc=True)
            res = query.execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error querying courses list: {type(e).__name__}")
            raise

    def get_by_id(self, course_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Fetch a single course by primary key ID.
        Returns course dictionary or None if not found.
        """
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        try:
            parsed_id = int(course_id)
            if parsed_id <= 0:
                return None
        except (ValueError, TypeError):
            return None

        try:
            res = self.client.table("courses").select(COURSE_DETAIL_COLUMNS).eq("id", parsed_id).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Error fetching course by ID: {type(e).__name__}")
            raise


# Singleton accessor
_course_service_instance: Optional[CourseService] = None


def get_course_service() -> CourseService:
    """Dependency provider / singleton accessor for CourseService."""
    global _course_service_instance
    if _course_service_instance is None:
        _course_service_instance = CourseService()
    return _course_service_instance
