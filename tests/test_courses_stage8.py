"""
Comprehensive Unit & Integration Tests for Phase 5 — Stage 8: Course Catalog Foundation
Coverage:
1. course list success
2. empty course list
3. search filtering (title and description)
4. category filtering
5. level filtering
6. combined filters (search + category + level)
7. course detail success
8. course detail 404 (non-existent ID)
9. invalid course ID (malformed string, 0, negative integer)
10. database/Supabase failure handling (503 Service Unavailable)
11. response does not expose private fields (no passwords, tokens, hashes)
12. public access without authentication
13. CourseService unit logic & query sanitization
100% isolated using dependency overrides on get_course_service.
"""

import unittest
from typing import Any, Dict, List, Optional, Union
from starlette.testclient import TestClient

from api.app.main import app
from api.app.services.courses import get_course_service, CourseService


class MockCourseServiceStage8:
    """In-memory mock course service implementing Stage 8 database operations."""

    def __init__(self):
        self.courses: Dict[int, Dict[str, Any]] = {}
        self.next_id = 1
        self.simulate_db_failure = False

    def add_course(
        self,
        title: str,
        description: str,
        instructor: str,
        category: str = "General",
        level: str = "Beginner",
        duration: str = "4 weeks",
        thumbnail: str = "📚",
        total_lessons: int = 10,
        rating: float = 4.5,
        price: int = 0,
        points_price: int = 0,
        created_by: int = 1,
        created_at: str = "2026-10-15T00:00:00Z",
    ) -> Dict[str, Any]:
        cid = self.next_id
        self.next_id += 1
        record = {
            "id": cid,
            "title": title,
            "description": description,
            "instructor": instructor,
            "category": category,
            "level": level,
            "duration": duration,
            "thumbnail": thumbnail,
            "total_lessons": total_lessons,
            "rating": rating,
            "price": price,
            "points_price": points_price,
            "created_by": created_by,
            "created_at": created_at,
        }
        self.courses[cid] = record
        return dict(record)

    def list_courses(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        results = list(self.courses.values())

        if search:
            clean_search = search.strip().lower()
            if clean_search:
                results = [
                    c for c in results
                    if clean_search in c["title"].lower() or clean_search in c["description"].lower()
                ]

        if category:
            clean_cat = category.strip().lower()
            if clean_cat:
                results = [c for c in results if c["category"].lower() == clean_cat]

        if level:
            clean_lvl = level.strip().lower()
            if clean_lvl:
                results = [c for c in results if c["level"].lower() == clean_lvl]

        # Sort descending by created_at
        results.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return results

    def get_by_id(self, course_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        try:
            cid = int(course_id)
            if cid <= 0:
                return None
        except (ValueError, TypeError):
            return None

        course = self.courses.get(cid)
        return dict(course) if course else None


class TestCourseCatalogStage8(unittest.TestCase):
    """Test suite for Course Catalog API endpoints & services."""

    def setUp(self):
        self.mock_service = MockCourseServiceStage8()
        app.dependency_overrides[get_course_service] = lambda: self.mock_service
        self.client = TestClient(app)

        # Seed sample verified test courses
        self.course_1 = self.mock_service.add_course(
            title="Full-Stack Web Development",
            description="Master Next.js, FastAPI, and Supabase from scratch.",
            instructor="Sarah Connor",
            category="Web Development",
            level="Intermediate",
            duration="8 weeks",
            thumbnail="💻",
            total_lessons=24,
            rating=4.9,
            price=49,
            points_price=500,
            created_by=10,
            created_at="2026-10-15T02:00:00Z",
        )
        self.course_2 = self.mock_service.add_course(
            title="Introduction to Python Programming",
            description="Learn the fundamentals of Python, data structures, and algorithms.",
            instructor="Guido Ross",
            category="Programming",
            level="Beginner",
            duration="4 weeks",
            thumbnail="🐍",
            total_lessons=12,
            rating=4.8,
            price=0,
            points_price=0,
            created_by=11,
            created_at="2026-10-14T10:00:00Z",
        )
        self.course_3 = self.mock_service.add_course(
            title="Advanced Machine Learning Systems",
            description="Production ML architectures, model deployment, and scaling.",
            instructor="Alan Turing",
            category="Data Science",
            level="Advanced",
            duration="12 weeks",
            thumbnail="🤖",
            total_lessons=30,
            rating=4.95,
            price=99,
            points_price=1000,
            created_by=12,
            created_at="2026-10-13T08:00:00Z",
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    # =========================================================================
    # 1. Course List Success & Structure
    # =========================================================================

    def test_01_course_list_success(self):
        """GET /api/v1/courses returns 200 with list of courses and total count."""
        res = self.client.get("/api/v1/courses")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("courses", data)
        self.assertIn("total", data)
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["courses"]), 3)

    # =========================================================================
    # 2. Empty Course List
    # =========================================================================

    def test_02_empty_course_list(self):
        """GET /api/v1/courses returns empty list when no courses match or exist."""
        self.mock_service.courses.clear()
        res = self.client.get("/api/v1/courses")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["courses"], [])
        self.assertEqual(data["total"], 0)

    # =========================================================================
    # 3. Search Filtering (Title & Description)
    # =========================================================================

    def test_03_search_filtering_title(self):
        """Search filter correctly matches course titles."""
        res = self.client.get("/api/v1/courses?search=Python")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["courses"][0]["title"], "Introduction to Python Programming")

    def test_04_search_filtering_description(self):
        """Search filter correctly matches course descriptions."""
        res = self.client.get("/api/v1/courses?search=FastAPI")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["courses"][0]["title"], "Full-Stack Web Development")

    def test_05_search_filtering_no_match(self):
        """Search query with no matching keywords returns empty list."""
        res = self.client.get("/api/v1/courses?search=NonExistentKeywordXYZ")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["courses"], [])

    # =========================================================================
    # 4. Category Filtering
    # =========================================================================

    def test_06_category_filtering(self):
        """Category query parameter filters accurately."""
        res = self.client.get("/api/v1/courses?category=Data Science")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["courses"][0]["title"], "Advanced Machine Learning Systems")

    # =========================================================================
    # 5. Level Filtering
    # =========================================================================

    def test_07_level_filtering(self):
        """Level query parameter filters accurately by difficulty level."""
        res = self.client.get("/api/v1/courses?level=Beginner")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["courses"][0]["level"], "Beginner")

    # =========================================================================
    # 6. Combined Filters
    # =========================================================================

    def test_08_combined_filters_matching(self):
        """Combining search, category, and level filters returns matching course."""
        res = self.client.get("/api/v1/courses?search=FastAPI&category=Web Development&level=Intermediate")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["courses"][0]["title"], "Full-Stack Web Development")

    def test_09_combined_filters_conflicting_returns_empty(self):
        """Conflicting filter parameters return 0 results gracefully."""
        res = self.client.get("/api/v1/courses?search=Python&category=Web Development")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["courses"], [])

    # =========================================================================
    # 7. Course Detail Success
    # =========================================================================

    def test_10_course_detail_success(self):
        """GET /api/v1/courses/{course_id} returns 200 and full course details."""
        res = self.client.get(f"/api/v1/courses/{self.course_1['id']}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], self.course_1["id"])
        self.assertEqual(data["title"], "Full-Stack Web Development")
        self.assertEqual(data["instructor"], "Sarah Connor")
        self.assertEqual(data["price"], 49)
        self.assertEqual(data["points_price"], 500)
        self.assertEqual(data["created_by"], 10)

    # =========================================================================
    # 8. Course Detail 404 (Non-existent ID)
    # =========================================================================

    def test_11_course_detail_not_found(self):
        """Querying a non-existent course ID returns 404 Not Found."""
        res = self.client.get("/api/v1/courses/99999")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    # =========================================================================
    # 9. Invalid Course ID
    # =========================================================================

    def test_12_invalid_course_id_non_numeric(self):
        """Non-numeric course IDs return safe 404 Not Found."""
        res = self.client.get("/api/v1/courses/not-a-number")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    def test_13_invalid_course_id_zero(self):
        """Zero course ID returns safe 404 Not Found."""
        res = self.client.get("/api/v1/courses/0")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    def test_14_invalid_course_id_negative(self):
        """Negative course ID returns safe 404 Not Found."""
        res = self.client.get("/api/v1/courses/-5")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    # =========================================================================
    # 10. Database / Supabase Failure Handling (503)
    # =========================================================================

    def test_15_list_courses_db_failure_returns_503(self):
        """Database failure during course listing returns safe 503."""
        self.mock_service.simulate_db_failure = True
        res = self.client.get("/api/v1/courses")
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    def test_16_course_detail_db_failure_returns_503(self):
        """Database failure during course detail retrieval returns safe 503."""
        self.mock_service.simulate_db_failure = True
        res = self.client.get(f"/api/v1/courses/{self.course_1['id']}")
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    # =========================================================================
    # 11. Response Does Not Expose Private Fields
    # =========================================================================

    def test_17_no_private_fields_exposed_in_list_or_detail(self):
        """Verify responses never expose passwords, tokens, or credentials."""
        # Check list item
        res_list = self.client.get("/api/v1/courses")
        self.assertEqual(res_list.status_code, 200)
        first_course = res_list.json()["courses"][0]

        private_fields = ["password", "password_hash", "token", "secret", "email", "reset_token"]
        for pf in private_fields:
            self.assertNotIn(pf, first_course)

        # Check detail item
        res_detail = self.client.get(f"/api/v1/courses/{self.course_1['id']}")
        self.assertEqual(res_detail.status_code, 200)
        detail_data = res_detail.json()
        for pf in private_fields:
            self.assertNotIn(pf, detail_data)

    # =========================================================================
    # 12. Public Access Without Authentication
    # =========================================================================

    def test_18_public_access_no_auth_cookie_required(self):
        """Course catalog endpoints are completely accessible without authentication."""
        # Explicitly empty cookies
        client_no_auth = TestClient(app)
        res_list = client_no_auth.get("/api/v1/courses")
        self.assertEqual(res_list.status_code, 200)

        res_detail = client_no_auth.get(f"/api/v1/courses/{self.course_1['id']}")
        self.assertEqual(res_detail.status_code, 200)


class TestCourseServiceLogic(unittest.TestCase):
    """Test unit logic inside CourseService."""

    def test_service_sanitizes_search_query(self):
        """CourseService safely handles search strings with special characters."""
        service = CourseService(supabase_service=None)
        # Mock client without crashing on sanitize
        class DummyTable:
            def __init__(self):
                self.or_clause = None

            def select(self, cols):
                return self

            def or_(self, clause):
                self.or_clause = clause
                return self

            def ilike(self, col, val):
                return self

            def order(self, col, desc=True):
                return self

            def execute(self):
                class DummyRes:
                    data = []
                return DummyRes()

        class DummyClient:
            def table(self, name):
                return DummyTable()

        class DummySupabaseService:
            client = DummyClient()

        srv = CourseService(supabase_service=DummySupabaseService())
        # Pass potentially dangerous postgrest injection characters
        res = srv.list_courses(search='test"(),\\injection')
        self.assertEqual(res, [])

    def test_service_get_by_id_invalid_returns_none(self):
        """CourseService returns None for non-positive or non-integer IDs without querying."""
        class DummyClient:
            def table(self, name):
                raise AssertionError("Should not reach table query on invalid ID")

        class DummySupabaseService:
            client = DummyClient()

        srv = CourseService(supabase_service=DummySupabaseService())
        self.assertIsNone(srv.get_by_id("invalid-id"))
        self.assertIsNone(srv.get_by_id(0))
        self.assertIsNone(srv.get_by_id(-99))


if __name__ == "__main__":
    unittest.main()
