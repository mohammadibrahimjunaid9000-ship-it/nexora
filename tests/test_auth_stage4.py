"""
Comprehensive Unit Tests for Phase 4 — Stage 4: Password Recovery / Password Reset
Tests forgot-password, reset-password, token signing, expiration, HMAC fingerprint validation,
single-use invalidation, user enumeration protection, and security isolation.
Uses dependency injection overrides to completely isolate from production Supabase database.
"""

import unittest
from datetime import timedelta, datetime, timezone
import jwt
import logging
from io import StringIO
from starlette.testclient import TestClient

from api.app.main import app
from api.app.services.users import get_user_service
from api.app.services.email import get_email_service, EmailService
from api.app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_password_reset_token,
    generate_password_hash_fingerprint,
)
from api.app.config import settings


class MockUserServiceStage4:
    """In-memory mock user service supporting Stage 4 password recovery tests."""

    def __init__(self):
        self.users = {}
        self.next_id = 1
        self.simulate_db_failure = False

    def add_user(self, name: str, email: str, password_hash: str = None, role: str = "learner", points: int = 0) -> dict:
        uid = self.next_id
        self.next_id += 1
        record = {
            "id": uid,
            "name": name.strip(),
            "email": email.strip().lower(),
            "password": password_hash,
            "role": role,
            "points": points,
            "joined_at": "2026-10-11T00:00:00Z"
        }
        self.users[uid] = record
        return dict(record)

    def get_by_id(self, user_id, include_password=False):
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        uid = int(user_id) if str(user_id).isdigit() else user_id
        user = self.users.get(uid)
        if not user:
            return None
        safe = dict(user)
        if not include_password:
            safe.pop("password", None)
        return safe

    def get_by_email(self, email, include_password=False):
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

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
                return dict(u)
        return None

    def update_password(self, user_id, new_password_hash):
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        uid = int(user_id) if str(user_id).isdigit() else user_id
        if uid in self.users:
            self.users[uid]["password"] = new_password_hash
            return True
        return False


