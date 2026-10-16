"""
Comprehensive Unit & Integration Tests for Phase 5 — Stage 9: Course Enrollment Foundation
Minimum Test Requirements:
1. authenticated learner can enroll (201 Created)
2. unauthenticated enrollment is rejected (401 Unauthorized)
3. creator/admin cannot use learner enrollment endpoint (403 Forbidden)
4. invalid course ID rejected (404 Not Found)
5. nonexistent course rejected (404 Not Found)
6. duplicate enrollment handled safely (409 Conflict)
7. enrollment status for enrolled learner (is_enrolled: True)
8. enrollment status for non-enrolled learner (is_enrolled: False)
9. user isolation / IDOR protection (user A cannot enroll or view for user B)
10. Supabase/database failure returns controlled 503
11. response does not expose unnecessary private user fields (no passwords, tokens, hashes)
12. verified live schema is used correctly (id, user_id, course_id, progress, completed_lessons, enrolled_at)
13. body-based enrollment endpoint (/api/v1/enrollments)
14. EnrollmentService unit logic & constraint handling
"""

import unittest
from typing import Any, Dict, Optional, Union
from starlette.testclient import TestClient

from api.app.main import app
from api.app.auth.security import create_access_token
from api.app.config import settings
from api.app.services.users import get_user_service
from api.app.services.enrollments import (
    get_enrollment_service,
    EnrollmentService,
    CourseNotFoundError,
    DuplicateEnrollmentError,
)
from api.app.services.courses import get_course_service


