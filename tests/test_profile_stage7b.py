"""
Comprehensive Unit Tests for Phase 4 — Stage 7B: Authenticated User Profile API Routes
Tests:
- GET /api/v1/users/me (auth required, safe fields, 401 unauth, 503 db failure)
- PUT /api/v1/users/me (auth required, name update, strict validation, forbidden extra fields, 422, 401, 503)
- GET /api/v1/users/{user_id} (public, minimal projection, 404 nonexistent, 404 invalid id, 503 db failure)
- IDOR Regression: Proves user A cannot update user B regardless of client inputs.
- 100% isolated using dependency overrides on get_user_service.
"""

import unittest
from typing import Any, Dict, Optional, Union
from starlette.testclient import TestClient

from api.app.main import app
from api.app.auth.security import create_access_token
from api.app.config import settings
from api.app.services.users import get_user_service


class MockUserServiceStage7B:
    """In-memory mock user service implementing Stage 7B database operations."""

    def __init__(self):
        self.users: Dict[int, Dict[str, Any]] = {}
        self.next_id = 1
        self.simulate_db_failure = False

    def add_user(
        self,
        name: str,
        email: str,
        role: Optional[str] = "learner",
        points: int = 0,
        password_hash: Optional[str] = "$2b$12$syntheticPasswordHash12345",
    ) -> Dict[str, Any]:
        uid = self.next_id
        self.next_id += 1
        record = {
            "id": uid,
            "name": name.strip(),
            "email": email.strip().lower(),
            "password": password_hash,
            "role": role,
            "points": points,
            "joined_at": "2026-10-14T00:00:00Z",
        }
        self.users[uid] = record
        return dict(record)

    def get_by_id(self, user_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        uid = int(user_id) if str(user_id).isdigit() else user_id
        user = self.users.get(uid)
        if not user:
            return None
        safe = dict(user)
        safe.pop("password", None)
        return safe

    def update_name(self, user_id: Union[int, str], name: str) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        if not user_id:
            raise ValueError("user_id is required.")

        clean_name = str(name).strip() if name is not None else ""
        if len(clean_name) < 2:
            raise ValueError("Name must be at least 2 characters long.")
        if len(clean_name) > 150:
            raise ValueError("Name must not exceed 150 characters.")

        uid = int(user_id) if str(user_id).isdigit() else user_id
        if uid not in self.users:
            return None

        self.users[uid]["name"] = clean_name
        return self.get_by_id(uid)

    def get_public_profile(self, user_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        uid = int(user_id) if str(user_id).isdigit() else user_id
        user = self.users.get(uid)
        if not user:
            return None
        return {
            "id": user["id"],
            "name": user["name"],
            "role": user.get("role"),
        }


class TestUserProfileRoutesStage7B(unittest.TestCase):
    """Test suite for Stage 7B User Profile routes."""

    def setUp(self):
        self.mock_service = MockUserServiceStage7B()
        app.dependency_overrides[get_user_service] = lambda: self.mock_service
        self.client = TestClient(app)

        # Seed test users
        self.user_a = self.mock_service.add_user(
            name="Alice Learner",
            email="alice@example.com",
            role="learner",
            points=100,
        )
        self.user_b = self.mock_service.add_user(
            name="Bob Creator",
            email="bob@example.com",
            role="creator",
            points=250,
        )

        # Generate tokens
        self.token_a = create_access_token(
            user_id=self.user_a["id"],
            email=self.user_a["email"],
            role=self.user_a["role"],
        )
        self.token_b = create_access_token(
            user_id=self.user_b["id"],
            email=self.user_b["email"],
            role=self.user_b["role"],
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    # =========================================================================
    # 1. GET /api/v1/users/me
    # =========================================================================

    def test_01_get_me_authenticated_returns_200(self):
        """Authenticated user receives 200 OK on GET /users/me."""
        res = self.client.get(
            "/api/v1/users/me",
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 200)

    def test_02_get_me_contains_authoritative_safe_fields(self):
        """GET /users/me response contains id, name, email, role, points, joined_at."""
        res = self.client.get(
            "/api/v1/users/me",
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], self.user_a["id"])
        self.assertEqual(data["name"], "Alice Learner")
        self.assertEqual(data["email"], "alice@example.com")
        self.assertEqual(data["role"], "learner")
        self.assertEqual(data["points"], 100)
        self.assertEqual(data["joined_at"], "2026-10-14T00:00:00Z")

    def test_03_get_me_never_exposes_password(self):
        """GET /users/me never exposes password or password hashes."""
        res = self.client.get(
            "/api/v1/users/me",
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("password", data)
        self.assertNotIn("password_hash", data)
        self.assertNotIn("hash", str(data))

    def test_04_get_me_unauthenticated_returns_401(self):
        """Unauthenticated GET /users/me returns 401 Unauthorized."""
        res = self.client.get("/api/v1/users/me")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json()["detail"])

    def test_05_get_me_database_failure_returns_503(self):
        """Database outage during GET /users/me returns safe 503."""
        self.mock_service.simulate_db_failure = True
        res = self.client.get(
            "/api/v1/users/me",
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    # =========================================================================
    # 2. PUT /api/v1/users/me
    # =========================================================================

    def test_06_put_me_authenticated_user_can_update_name(self):
        """Authenticated user successfully updates their name via PUT /users/me."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "Alice Wonderland"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["name"], "Alice Wonderland")
        self.assertEqual(data["id"], self.user_a["id"])

        # Verify DB was updated
        db_record = self.mock_service.get_by_id(self.user_a["id"])
        self.assertEqual(db_record["name"], "Alice Wonderland")

    def test_07_put_me_current_user_id_comes_from_auth_dependency(self):
        """Target user ID is exclusively derived from authenticated session."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "Bob The Builder"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_b},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["id"], self.user_b["id"])
        self.assertEqual(self.mock_service.get_by_id(self.user_b["id"])["name"], "Bob The Builder")
        # Ensure user A was not touched
        self.assertEqual(self.mock_service.get_by_id(self.user_a["id"])["name"], "Alice Learner")

    def test_08_put_me_client_cannot_choose_target_user(self):
        """Attempting to target user B while authenticated as user A updates user A only."""
        res = self.client.put(
            "/api/v1/users/me?user_id=2",
            json={"name": "Alice Modified"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["id"], self.user_a["id"])
        self.assertEqual(self.mock_service.get_by_id(self.user_a["id"])["name"], "Alice Modified")
        self.assertEqual(self.mock_service.get_by_id(self.user_b["id"])["name"], "Bob Creator")

    def test_09_put_me_extra_user_id_field_rejected(self):
        """Payload attempting to inject extra user_id field is rejected with 422."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "New Name", "user_id": 99},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 422)

    def test_10_put_me_extra_role_field_rejected(self):
        """Payload attempting to inject extra role field is rejected with 422."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "New Name", "role": "admin"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 422)

    def test_11_put_me_extra_points_field_rejected(self):
        """Payload attempting to inject extra points field is rejected with 422."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "New Name", "points": 99999},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 422)

    def test_12_put_me_extra_email_field_rejected(self):
        """Payload attempting to inject extra email field is rejected with 422."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "New Name", "email": "attacker@example.com"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 422)

    def test_13_put_me_extra_password_field_rejected(self):
        """Payload attempting to inject extra password field is rejected with 422."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "New Name", "password": "new-secret-password"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 422)

    def test_14_put_me_whitespace_name_rejected(self):
        """Whitespace-only name is rejected with 422."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "     "},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 422)

    def test_15_put_me_too_short_name_rejected(self):
        """Name under 2 characters is rejected with 422."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "X"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 422)

    def test_16_put_me_too_long_name_rejected(self):
        """Name over 150 characters is rejected with 422."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "A" * 151},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 422)

    def test_17_put_me_successful_response_contains_only_safe_fields(self):
        """Successful PUT /users/me response contains only safe authenticated fields."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "Alice Super Learner"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertIn("email", data)
        self.assertIn("role", data)
        self.assertIn("points", data)
        self.assertIn("joined_at", data)
        self.assertNotIn("password", data)
        self.assertNotIn("password_hash", data)

    def test_18_put_me_unauthenticated_returns_401(self):
        """Unauthenticated PUT /users/me returns 401 Unauthorized."""
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "New Name"},
        )
        self.assertEqual(res.status_code, 401)

    def test_19_put_me_service_failure_returns_503(self):
        """Database outage during PUT /users/me returns safe 503."""
        self.mock_service.simulate_db_failure = True
        res = self.client.put(
            "/api/v1/users/me",
            json={"name": "Valid Name"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    # =========================================================================
    # 3. GET /api/v1/users/{user_id}
    # =========================================================================

    def test_20_get_public_profile_valid_id_returns_200(self):
        """Unauthenticated GET /users/{id} returns 200 OK for existing user."""
        res = self.client.get(f"/api/v1/users/{self.user_b['id']}")
        self.assertEqual(res.status_code, 200)

    def test_21_get_public_profile_contains_only_minimal_fields(self):
        """Public profile contains only id, name, and role."""
        res = self.client.get(f"/api/v1/users/{self.user_b['id']}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], self.user_b["id"])
        self.assertEqual(data["name"], "Bob Creator")
        self.assertEqual(data["role"], "creator")

    def test_22_get_public_profile_does_not_contain_email(self):
        """Public profile strictly omits email address."""
        res = self.client.get(f"/api/v1/users/{self.user_b['id']}")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("email", res.json())

    def test_23_get_public_profile_does_not_contain_password(self):
        """Public profile strictly omits password."""
        res = self.client.get(f"/api/v1/users/{self.user_b['id']}")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("password", res.json())
        self.assertNotIn("password_hash", res.json())

    def test_24_get_public_profile_does_not_contain_points(self):
        """Public profile strictly omits points."""
        res = self.client.get(f"/api/v1/users/{self.user_b['id']}")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("points", res.json())

    def test_25_get_public_profile_does_not_contain_joined_at(self):
        """Public profile strictly omits joined_at."""
        res = self.client.get(f"/api/v1/users/{self.user_b['id']}")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("joined_at", res.json())

    def test_26_get_public_profile_nonexistent_user_returns_404(self):
        """Nonexistent user ID returns safe 404 Not Found."""
        res = self.client.get("/api/v1/users/9999")
        self.assertEqual(res.status_code, 404)
        self.assertIn("User not found", res.json()["detail"])

    def test_27_get_public_profile_invalid_user_id_returns_404(self):
        """Malformed or negative user IDs return safe 404 Not Found."""
        # Non-numeric string
        res_str = self.client.get("/api/v1/users/not-a-number")
        self.assertEqual(res_str.status_code, 404)
        self.assertIn("User not found", res_str.json()["detail"])

        # Zero
        res_zero = self.client.get("/api/v1/users/0")
        self.assertEqual(res_zero.status_code, 404)

        # Negative
        res_neg = self.client.get("/api/v1/users/-10")
        self.assertEqual(res_neg.status_code, 404)

    def test_28_get_public_profile_service_failure_returns_503(self):
        """Database outage during public profile query returns safe 503."""
        self.mock_service.simulate_db_failure = True
        res = self.client.get(f"/api/v1/users/{self.user_b['id']}")
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    # =========================================================================
    # 4. IDOR REGRESSION
    # =========================================================================

    def test_29_idor_regression_user_a_cannot_update_user_b(self):
        """
        Explicit IDOR test:
        Authenticated user A attempts to update user B by injecting user_id in various ways.
        User B's name must remain unmodified.
        """
        original_b_name = self.user_b["name"]
        self.assertEqual(original_b_name, "Bob Creator")

        # 1. Attempt body injection (rejected by schema 422)
        res_body = self.client.put(
            "/api/v1/users/me",
            json={"name": "Hacked B Name", "user_id": self.user_b["id"]},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res_body.status_code, 422)
        self.assertEqual(self.mock_service.get_by_id(self.user_b["id"])["name"], original_b_name)

        # 2. Attempt query parameter injection
        res_query = self.client.put(
            f"/api/v1/users/me?user_id={self.user_b['id']}",
            json={"name": "Alice Innocent Name"},
            cookies={settings.AUTH_COOKIE_NAME: self.token_a},
        )
        self.assertEqual(res_query.status_code, 200)

        # Verify User B was NOT modified
        user_b_current = self.mock_service.get_by_id(self.user_b["id"])
        self.assertEqual(user_b_current["name"], original_b_name)

        # Verify only User A was modified
        user_a_current = self.mock_service.get_by_id(self.user_a["id"])
        self.assertEqual(user_a_current["name"], "Alice Innocent Name")


if __name__ == "__main__":
    unittest.main()