class TestAuthStage4PasswordReset(unittest.TestCase):
    """Test suite for Phase 4 Stage 4 password recovery implementation."""

    def setUp(self):
        self.mock_user_service = MockUserServiceStage4()
        self.email_service = EmailService()

        app.dependency_overrides[get_user_service] = lambda: self.mock_user_service
        app.dependency_overrides[get_email_service] = lambda: self.email_service
        self.client = TestClient(app)

        # Seed test user with known password
        self.raw_password = "OriginalPassword123!"
        self.password_hash = hash_password(self.raw_password)
        self.user = self.mock_user_service.add_user(
            name="Alice Learner",
            email="alice@example.com",
            password_hash=self.password_hash,
            role="learner"
        )

        # Seed Google-only user with password = None
        self.google_user = self.mock_user_service.add_user(
            name="Google User",
            email="googleuser@example.com",
            password_hash=None,
            role="learner"
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    # ─── 1. Forgot Password Flow & User Enumeration Protection ─────────────────────

    def test_01_existing_email_returns_200(self):
        """Requesting password reset for an existing account returns HTTP 200 with generic message."""
        res = self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()["message"],
            "If an account exists with this email, password reset instructions have been sent."
        )

    def test_02_existing_password_account_dispatches_notification(self):
        """Existing account with a password triggers email notification with a valid reset token."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        self.assertEqual(len(self.email_service.sent_messages), 1)
        msg = self.email_service.sent_messages[0]
        self.assertEqual(msg["to_email"], "alice@example.com")
        self.assertIn("reset_token", msg)
        self.assertTrue(len(msg["reset_token"]) > 20)

    def test_03_nonexistent_email_returns_identical_200(self):
        """Nonexistent email returns identical 200 message (anti-enumeration)."""
        res = self.client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@example.com"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()["message"],
            "If an account exists with this email, password reset instructions have been sent."
        )

    def test_04_nonexistent_email_does_not_dispatch_notification(self):
        """Nonexistent email does not trigger any notification dispatch."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@example.com"})
        self.assertEqual(len(self.email_service.sent_messages), 0)

    def test_05_google_only_account_returns_identical_200(self):
        """Google-only account (password is NULL) returns identical 200 message (anti-enumeration)."""
        res = self.client.post("/api/v1/auth/forgot-password", json={"email": "googleuser@example.com"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()["message"],
            "If an account exists with this email, password reset instructions have been sent."
        )

    def test_06_google_only_account_does_not_generate_reset_token(self):
        """Google-only account does not trigger email notification or token generation."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "googleuser@example.com"})
        self.assertEqual(len(self.email_service.sent_messages), 0)

    def test_07_invalid_email_format_returns_422(self):
        """Malformed email address fails schema validation with HTTP 422."""
        res = self.client.post("/api/v1/auth/forgot-password", json={"email": "not-an-email"})
        self.assertEqual(res.status_code, 422)

    # ─── 2. Password Reset Flow & Verification ────────────────────────────────────

    def test_08_valid_reset_token_resets_password(self):
        """Submitting a valid reset token with matching password successfully updates password."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        new_pw = "NewSecurePassword456!"
        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": new_pw,
            "confirm_password": new_pw
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()["message"],
            "Password reset successfully. You can now log in with your new password."
        )

    def test_09_new_password_stored_as_bcrypt(self):
        """Updated password in the database is a valid bcrypt hash ($2b$)."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        new_pw = "BrandNewSecret789!"
        self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": new_pw,
            "confirm_password": new_pw
        })

        stored_user = self.mock_user_service.get_by_id(self.user["id"], include_password=True)
        stored_hash = stored_user["password"]
        self.assertTrue(stored_hash.startswith("$2b$"))

    def test_10_new_password_uses_bcrypt_cost_12(self):
        """Updated password hash uses bcrypt cost factor 12 ($2b$12$)."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        new_pw = "BrandNewSecret789!"
        self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": new_pw,
            "confirm_password": new_pw
        })

        stored_user = self.mock_user_service.get_by_id(self.user["id"], include_password=True)
        stored_hash = stored_user["password"]
        self.assertTrue(stored_hash.startswith("$2b$12$"))

    def test_11_old_password_no_longer_works(self):
        """After password reset, the previous password is rejected."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        new_pw = "UpdatedPassword456!"
        self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": new_pw,
            "confirm_password": new_pw
        })

        # Attempt login with old password
        res = self.client.post("/api/v1/auth/login", json={
            "email": "alice@example.com",
            "password": self.raw_password
        })
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    def test_12_new_password_works_through_login(self):
        """After password reset, login succeeds using the new password."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        new_pw = "UpdatedPassword456!"
        self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": new_pw,
            "confirm_password": new_pw
        })

        # Login with new password
        res = self.client.post("/api/v1/auth/login", json={
            "email": "alice@example.com",
            "password": new_pw
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("user", res.json())
        self.assertIn(settings.AUTH_COOKIE_NAME, res.cookies)

    # ─── 3. Token Security, Invalidation & Edge Cases ─────────────────────────────

    def test_13_expired_reset_token_returns_400(self):
        """Expired password reset token is rejected with HTTP 400."""
        expired_token = create_password_reset_token(
            user_id=self.user["id"],
            email=self.user["email"],
            current_password_hash=self.password_hash,
            expires_delta=timedelta(seconds=-10)
        )
        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": expired_token,
            "new_password": "NewValidPassword123!",
            "confirm_password": "NewValidPassword123!"
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "Invalid or expired password reset token.")

    def test_14_tampered_reset_token_returns_400(self):
        """Tampered reset token with invalid signature returns HTTP 400."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]
        tampered_token = token[:-5] + "XXXXX"

        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": tampered_token,
            "new_password": "NewValidPassword123!",
            "confirm_password": "NewValidPassword123!"
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "Invalid or expired password reset token.")

    def test_15_wrong_token_type_returns_400(self):
        """Access token (type='access') submitted to reset-password endpoint returns HTTP 400."""
        access_token = create_access_token(
            user_id=self.user["id"],
            email=self.user["email"],
            role="learner"
        )
        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": access_token,
            "new_password": "NewValidPassword123!",
            "confirm_password": "NewValidPassword123!"
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "Invalid or expired password reset token.")

    def test_16_missing_subject_returns_400(self):
        """Reset token missing subject identifier returns HTTP 400."""
        now = datetime.now(timezone.utc)
        payload = {
            "email": self.user["email"],
            "fingerprint": generate_password_hash_fingerprint(self.password_hash),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "type": "reset"
        }
        no_sub_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": no_sub_token,
            "new_password": "NewValidPassword123!",
            "confirm_password": "NewValidPassword123!"
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "Invalid or expired password reset token.")

    def test_17_nonexistent_user_referenced_by_reset_token_returns_400(self):
        """Reset token referencing a nonexistent user ID returns HTTP 400."""
        ghost_token = create_password_reset_token(
            user_id=99999,
            email="ghost@example.com",
            current_password_hash=self.password_hash
        )
        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": ghost_token,
            "new_password": "NewValidPassword123!",
            "confirm_password": "NewValidPassword123!"
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "Invalid or expired password reset token.")

    def test_18_fingerprint_mismatch_returns_400(self):
        """Token with an invalid or mismatched fingerprint is rejected with HTTP 400."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(self.user["id"]),
            "email": self.user["email"],
            "fingerprint": "bad_fingerprint_1234567890abcdef",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "type": "reset"
        }
        bad_fingerprint_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": bad_fingerprint_token,
            "new_password": "NewValidPassword123!",
            "confirm_password": "NewValidPassword123!"
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "Invalid or expired password reset token.")

    def test_19_reusing_a_consumed_reset_token_returns_400(self):
        """Reusing a successfully redeemed reset token fails because the password hash changed."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        new_pw1 = "FirstPasswordReset123!"
        res1 = self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": new_pw1,
            "confirm_password": new_pw1
        })
        self.assertEqual(res1.status_code, 200)

        # Attempt to reuse the SAME token to set a second password
        new_pw2 = "SecondPasswordAttempt456!"
        res2 = self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": new_pw2,
            "confirm_password": new_pw2
        })
        self.assertEqual(res2.status_code, 400)
        self.assertEqual(res2.json()["detail"], "Invalid or expired password reset token.")

    def test_20_previously_issued_token_becomes_invalid_after_password_change(self):
        """If multiple reset tokens were requested, redeeming one invalidates all prior tokens."""
        # Request token A
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token_a = self.email_service.sent_messages[0]["reset_token"]

        # Request token B
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token_b = self.email_service.sent_messages[1]["reset_token"]

        # Redeem token B successfully
        new_pw = "NewPasswordSetViaTokenB!"
        res_b = self.client.post("/api/v1/auth/reset-password", json={
            "token": token_b,
            "new_password": new_pw,
            "confirm_password": new_pw
        })
        self.assertEqual(res_b.status_code, 200)

        # Now attempting to use token A must fail
        res_a = self.client.post("/api/v1/auth/reset-password", json={
            "token": token_a,
            "new_password": "AttemptUsingTokenA123!",
            "confirm_password": "AttemptUsingTokenA123!"
        })
        self.assertEqual(res_a.status_code, 400)
        self.assertEqual(res_a.json()["detail"], "Invalid or expired password reset token.")

    # ─── 4. Input Validation & Boundaries ─────────────────────────────────────────

    def test_21_mismatched_passwords_are_rejected(self):
        """Mismatched new_password and confirm_password are rejected with HTTP 422."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "PasswordOne123!",
            "confirm_password": "PasswordMismatch456!"
        })
        self.assertEqual(res.status_code, 422)

    def test_22_password_shorter_than_8_is_rejected(self):
        """Password shorter than 8 characters is rejected with HTTP 422."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "Short1!",
            "confirm_password": "Short1!"
        })
        self.assertEqual(res.status_code, 422)

    def test_23_password_longer_than_128_is_rejected(self):
        """Password longer than 128 characters is rejected with HTTP 422."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        too_long = "A" * 129
        res = self.client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": too_long,
            "confirm_password": too_long
        })
        self.assertEqual(res.status_code, 422)

    # ─── 5. Privacy, Logging & Boundary Isolation ─────────────────────────────────

    def test_24_reset_token_never_included_in_normal_api_response(self):
        """Forgot-password response body never exposes the reset token."""
        res = self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        data = res.json()
        self.assertNotIn("token", data)
        self.assertNotIn("reset_token", data)
        self.assertEqual(list(data.keys()), ["message"])

    def test_25_reset_token_is_never_written_to_logs(self):
        """Server logs do not contain the raw reset token string."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
            token = self.email_service.sent_messages[0]["reset_token"]
            log_output = log_stream.getvalue()
            self.assertNotIn(token, log_output)
        finally:
            root_logger.removeHandler(handler)

    def test_26_password_hash_is_never_written_to_logs(self):
        """Server logs do not contain the raw password hash."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
            token = self.email_service.sent_messages[0]["reset_token"]
            self.client.post("/api/v1/auth/reset-password", json={
                "token": token,
                "new_password": "NewSecurePassword123!",
                "confirm_password": "NewSecurePassword123!"
            })
            log_output = log_stream.getvalue()
            self.assertNotIn(self.password_hash, log_output)
        finally:
            root_logger.removeHandler(handler)

    def test_27_reset_token_cannot_access_me_endpoint(self):
        """Reset token passed as auth cookie to /me is rejected with 401."""
        self.client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        token = self.email_service.sent_messages[0]["reset_token"]

        self.client.cookies.set(settings.AUTH_COOKIE_NAME, token)
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid authentication token.")

    def test_28_existing_stage_1_2_3_behavior_remains_intact(self):
        """Standard login and /me work normally for active user."""
        res = self.client.post("/api/v1/auth/login", json={
            "email": "alice@example.com",
            "password": self.raw_password
        })
        self.assertEqual(res.status_code, 200)

        # /me succeeds with cookie
        me_res = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["email"], "alice@example.com")


if __name__ == "__main__":
    unittest.main()
