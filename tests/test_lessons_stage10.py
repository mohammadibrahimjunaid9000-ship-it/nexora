"""
Comprehensive Unit & Integration Tests for Phase 5 — Stage 10: Learning Foundation
Authoritative verification for lesson discovery, curriculum viewing, and database boundary.

Minimum Test Requirements:
1. course lessons can be retrieved
2. nonexistent course returns 404
3. invalid course ID is rejected
4. course-scoped lesson detail can be retrieved
5. nonexistent lesson returns 404
6. invalid lesson ID is rejected
7. database failure returns controlled 503
8. lesson/course relationship is strictly enforced
9. standalone lesson endpoint is removed (returns 404)
10. response contains only safe verified fields (no invented fields)
11. no arbitrary user ID controls access
12. no fabricated lesson records
13. live Supabase boundary verification (graceful fallback when table absent in schema cache)
"""

import unittest
from typing import Any, Dict, List, Optional, Union
from starlette.testclient import TestClient

from api.app.main import app
from api.app.schemas.lessons import LessonItem, LessonDetail, CourseLessonsResponse
from api.app.services.courses import get_course_service, CourseService
from api.app.services.lessons import (
    get_lesson_service,
    LessonService,
    CourseNotFoundError,
    LessonNotFoundError,
)
from api.app.services.supabase import get_supabase_service


