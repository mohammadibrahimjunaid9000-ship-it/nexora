"""
Comprehensive Unit Tests for Phase 4 — Stage 2: Authentication Backend
Tests registration, login, logout, current user (/me), and legacy password migration.
Uses dependency injection overrides to completely isolate from production Supabase database.
"""

import unittest
from datetime import timedelta
from unittest.mock import MagicMock
from starlette.testclient import TestClient
from werkzeug.security import generate_password_hash

from api.app.main import app
from api.app.services.users import get_user_service, UserService
from api.app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
)
from api.app.config import settings


class MockUserService:
    """In-memory mock user service implementing existing users table behavior."""

    def __init__(self):
        self.users = {}
        self.next_id = 1

    def get_by_id(self, user_id):
        uid = int(user_id) if str(user_id).isdigit() else user_id
        user = self.users.get(uid)
        if not user:
            return None
        safe = dict(user)
        safe.pop("password", None)
        return safe

    def get_by_email(self, email, include_password=False):
        clean_email = email.strip().lower()
        for u in self.users.values():
            if u["email"].lower() == clean_email:
                res = dict(u)
                if not include_password:
                    res.pop("password", None)
                return res
        return None

    def get_by_identifier(self, identifier):
        clean_id = identifier.strip().lower()
        for u in self.users.values():
            if u["email"].lower() == clean_id or u["name"].lower() == clean_id:
                return dict(u)  # Returns with password for login verification
        return None

    def create_user(self, name, email, password_hash, role):
        uid = self.next_id
        self.next_id += 1
        record = {
            "id": uid,
            "name": name.strip(),
            "email": email.strip().lower(),
            "password": password_hash,
            "role": role,
            "points": 0,
            "joined_at": "2026-10-11T00:00:00Z"
        }
        self.users[uid] = record
        safe = dict(record)
        safe.pop("password", None)
        return safe

    def update_password(self, user_id, new_password_hash):
        uid = int(user_id) if str(user_id).isdigit() else user_id
        if uid in self.users:
            self.users[uid]["password"] = new_password_hash
            return True
        return False


