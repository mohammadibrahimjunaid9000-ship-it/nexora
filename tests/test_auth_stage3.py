"""
Comprehensive Unit Tests for Phase 4 — Stage 3: Authentication & Role Authorization Dependencies
Tests canonical get_current_user, role authorization (learner/creator/admin),
JWT type enforcement, database authority, 401 vs 403 vs 503 semantics, and refactored /me endpoint.
Uses dependency injection overrides to completely isolate from production Supabase database.
"""

import unittest
from datetime import timedelta, datetime, timezone
import jwt
from starlette.testclient import TestClient
from fastapi import APIRouter, Depends

from api.app.main import app
from api.app.services.users import get_user_service
from api.app.auth.security import create_access_token
from api.app.auth.schemas import UserResponse, UserRole
from api.app.auth.dependencies import (
    get_current_user,
    require_learner,
    require_creator,
    require_admin,
)
from api.app.config import settings

# Test router to verify role authorization dependencies on endpoints
test_router = APIRouter(prefix="/api/v1/test", tags=["Stage3Tests"])


@test_router.get("/auth-only")
def auth_only_endpoint(current_user: UserResponse = Depends(get_current_user)):
    return {"message": "authenticated", "user_id": current_user.id, "role": current_user.role}


@test_router.get("/learner-only")
def learner_endpoint(learner: UserResponse = Depends(require_learner)):
    return {"message": "learner allowed", "user_id": learner.id, "role": learner.role}


@test_router.get("/creator-only")
def creator_endpoint(creator: UserResponse = Depends(require_creator)):
    return {"message": "creator allowed", "user_id": creator.id, "role": creator.role}


@test_router.get("/admin-only")
def admin_endpoint(admin: UserResponse = Depends(require_admin)):
    return {"message": "admin allowed", "user_id": admin.id, "role": admin.role}


# Mount the test router to app for testing
app.include_router(test_router)


class MockUserService:
    """In-memory mock user service implementing database behavior for Stage 3."""

    def __init__(self):
        self.users = {}
        self.next_id = 1
        self.simulate_db_failure = False

    def add_user(self, name: str, email: str, role: str, points: int = 0) -> dict:
        uid = self.next_id
        self.next_id += 1
        record = {
            "id": uid,
            "name": name.strip(),
            "email": email.strip().lower(),
            "role": role,
            "points": points,
            "joined_at": "2026-10-11T00:00:00Z"
        }
        self.users[uid] = record
        return dict(record)

    def get_by_id(self, user_id):
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        uid = int(user_id) if str(user_id).isdigit() else user_id
        user = self.users.get(uid)
        if not user:
            return None
        safe = dict(user)
        safe.pop("password", None)
        return safe