class MockCourseServiceStage10:
    """Mock course service providing known courses for Stage 10 testing."""

    def __init__(self):
        self.courses: Dict[int, Dict[str, Any]] = {}
        self.simulate_db_failure = False

    def add_course(
        self,
        course_id: int,
        title: str = "Test Course",
        description: str = "Test Description",
    ) -> Dict[str, Any]:
        record = {
            "id": course_id,
            "title": title,
            "description": description,
            "instructor": "Jane Doe",
            "category": "Web Development",
            "level": "Beginner",
            "duration": "4 weeks",
            "thumbnail": "💻",
            "total_lessons": 10,
            "rating": 4.8,
            "price": 29,
            "points_price": 300,
            "created_by": 1,
            "created_at": "2026-10-14T00:00:00Z",
        }
        self.courses[course_id] = record
        return record

    def get_by_id(self, course_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("Database connection timed out.")
        try:
            cid = int(course_id)
            if cid <= 0:
                return None
        except (ValueError, TypeError):
            return None
        return self.courses.get(cid)


class MockLessonServiceStage10:
    """Mock lesson service verifying business logic and schema compliance."""

    def __init__(self, course_service: Optional[MockCourseServiceStage10] = None):
        self.course_service = course_service or MockCourseServiceStage10()
        self.lessons: Dict[int, Dict[str, Any]] = {}
        self.simulate_db_failure = False
        self._next_id = 1

    def add_lesson(
        self,
        course_id: int,
        title: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        lid = self._next_id
        self._next_id += 1
        record = {
            "id": lid,
            "course_id": course_id,
            "title": title,
            "description": description,
        }
        self.lessons[lid] = record
        return record

    def get_course_lessons(self, course_id: Union[int, str]) -> List[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("Database connection timed out.")

        try:
            cid = int(course_id)
            if cid <= 0:
                raise CourseNotFoundError("Course not found.")
        except (ValueError, TypeError):
            raise CourseNotFoundError("Course not found.")

        course = self.course_service.get_by_id(cid)
        if not course:
            raise CourseNotFoundError("Course not found.")

        matching = [l for l in self.lessons.values() if l["course_id"] == cid]
        return matching

    def get_lesson_by_id(
        self,
        lesson_id: Union[int, str],
        course_id: Union[int, str],
    ) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("Database connection timed out.")

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

        lesson = self.lessons.get(lid)
        if not lesson:
            return None

        if lesson["course_id"] != target_cid:
            return None

        return lesson


class TestLessonsStage10(unittest.TestCase):
    """Test suite for Lesson Discovery and Viewing API (Stage 10)."""

    def setUp(self):
        self.mock_course_service = MockCourseServiceStage10()
        self.mock_lesson_service = MockLessonServiceStage10(self.mock_course_service)

        # Seed valid courses
        self.course_1 = self.mock_course_service.add_course(1, "Web Dev Essentials")
        self.course_2 = self.mock_course_service.add_course(2, "Python Masterclass")

        # Seed valid lessons for course 1
        self.lesson_1 = self.mock_lesson_service.add_lesson(
            course_id=1,
            title="Introduction to Web Development",
            description="Overview of the modern web stack."
        )
        self.lesson_2 = self.mock_lesson_service.add_lesson(
            course_id=1,
            title="HTML5 Semantic Elements",
            description="Structuring pages using semantic HTML."
        )

        app.dependency_overrides[get_course_service] = lambda: self.mock_course_service
        app.dependency_overrides[get_lesson_service] = lambda: self.mock_lesson_service
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    # =========================================================================
    # 1. Course lessons can be retrieved
    # =========================================================================

    def test_01_get_course_lessons_success(self):
        """GET /api/v1/courses/{course_id}/lessons retrieves lessons for valid course."""
        res = self.client.get("/api/v1/courses/1/lessons")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["course_id"], 1)
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["lessons"]), 2)
        self.assertEqual(data["lessons"][0]["id"], self.lesson_1["id"])
        self.assertEqual(data["lessons"][0]["title"], "Introduction to Web Development")
        self.assertEqual(data["lessons"][1]["id"], self.lesson_2["id"])

    def test_02_get_course_lessons_empty(self):
        """GET /api/v1/courses/{course_id}/lessons returns empty list when course has no lessons."""
        res = self.client.get("/api/v1/courses/2/lessons")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["course_id"], 2)
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["lessons"], [])

    # =========================================================================
    # 2. Nonexistent course returns 404
    # =========================================================================

    def test_03_get_course_lessons_nonexistent_course(self):
        """GET /api/v1/courses/{course_id}/lessons returns 404 for nonexistent course."""
        res = self.client.get("/api/v1/courses/9999/lessons")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    # =========================================================================
    # 3. Invalid course ID is rejected
    # =========================================================================

    def test_04_get_course_lessons_invalid_course_id_non_numeric(self):
        """Non-numeric course ID returns controlled 404."""
        res = self.client.get("/api/v1/courses/not-a-number/lessons")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    def test_05_get_course_lessons_invalid_course_id_zero(self):
        """Zero course ID returns controlled 404."""
        res = self.client.get("/api/v1/courses/0/lessons")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    def test_06_get_course_lessons_invalid_course_id_negative(self):
        """Negative course ID returns controlled 404."""
        res = self.client.get("/api/v1/courses/-5/lessons")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    # =========================================================================
    # 4. Course-scoped lesson detail can be retrieved
    # =========================================================================

    def test_07_get_course_lesson_detail_success(self):
        """GET /api/v1/courses/{course_id}/lessons/{lesson_id} returns 200 and lesson details."""
        res = self.client.get(f"/api/v1/courses/1/lessons/{self.lesson_1['id']}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], self.lesson_1["id"])
        self.assertEqual(data["course_id"], 1)
        self.assertEqual(data["title"], "Introduction to Web Development")
        self.assertEqual(data["description"], "Overview of the modern web stack.")

    # =========================================================================
    # 5. Nonexistent lesson returns 404
    # =========================================================================

    def test_08_get_course_lesson_detail_not_found(self):
        """GET /api/v1/courses/{course_id}/lessons/{lesson_id} returns 404 for nonexistent lesson."""
        res = self.client.get("/api/v1/courses/1/lessons/99999")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Lesson not found", res.json()["detail"])

    # =========================================================================
    # 6. Nonexistent course on lesson detail returns 404
    # =========================================================================

    def test_09_get_course_lesson_detail_nonexistent_course(self):
        """GET /api/v1/courses/{course_id}/lessons/{lesson_id} returns 404 when course does not exist."""
        res = self.client.get(f"/api/v1/courses/9999/lessons/{self.lesson_1['id']}")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    # =========================================================================
    # 7. Invalid IDs are rejected
    # =========================================================================

    def test_10_get_course_lesson_detail_invalid_course_id(self):
        """Invalid course ID on lesson detail returns controlled 404."""
        res = self.client.get(f"/api/v1/courses/invalid-cid/lessons/{self.lesson_1['id']}")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    def test_11_get_course_lesson_detail_invalid_lesson_id(self):
        """Invalid lesson ID on lesson detail returns controlled 404."""
        res = self.client.get("/api/v1/courses/1/lessons/invalid-lid")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Lesson not found", res.json()["detail"])

    # =========================================================================
    # 8. Database failure returns controlled 503
    # =========================================================================

    def test_12_database_failure_on_course_lessons(self):
        """Simulated database failure on course lessons returns controlled 503."""
        self.mock_lesson_service.simulate_db_failure = True
        res = self.client.get("/api/v1/courses/1/lessons")
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    def test_13_database_failure_on_lesson_detail(self):
        """Simulated database failure on lesson detail returns controlled 503."""
        self.mock_lesson_service.simulate_db_failure = True
        res = self.client.get("/api/v1/courses/1/lessons/1")
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    # =========================================================================
    # 9. Lesson/course relationship mismatch is enforced
    # =========================================================================

    def test_14_lesson_course_mismatch_returns_404(self):
        """GET /api/v1/courses/{cid}/lessons/{lid} returns 404 when lesson belongs to another course."""
        res_mismatch = self.client.get(f"/api/v1/courses/2/lessons/{self.lesson_1['id']}")
        self.assertEqual(res_mismatch.status_code, 404)
        self.assertIn("Lesson not found in specified course", res_mismatch.json()["detail"])

    # =========================================================================
    # 10. Standalone lesson endpoint is removed
    # =========================================================================

    def test_15_standalone_lesson_endpoint_is_removed(self):
        """Standalone GET /api/v1/lessons/{lesson_id} is removed and returns 404 Not Found."""
        res = self.client.get(f"/api/v1/lessons/{self.lesson_1['id']}")
        self.assertEqual(res.status_code, 404)

    # =========================================================================
    # 11. Response contains only safe verified fields (No invented fields)
    # =========================================================================

    def test_16_response_contains_only_safe_fields(self):
        """Verify that lesson responses do NOT contain invented fields."""
        res = self.client.get(f"/api/v1/courses/1/lessons/{self.lesson_1['id']}")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Verified safe fields
        allowed_fields = {"id", "course_id", "title", "description"}
        self.assertTrue(set(data.keys()).issubset(allowed_fields))

        # Prohibited invented fields
        prohibited_fields = [
            "video_url",
            "content",
            "order",
            "duration",
            "is_completed",
            "progress_percentage",
            "completed_at",
            "password",
            "token",
        ]
        for field in prohibited_fields:
            self.assertNotIn(field, data, f"Prohibited invented field '{field}' was exposed!")

    # =========================================================================
    # 12. No arbitrary user ID controls access
    # =========================================================================

    def test_17_no_arbitrary_user_id_accepted_for_access(self):
        """Arbitrary query parameters attempting to pass user_id are ignored."""
        res = self.client.get(f"/api/v1/courses/1/lessons/{self.lesson_1['id']}?user_id=999")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("user_id", data)

    # =========================================================================
    # 13. No fabricated lesson records
    # =========================================================================

    def test_18_no_fabricated_records_when_empty(self):
        """When course has no lessons, exactly 0 lessons are returned, not fake dummy lessons."""
        res = self.client.get("/api/v1/courses/2/lessons")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["lessons"], [])
        self.assertEqual(data["total"], 0)

    # =========================================================================
    # 14. Live Supabase database boundary test
    # =========================================================================

    def test_19_live_supabase_graceful_boundary(self):
        """
        Verify live Supabase integration:
        When using actual Supabase client against the live project (which lacks a 'lessons' table),
        LessonService handles the missing table gracefully without crashing.
        """
        app.dependency_overrides.clear()
        live_client = TestClient(app)

        # In live Supabase, courses table is currently empty or course 99999 does not exist
        res = live_client.get("/api/v1/courses/99999/lessons")
        self.assertIn(res.status_code, [404, 503])
        if res.status_code == 404:
            self.assertIn("Course not found", res.json()["detail"])

        # Course-scoped lesson query returns 404 (not fabricated)
        res_single = live_client.get("/api/v1/courses/99999/lessons/1")
        self.assertIn(res_single.status_code, [404, 503])
        if res_single.status_code == 404:
            self.assertIn("Course not found", res_single.json()["detail"])


if __name__ == "__main__":
    unittest.main()