class TestAuthStage2(unittest.TestCase):

    def setUp(self):
        self.mock_user_service = MockUserService()
        app.dependency_overrides[get_user_service] = lambda: self.mock_user_service
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    # ─── REGISTRATION TESTS ───────────────────────────────────────────────────

    def test_01_valid_learner_registration(self):
        """Valid registration as learner succeeds (201) and sets HttpOnly cookie."""
        payload = {
            "name": "Jane Learner",
            "email": "jane@example.com",
            "password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
            "role": "learner"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["message"], "Account created successfully.")
        self.assertEqual(data["user"]["role"], "learner")
        self.assertEqual(data["user"]["email"], "jane@example.com")
        self.assertNotIn("password", data["user"])
        self.assertNotIn("access_token", data)

        # Verify HttpOnly cookie
        cookie_header = res.headers.get("set-cookie", "")
        self.assertIn(settings.AUTH_COOKIE_NAME, cookie_header)
        self.assertIn("httponly", cookie_header.lower())

    def test_02_valid_creator_registration(self):
        """Valid registration as creator succeeds (201)."""
        payload = {
            "name": "Alex Creator",
            "email": "alex@example.com",
            "password": "CreatorPassword123!",
            "confirm_password": "CreatorPassword123!",
            "role": "creator"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["user"]["role"], "creator")

    def test_03_default_learner_role_when_omitted(self):
        """Role defaults to 'learner' when omitted."""
        payload = {
            "name": "Sam Default",
            "email": "sam@example.com",
            "password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["user"]["role"], "learner")

    def test_04_registration_missing_fields_fails(self):
        """Registration fails (422) if required fields are missing."""
        res = self.client.post("/api/v1/auth/register", json={"email": "sam@example.com"})
        self.assertEqual(res.status_code, 422)

    def test_05_registration_invalid_email_fails(self):
        """Registration fails (422) if email format is invalid."""
        payload = {
            "name": "Invalid Email User",
            "email": "not-an-email",
            "password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_06_registration_password_too_short_fails(self):
        """Registration fails (422) if password is less than 8 characters."""
        payload = {
            "name": "Short Pass User",
            "email": "short@example.com",
            "password": "short7!",
            "confirm_password": "short7!"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_07_registration_password_mismatch_fails(self):
        """Registration fails (422) if password confirmation does not match."""
        payload = {
            "name": "Mismatch User",
            "email": "mismatch@example.com",
            "password": "Password123!",
            "confirm_password": "DifferentPassword123!"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_08_registration_as_admin_is_strictly_rejected(self):
        """Self-registration as admin is forbidden (422)."""
        payload = {
            "name": "Hacker Admin",
            "email": "admin@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "role": "admin"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_09_duplicate_email_rejected_case_insensitively(self):
        """Duplicate email registration is rejected with 409 Conflict."""
        payload = {
            "name": "First User",
            "email": "duplicate@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        res1 = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res1.status_code, 201)

        # Duplicate attempt with uppercase letters
        payload_dup = dict(payload)
        payload_dup["email"] = "DUPLICATE@EXAMPLE.COM"
        res2 = self.client.post("/api/v1/auth/register", json=payload_dup)
        self.assertEqual(res2.status_code, 409)
        self.assertIn("already exists", res2.json()["detail"])

    def test_10_password_stored_as_bcrypt_hash(self):
        """Password in database is stored as a bcrypt hash."""
        payload = {
            "name": "Hash Check",
            "email": "hashcheck@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        uid = res.json()["user"]["id"]
        stored_hash = self.mock_user_service.users[uid]["password"]
        self.assertTrue(stored_hash.startswith("$2b$"))
        self.assertTrue(verify_password("Password123!", stored_hash))

    # ─── LOGIN TESTS ──────────────────────────────────────────────────────────

    def test_11_valid_email_login(self):
        """Login with valid email and password succeeds and sets HttpOnly cookie."""
        pw_hash = hash_password("ValidPassword123!")
        self.mock_user_service.create_user("Alice", "alice@example.com", pw_hash, "learner")

        res = self.client.post("/api/v1/auth/login", json={
            "identifier": "alice@example.com",
            "password": "ValidPassword123!"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["message"], "Login successful.")
        self.assertEqual(data["user"]["email"], "alice@example.com")
        self.assertNotIn("password", data["user"])
        self.assertNotIn("access_token", data)

        cookie_header = res.headers.get("set-cookie", "")
        self.assertIn(settings.AUTH_COOKIE_NAME, cookie_header)
        self.assertIn("httponly", cookie_header.lower())

    def test_12_valid_name_login(self):
        """Login with valid user name succeeds."""
        pw_hash = hash_password("ValidPassword123!")
        self.mock_user_service.create_user("BobBuilder", "bob@example.com", pw_hash, "creator")

        res = self.client.post("/api/v1/auth/login", json={
            "identifier": "BobBuilder",
            "password": "ValidPassword123!"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["name"], "BobBuilder")

    def test_13_login_email_case_insensitivity(self):
        """Email lookup is case-insensitive during login."""
        pw_hash = hash_password("ValidPassword123!")
        self.mock_user_service.create_user("Charlie", "charlie@example.com", pw_hash, "learner")

        res = self.client.post("/api/v1/auth/login", json={
            "identifier": "CHARLIE@EXAMPLE.COM",
            "password": "ValidPassword123!"
        })
        self.assertEqual(res.status_code, 200)

    def test_14_login_wrong_password_fails(self):
        """Login with incorrect password returns 401."""
        pw_hash = hash_password("ValidPassword123!")
        self.mock_user_service.create_user("Dana", "dana@example.com", pw_hash, "learner")

        res = self.client.post("/api/v1/auth/login", json={
            "identifier": "dana@example.com",
            "password": "WrongPassword123!"
        })
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    def test_15_login_unknown_user_fails(self):
        """Login with unknown user returns 401."""
        res = self.client.post("/api/v1/auth/login", json={
            "identifier": "nonexistent@example.com",
            "password": "Password123!"
        })
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    def test_16_google_only_null_password_account_fails(self):
        """Accounts with null password (Google-only) return 400 prompt."""
        self.mock_user_service.create_user("GoogleUser", "google@example.com", None, "learner")

        res = self.client.post("/api/v1/auth/login", json={
            "identifier": "google@example.com",
            "password": "AnyPassword123!"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not have a password", res.json()["detail"])

    # ─── LEGACY PASSWORD MIGRATION TESTS ──────────────────────────────────────

    def test_17_legacy_werkzeug_hash_authenticates_and_migrates_to_bcrypt(self):
        """Legacy Werkzeug PBKDF2 hash authenticates and transparently upgrades to bcrypt."""
        old_werkzeug_hash = generate_password_hash("LegacyPassword123!", method="pbkdf2:sha256")
        user = self.mock_user_service.create_user("LegacyUser", "legacy@example.com", old_werkzeug_hash, "learner")

        # 1. Login with correct password
        res = self.client.post("/api/v1/auth/login", json={
            "identifier": "legacy@example.com",
            "password": "LegacyPassword123!"
        })
        self.assertEqual(res.status_code, 200)

        # 2. Verify stored password has been upgraded to bcrypt
        updated_hash = self.mock_user_service.users[user["id"]]["password"]
        self.assertTrue(updated_hash.startswith("$2b$"))
        self.assertTrue(verify_password("LegacyPassword123!", updated_hash))

    def test_18_incorrect_legacy_password_fails_and_does_not_upgrade(self):
        """Incorrect password against legacy Werkzeug hash fails and does not modify DB."""
        old_werkzeug_hash = generate_password_hash("LegacyPassword123!", method="pbkdf2:sha256")
        user = self.mock_user_service.create_user("LegacyUser2", "legacy2@example.com", old_werkzeug_hash, "learner")

        res = self.client.post("/api/v1/auth/login", json={
            "identifier": "legacy2@example.com",
            "password": "WrongPassword123!"
        })
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self.mock_user_service.users[user["id"]]["password"], old_werkzeug_hash)

    # ─── /me ENDPOINT TESTS ───────────────────────────────────────────────────

    def test_19_me_with_valid_cookie(self):
        """GET /api/v1/auth/me returns current user profile when valid cookie is presented."""
        user = self.mock_user_service.create_user("Eve", "eve@example.com", "hash", "creator")
        token = create_access_token(user_id=user["id"], email=user["email"], role=user["role"])

        self.client.cookies.set(settings.AUTH_COOKIE_NAME, token)
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 200)
        data = res.json()["user"]
        self.assertEqual(data["id"], user["id"])
        self.assertEqual(data["email"], "eve@example.com")
        self.assertEqual(data["role"], "creator")
        self.assertNotIn("password", data)

    def test_20_me_missing_cookie_fails(self):
        """GET /api/v1/auth/me returns 401 when auth cookie is absent."""
        self.client.cookies.clear()
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Authentication required.")

    def test_21_me_expired_token_fails(self):
        """GET /api/v1/auth/me returns 401 when token has expired."""
        expired_token = create_access_token(
            user_id=1, email="test@example.com", expires_delta=timedelta(seconds=-10)
        )
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, expired_token)
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)
        self.assertIn("expired", res.json()["detail"].lower())

    def test_22_me_malformed_token_fails(self):
        """GET /api/v1/auth/me returns 401 on malformed or tampered token."""
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, "malformed.invalid.token")
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)
        self.assertIn("invalid", res.json()["detail"].lower())

    def test_23_me_nonexistent_user_fails(self):
        """GET /api/v1/auth/me returns 401 if user was deleted from database."""
        token = create_access_token(user_id=999, email="deleted@example.com", role="learner")
        self.client.cookies.set(settings.AUTH_COOKIE_NAME, token)
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)
        self.assertIn("no longer exists", res.json()["detail"])

    # ─── LOGOUT TESTS ─────────────────────────────────────────────────────────

    def test_24_logout_clears_cookie_and_is_idempotent(self):
        """POST /api/v1/auth/logout clears auth cookie and is safe to call repeatedly."""
        # 1. First logout call
        res = self.client.post("/api/v1/auth/logout")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["message"], "Logged out successfully.")
        cookie_header = res.headers.get("set-cookie", "")
        self.assertTrue("max-age=0" in cookie_header.lower() or "expires=" in cookie_header.lower())

        # 2. Second logout call (idempotent)
        res2 = self.client.post("/api/v1/auth/logout")
        self.assertEqual(res2.status_code, 200)


if __name__ == "__main__":
    unittest.main()