class MockUserServiceStage9:
    """Mock user service providing authoritative users for auth dependency."""

    def __init__(self):
        self.users: Dict[int, Dict[str, Any]] = {}
        self.simulate_db_failure = False

    def add_user(
        self,
        user_id: int,
        name: str,
        email: str,
        role: str = "learner",
    ) -> Dict[str, Any]:
        record = {
            "id": user_id,
            "name": name,
            "email": email,
            "role": role,
            "points": 100,
            "joined_at": "2026-10-14T00:00:00Z",
        }
        self.users[user_id] = record
        return record

    def get_by_id(self, user_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("Database connection failure")
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            return None
        return dict(self.users[uid]) if uid in self.users else None


class MockEnrollmentServiceStage9:
    """Mock enrollment service for Stage 9 integration tests."""

    def __init__(self, existing_courses: Optional[Dict[int, Dict[str, Any]]] = None):
        self.enrollments: Dict[int, Dict[str, Any]] = {}
        self.courses = existing_courses or {}
        self.next_id = 1
        self.simulate_db_failure = False

    def get_enrollment(self, user_id: int, course_id: int) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        for rec in self.enrollments.values():
            if rec["user_id"] == user_id and rec["course_id"] == course_id:
                return dict(rec)
        return None

    def create_enrollment(self, user_id: int, course_id: int) -> Dict[str, Any]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        if course_id not in self.courses:
            raise CourseNotFoundError("Course not found.")

        if self.get_enrollment(user_id, course_id):
            raise DuplicateEnrollmentError("Already enrolled in this course.")

        eid = self.next_id
        self.next_id += 1
        record = {
            "id": eid,
            "user_id": user_id,
            "course_id": course_id,
            "progress": 0,
            "completed_lessons": 0,
            "enrolled_at": "2026-10-17T00:00:00Z",
        }
        self.enrollments[eid] = record
        return dict(record)

    def get_enrollment_status(self, user_id: int, course_id: int) -> Dict[str, Any]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        if course_id not in self.courses:
            raise CourseNotFoundError("Course not found.")

        enrollment = self.get_enrollment(user_id, course_id)
        return {
            "is_enrolled": enrollment is not None,
            "course_id": course_id,
            "enrollment": enrollment,
        }


class TestCourseEnrollmentStage9(unittest.TestCase):
    """Integration test suite for course enrollment endpoints."""

    def setUp(self):
        self.mock_user_service = MockUserServiceStage9()
        self.courses = {
            1: {"id": 1, "title": "Web Development", "price": 0},
            2: {"id": 2, "title": "Python Bootcamp", "price": 49},
        }
        self.mock_enrollment_service = MockEnrollmentServiceStage9(self.courses)

        app.dependency_overrides[get_user_service] = lambda: self.mock_user_service
        app.dependency_overrides[get_enrollment_service] = lambda: self.mock_enrollment_service

        self.client = TestClient(app)

        # Create test users
        self.learner_user = self.mock_user_service.add_user(
            user_id=10,
            name="Alice Learner",
            email="alice@example.com",
            role="learner",
        )
        self.other_learner = self.mock_user_service.add_user(
            user_id=20,
            name="Bob Learner",
            email="bob@example.com",
            role="learner",
        )
        self.creator_user = self.mock_user_service.add_user(
            user_id=30,
            name="Carol Creator",
            email="carol@example.com",
            role="creator",
        )
        self.admin_user = self.mock_user_service.add_user(
            user_id=40,
            name="Dan Admin",
            email="dan@example.com",
            role="admin",
        )

        # Tokens
        self.learner_token = create_access_token(
            user_id=self.learner_user["id"],
            email=self.learner_user["email"],
            role=self.learner_user["role"],
        )
        self.other_learner_token = create_access_token(
            user_id=self.other_learner["id"],
            email=self.other_learner["email"],
            role=self.other_learner["role"],
        )
        self.creator_token = create_access_token(
            user_id=self.creator_user["id"],
            email=self.creator_user["email"],
            role=self.creator_user["role"],
        )
        self.admin_token = create_access_token(
            user_id=self.admin_user["id"],
            email=self.admin_user["email"],
            role=self.admin_user["role"],
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    # =========================================================================
    # 1. Authenticated Learner Can Enroll
    # =========================================================================

    def test_01_authenticated_learner_can_enroll_success(self):
        """Authenticated learner receives 201 Created upon enrolling."""
        res = self.client.post(
            "/api/v1/courses/1/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["course_id"], 1)
        self.assertEqual(data["user_id"], self.learner_user["id"])
        self.assertEqual(data["progress"], 0)
        self.assertEqual(data["completed_lessons"], 0)
        self.assertIn("enrolled_at", data)

    # =========================================================================
    # 2. Unauthenticated Enrollment Is Rejected
    # =========================================================================

    def test_02_unauthenticated_enrollment_rejected(self):
        """Unauthenticated request to enroll returns 401 Unauthorized."""
        res = self.client.post("/api/v1/courses/1/enroll")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json()["detail"])

    # =========================================================================
    # 3. Creator/Admin Role Authorization
    # =========================================================================

    def test_03_creator_cannot_enroll_as_learner(self):
        """User with 'creator' role is forbidden from using learner enrollment."""
        res = self.client.post(
            "/api/v1/courses/1/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.creator_token},
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Learner privileges required", res.json()["detail"])

    def test_04_admin_cannot_enroll_as_learner(self):
        """User with 'admin' role is forbidden from using learner enrollment."""
        res = self.client.post(
            "/api/v1/courses/1/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.admin_token},
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Learner privileges required", res.json()["detail"])

    # =========================================================================
    # 4. Invalid Course ID Rejected
    # =========================================================================

    def test_05_invalid_course_id_non_numeric(self):
        """Non-numeric course ID returns 404 Course not found."""
        res = self.client.post(
            "/api/v1/courses/not-a-number/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    def test_06_invalid_course_id_zero_or_negative(self):
        """Zero or negative course ID returns 404 Course not found."""
        res_zero = self.client.post(
            "/api/v1/courses/0/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res_zero.status_code, 404)

        res_neg = self.client.post(
            "/api/v1/courses/-5/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res_neg.status_code, 404)

    # =========================================================================
    # 5. Nonexistent Course Rejected
    # =========================================================================

    def test_07_nonexistent_course_rejected(self):
        """Attempting to enroll in a non-existent course returns 404."""
        res = self.client.post(
            "/api/v1/courses/99999/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Course not found", res.json()["detail"])

    # =========================================================================
    # 6. Duplicate Enrollment Handled Safely
    # =========================================================================

    def test_08_duplicate_enrollment_rejected_with_409(self):
        """Enrolling twice in the same course returns 409 Conflict without unhandled error."""
        # First enrollment
        res1 = self.client.post(
            "/api/v1/courses/1/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res1.status_code, 201)

        # Duplicate enrollment
        res2 = self.client.post(
            "/api/v1/courses/1/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res2.status_code, 409)
        self.assertIn("Already enrolled in this course", res2.json()["detail"])

    # =========================================================================
    # 7. Enrollment Status for Enrolled Learner
    # =========================================================================

    def test_09_enrollment_status_for_enrolled_learner(self):
        """Enrolled learner checks status and receives is_enrolled: True."""
        # Enroll first
        self.client.post(
            "/api/v1/courses/1/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )

        res = self.client.get(
            "/api/v1/courses/1/enrollment-status",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_enrolled"])
        self.assertEqual(data["course_id"], 1)
        self.assertIsNotNone(data["enrollment"])
        self.assertEqual(data["enrollment"]["user_id"], self.learner_user["id"])

    # =========================================================================
    # 8. Enrollment Status for Non-Enrolled Learner
    # =========================================================================

    def test_10_enrollment_status_for_non_enrolled_learner(self):
        """Non-enrolled user receives is_enrolled: False and enrollment: null."""
        res = self.client.get(
            "/api/v1/courses/1/enrollment-status",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["is_enrolled"])
        self.assertEqual(data["course_id"], 1)
        self.assertIsNone(data["enrollment"])

    # =========================================================================
    # 9. User Isolation / Anti-IDOR Protection
    # =========================================================================

    def test_11_user_isolation_cannot_enroll_or_view_for_other_user(self):
        """User A enrolling does NOT enroll User B, and User B sees is_enrolled: False."""
        # Alice enrolls in course 1
        res_a = self.client.post(
            "/api/v1/courses/1/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res_a.status_code, 201)

        # Bob checks status for course 1 -> must be False
        res_b = self.client.get(
            "/api/v1/courses/1/enrollment-status",
            cookies={settings.AUTH_COOKIE_NAME: self.other_learner_token},
        )
        self.assertEqual(res_b.status_code, 200)
        self.assertFalse(res_b.json()["is_enrolled"])

    # =========================================================================
    # 10. Database Failure Handling (503 Service Unavailable)
    # =========================================================================

    def test_12_enrollment_db_failure_returns_503(self):
        """Database failure during enrollment returns safe 503."""
        self.mock_enrollment_service.simulate_db_failure = True
        res = self.client.post(
            "/api/v1/courses/1/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    def test_13_status_check_db_failure_returns_503(self):
        """Database failure during enrollment status check returns safe 503."""
        self.mock_enrollment_service.simulate_db_failure = True
        res = self.client.get(
            "/api/v1/courses/1/enrollment-status",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    # =========================================================================
    # 11. Response Does Not Expose Private Fields
    # =========================================================================

    def test_14_enrollment_response_strictly_safe_fields_only(self):
        """Enrollment output strictly contains verified live columns without user credentials."""
        res = self.client.post(
            "/api/v1/courses/1/enroll",
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()

        # Authoritative verified columns only
        expected_keys = {"id", "user_id", "course_id", "progress", "completed_lessons", "enrolled_at"}
        self.assertTrue(set(data.keys()).issubset(expected_keys))

        sensitive_fields = ["password", "password_hash", "token", "secret", "email", "reset_token"]
        for field in sensitive_fields:
            self.assertNotIn(field, data)

    # =========================================================================
    # 12. Body-Based Enrollment Endpoint (/api/v1/enrollments)
    # =========================================================================

    def test_15_body_based_enrollment_endpoint_success(self):
        """POST /api/v1/enrollments with JSON payload operates accurately."""
        res = self.client.post(
            "/api/v1/enrollments",
            json={"course_id": 2},
            cookies={settings.AUTH_COOKIE_NAME: self.learner_token},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["course_id"], 2)
        self.assertEqual(data["user_id"], self.learner_user["id"])


class TestEnrollmentServiceLogic(unittest.TestCase):
    """Unit tests for EnrollmentService internal database operations and error branches."""

    def test_enrollment_service_uniqueness_exception_handling(self):
        """EnrollmentService converts PostgREST unique violation into DuplicateEnrollmentError."""
        class MockTable:
            def select(self, cols):
                return self
            def eq(self, col, val):
                return self
            def limit(self, val):
                return self
            def execute(self):
                class Res:
                    data = []
                return Res()
            def insert(self, payload):
                raise Exception("duplicate key value violates unique constraint 'enrollments_user_id_course_id_key' 23505")

        class MockClient:
            def table(self, name):
                return MockTable()

        class MockSupabase:
            client = MockClient()

        class MockCourseService:
            def get_by_id(self, cid):
                return {"id": cid, "title": "Test"}

        service = EnrollmentService(
            supabase_service=MockSupabase(),
            course_service=MockCourseService(),
        )

        with self.assertRaises(DuplicateEnrollmentError):
            service.create_enrollment(user_id=1, course_id=1)

    def test_enrollment_service_course_not_found(self):
        """EnrollmentService raises CourseNotFoundError when course does not exist."""
        class MockCourseService:
            def get_by_id(self, cid):
                return None

        service = EnrollmentService(
            supabase_service=None,
            course_service=MockCourseService(),
        )

        with self.assertRaises(CourseNotFoundError):
            service.create_enrollment(user_id=1, course_id=999)


if __name__ == "__main__":
    unittest.main()