class TestAuthStage3Dependencies(unittest.TestCase):
    """Test suite for Phase 4 Stage 3 authentication and role authorization dependencies."""

    def setUp(self):
        self.mock_service = MockUserService()
        app.dependency_overrides[get_user_service] = lambda: self.mock_service
        self.client = TestClient(app)

        # Seed test users
        self.learner_user = self.mock_service.add_user(
            name="Alice Learner",
            email="alice@example.com",
            role=UserRole.LEARNER.value
        )
        self.creator_user = self.mock_service.add_user(
            name="Bob Creator",
            email="bob@example.com",
            role=UserRole.CREATOR.value
        )
        self.admin_user = self.mock_service.add_user(
            name="Carol Admin",
            email="carol@example.com",
            role=UserRole.ADMIN.value
        )

        # Generate tokens
        self.learner_token = create_access_token(
            user_id=self.learner_user["id"],
            email=self.learner_user["email"],
            role=self.learner_user["role"]
        )
        self.creator_token = create_access_token(
            user_id=self.creator_user["id"],
            email=self.creator_user["email"],
            role=self.creator_user["role"]
        )
        self.admin_token = create_access_token(
            user_id=self.admin_user["id"],
            email=self.admin_user["email"],
            role=self.admin_user["role"]
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    # ─── 1. Authentication Dependency (get_current_user) ──────────────────────────

    def test_01_valid_cookie_resolves_current_user(self):
        """Valid token in HttpOnly cookie resolves user and DB data successfully."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.learner_token)
        res = self.client.get("/api/v1/test/auth-only")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["user_id"], self.learner_user["id"])
        self.assertEqual(data["role"], "learner")

    def test_02_missing_cookie_returns_401(self):
        """Request without authentication cookie returns 401 Unauthorized."""
        res = self.client.get("/api/v1/test/auth-only")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Authentication required.")

    def test_03_malformed_token_returns_401(self):
        """Malformed JWT string in cookie returns 401 Unauthorized."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, "this.is.not.a.valid.jwt")
        res = self.client.get("/api/v1/test/auth-only")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid authentication token.")

    def test_04_expired_token_returns_401(self):
        """Expired JWT token returns 401 Unauthorized."""
        expired_token = create_access_token(
            user_id=self.learner_user["id"],
            email=self.learner_user["email"],
            role=self.learner_user["role"],
            expires_delta=timedelta(seconds=-10)
        )
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, expired_token)
        res = self.client.get("/api/v1/test/auth-only")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Authentication token has expired.")

    def test_05_wrong_token_type_returns_401(self):
        """Token with type != 'access' (e.g. 'refresh' or 'reset') is rejected with 401."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(self.learner_user["id"]),
            "email": self.learner_user["email"],
            "role": "learner",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "type": "refresh"  # Wrong token type!
        }
        refresh_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        self.client.cookies.set(settings.AUTH_COOKIE_NAME, refresh_token)
        res = self.client.get("/api/v1/test/auth-only")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid authentication token.")

    def test_06_missing_sub_claim_returns_401(self):
        """Token without 'sub' identifier claim is rejected with 401."""
        now = datetime.now(timezone.utc)
        payload = {
            "email": self.learner_user["email"],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "type": "access"
        }
        no_sub_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        self.client.cookies.set(settings.AUTH_COOKIE_NAME, no_sub_token)
        res = self.client.get("/api/v1/test/auth-only")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid authentication token.")

    def test_07_nonexistent_user_returns_401(self):
        """Token referencing a deleted/non-existent user ID returns 401."""
        ghost_token = create_access_token(
            user_id=999999,
            email="ghost@example.com",
            role="learner"
        )
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, ghost_token)
        res = self.client.get("/api/v1/test/auth-only")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "User account no longer exists.")

    def test_08_supabase_infrastructure_failure_returns_503(self):
        """Database connection or PostgREST infrastructure failure returns 503 Service Unavailable."""
        self.mock_service.simulate_db_failure = True
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.learner_token)
        res = self.client.get("/api/v1/test/auth-only")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["detail"], "Database service is currently unavailable.")

    # ─── 2. Role Authorization (require_learner, require_creator, require_admin) ──

    def test_09_learner_accesses_learner_endpoint_allowed(self):
        """Authenticated learner can access learner-protected endpoints."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.learner_token)
        res = self.client.get("/api/v1/test/learner-only")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["message"], "learner allowed")

    def test_10_creator_accesses_creator_endpoint_allowed(self):
        """Authenticated creator can access creator-protected endpoints."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.creator_token)
        res = self.client.get("/api/v1/test/creator-only")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["message"], "creator allowed")

    def test_11_admin_accesses_admin_endpoint_allowed(self):
        """Authenticated admin can access admin-protected endpoints."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.admin_token)
        res = self.client.get("/api/v1/test/admin-only")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["message"], "admin allowed")

    def test_12_learner_accesses_creator_endpoint_forbidden(self):
        """Authenticated learner attempting creator endpoint receives 403 Forbidden."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.learner_token)
        res = self.client.get("/api/v1/test/creator-only")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], "Creator privileges required.")

    def test_13_creator_accesses_learner_endpoint_forbidden(self):
        """Authenticated creator attempting learner endpoint receives 403 Forbidden."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.creator_token)
        res = self.client.get("/api/v1/test/learner-only")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], "Learner privileges required.")

    def test_14_learner_accesses_admin_endpoint_forbidden(self):
        """Authenticated learner attempting admin endpoint receives 403 Forbidden."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.learner_token)
        res = self.client.get("/api/v1/test/admin-only")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], "Admin privileges required.")

    def test_15_creator_accesses_admin_endpoint_forbidden(self):
        """Authenticated creator attempting admin endpoint receives 403 Forbidden."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.creator_token)
        res = self.client.get("/api/v1/test/admin-only")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], "Admin privileges required.")

    def test_16_unauthenticated_role_endpoint_access_returns_401(self):
        """Unauthenticated request to any role-protected route fails at 401 before 403."""
        for path in ["/api/v1/test/learner-only", "/api/v1/test/creator-only", "/api/v1/test/admin-only"]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 401, f"Failed 401 check for path: {path}")
            self.assertEqual(res.json()["detail"], "Authentication required.")

    # ─── 3. Database Authority (DB Role overrides JWT claim) ───────────────────────

    def test_17_jwt_role_creator_but_db_role_learner_denied_creator_access(self):
        """If JWT claims role='creator' but DB record is 'learner', creator access is 403 Forbidden."""
        # Create token claiming role='creator' for learner_user
        tampered_token = create_access_token(
            user_id=self.learner_user["id"],
            email=self.learner_user["email"],
            role="creator"  # Token claims creator, but DB role is 'learner'
        )
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, tampered_token)
        res = self.client.get("/api/v1/test/creator-only")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], "Creator privileges required.")

    def test_18_jwt_role_learner_but_db_role_creator_granted_creator_access(self):
        """If JWT claims role='learner' but DB record was upgraded to 'creator', creator access is 200 OK."""
        # Create token claiming role='learner' for creator_user
        stale_token = create_access_token(
            user_id=self.creator_user["id"],
            email=self.creator_user["email"],
            role="learner"  # Token claims learner, but DB role is 'creator'
        )
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, stale_token)
        res = self.client.get("/api/v1/test/creator-only")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["message"], "creator allowed")

    # ─── 4. Refactored /me Route ──────────────────────────────────────────────────

    def test_19_refactored_me_endpoint_returns_safe_current_user_profile(self):
        """GET /api/v1/auth/me uses canonical dependency and returns safe profile data."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, self.creator_token)
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("user", data)
        user = data["user"]
        self.assertEqual(user["id"], self.creator_user["id"])
        self.assertEqual(user["email"], self.creator_user["email"])
        self.assertEqual(user["name"], self.creator_user["name"])
        self.assertEqual(user["role"], "creator")
        self.assertNotIn("password", user)
        self.assertNotIn("token", data)

    def test_20_refactored_me_endpoint_unauthenticated_returns_401(self):
        """GET /api/v1/auth/me without cookie returns 401 Unauthorized."""
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Authentication required.")


if __name__ == "__main__":
    unittest.main()
