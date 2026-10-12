"""
Comprehensive Unit Tests for Phase 4 — Stage 5: Account Security & Role Onboarding
Tests:
- POST /api/v1/auth/set-role (role onboarding, role security rule, token reissue, safe response)
- POST /api/v1/auth/change-password (rotation, legacy support, token reissue, Stage 4 reset token invalidation)
- Complete isolation using dependency injection overrides. Real database is NEVER touched.
"""

import hmac
import logging
import unittest
from io import StringIO
from typing import Optional, Dict, Any, Union
import bcrypt
import jwt
from starlette.testclient import TestClient

from api.app.main import app
from api.app.services.users import get_user_service
from api.app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_password_reset_token,
    generate_password_hash_fingerprint,
)
from api.app.config import settings


class MockUserServiceStage5:
    """In-memory mock user service supporting Stage 5 tests."""

    def __init__(self):
        self.users: Dict[Union[int, str], Dict[str, Any]] = {}
        self.next_id = 1
        self.simulate_db_failure = False

    def add_user(
        self,
        name: str,
        email: str,
        password_hash: Optional[str] = None,
        role: Optional[str] = None,
        points: int = 0
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
            "joined_at": "2026-10-12T00:00:00Z"
        }
        self.users[uid] = record
        return dict(record)

    def get_by_id(self, user_id: Union[int, str], include_password: bool = False) -> Optional[Dict[str, Any]]:
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

    def get_by_email(self, email: str, include_password: bool = False) -> Optional[Dict[str, Any]]:
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

    def get_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        clean_id = identifier.strip().lower()
        for u in self.users.values():
            if u["email"].lower() == clean_id or u["name"].lower() == clean_id:
                return dict(u)
        return None

    def update_password(self, user_id: Union[int, str], new_password_hash: str) -> bool:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        uid = int(user_id) if str(user_id).isdigit() else user_id
        if uid in self.users:
            self.users[uid]["password"] = new_password_hash
            return True
        return False

    def update_role(self, user_id: Union[int, str], new_role: str) -> Optional[Dict[str, Any]]:
        if self.simulate_db_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        uid = int(user_id) if str(user_id).isdigit() else user_id
        if uid in self.users:
            self.users[uid]["role"] = new_role
            return self.get_by_id(uid)
        return None


class TestAuthStage5(unittest.TestCase):
    """Test suite for Phase 4 Stage 5: Role Onboarding & Password Rotation."""

    def setUp(self):
        self.mock_user_service = MockUserServiceStage5()
        app.dependency_overrides[get_user_service] = lambda: self.mock_user_service
        self.client = TestClient(app)

        # Standard unassigned user (role=None)
        self.unassigned_raw_pw = "InitialPass123!"
        self.unassigned_pw_hash = hash_password(self.unassigned_raw_pw)
        self.unassigned_user = self.mock_user_service.add_user(
            name="New User",
            email="newbie@example.com",
            password_hash=self.unassigned_pw_hash,
            role=None,
        )

        # Standard assigned learner
        self.learner_raw_pw = "LearnerPass123!"
        self.learner_pw_hash = hash_password(self.learner_raw_pw)
        self.learner_user = self.mock_user_service.add_user(
            name="Bob Learner",
            email="learner@example.com",
            password_hash=self.learner_pw_hash,
            role="learner",
        )

        # Standard assigned creator
        self.creator_raw_pw = "CreatorPass123!"
        self.creator_pw_hash = hash_password(self.creator_raw_pw)
        self.creator_user = self.mock_user_service.add_user(
            name="Carol Creator",
            email="creator@example.com",
            password_hash=self.creator_pw_hash,
            role="creator",
        )

        # Google-only user (no password)
        self.google_user = self.mock_user_service.add_user(
            name="Google Only",
            email="google@example.com",
            password_hash=None,
            role="learner",
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    def _auth_cookie(self, user: Dict[str, Any]) -> Dict[str, str]:
        token = create_access_token(
            user_id=user["id"],
            email=user["email"],
            role=user.get("role")
        )
        return {settings.AUTH_COOKIE_NAME: token}

    # =========================================================================
    # ROLE ONBOARDING TESTS (1 - 13)
    # =========================================================================

    def test_01_unauthenticated_set_role_returns_401(self):
        """1. unauthenticated /set-role -> 401"""
        res = self.client.post("/api/v1/auth/set-role", json={"role": "learner"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json()["detail"])

    def test_02_unassigned_user_to_learner_succeeds(self):
        """2. unassigned user -> learner succeeds"""
        cookies = self._auth_cookie(self.unassigned_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "learner"}, cookies=cookies)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["user"]["role"], "learner")
        self.assertIn("Role set to learner successfully", data["message"])

    def test_03_unassigned_user_to_creator_succeeds(self):
        """3. unassigned user -> creator succeeds"""
        cookies = self._auth_cookie(self.unassigned_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "creator"}, cookies=cookies)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["user"]["role"], "creator")
        self.assertIn("Role set to creator successfully", data["message"])

    def test_04_admin_assignment_rejected(self):
        """4. admin assignment rejected"""
        cookies = self._auth_cookie(self.unassigned_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "admin"}, cookies=cookies)
        self.assertEqual(res.status_code, 422)

    def test_05_arbitrary_role_rejected(self):
        """5. arbitrary role rejected"""
        cookies = self._auth_cookie(self.unassigned_user)
        for bad_role in ["superuser", "moderator", "guest", "root", ""]:
            res = self.client.post("/api/v1/auth/set-role", json={"role": bad_role}, cookies=cookies)
            self.assertEqual(res.status_code, 422)

    def test_06_existing_learner_cannot_promote_to_creator(self):
        """6. existing learner cannot promote to creator"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "creator"}, cookies=cookies)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Role has already been assigned", res.json()["detail"])

    def test_07_existing_creator_cannot_change_to_learner(self):
        """7. existing creator cannot change to learner"""
        cookies = self._auth_cookie(self.creator_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "learner"}, cookies=cookies)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Role has already been assigned", res.json()["detail"])

    def test_08_existing_learner_cannot_call_set_role_again(self):
        """8. existing learner cannot call set-role again with same role"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "learner"}, cookies=cookies)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Role has already been assigned", res.json()["detail"])

    def test_09_successful_role_assignment_updates_db(self):
        """9. successful role assignment updates DB"""
        cookies = self._auth_cookie(self.unassigned_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "creator"}, cookies=cookies)
        self.assertEqual(res.status_code, 200)

        # Check authoritative DB user
        db_user = self.mock_user_service.get_by_id(self.unassigned_user["id"])
        self.assertEqual(db_user["role"], "creator")

    def test_10_successful_role_assignment_reissues_nexora_access_token(self):
        """10. successful role assignment reissues nexora_access_token"""
        cookies = self._auth_cookie(self.unassigned_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "learner"}, cookies=cookies)
        self.assertEqual(res.status_code, 200)
        self.assertIn(settings.AUTH_COOKIE_NAME, res.cookies)

    def test_11_new_token_contains_updated_role_claim(self):
        """11. new token contains updated role claim"""
        cookies = self._auth_cookie(self.unassigned_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "creator"}, cookies=cookies)
        self.assertEqual(res.status_code, 200)

        new_cookie_val = res.cookies.get(settings.AUTH_COOKIE_NAME)
        self.assertIsNotNone(new_cookie_val)
        decoded = decode_access_token(new_cookie_val)
        self.assertEqual(decoded["role"], "creator")
        self.assertEqual(decoded["sub"], str(self.unassigned_user["id"]))

    def test_12_password_never_appears_in_set_role_response(self):
        """12. password never appears in response"""
        cookies = self._auth_cookie(self.unassigned_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "learner"}, cookies=cookies)
        self.assertEqual(res.status_code, 200)
        res_text = res.text.lower()
        self.assertNotIn("password", res_text)
        self.assertNotIn(self.unassigned_raw_pw.lower(), res_text)

    def test_13_jwt_never_appears_in_set_role_response(self):
        """13. JWT never appears in response body"""
        cookies = self._auth_cookie(self.unassigned_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "learner"}, cookies=cookies)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertNotIn("access_token", body)
        self.assertNotIn("token", body)
        self.assertNotIn("jwt", body)

    # =========================================================================
    # CHANGE PASSWORD TESTS (14 - 29)
    # =========================================================================

    def test_14_unauthenticated_change_password_returns_401(self):
        """14. unauthenticated -> 401"""
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": "ValidPassword123!",
            "new_password": "BrandNewPassword123!",
            "confirm_password": "BrandNewPassword123!",
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json()["detail"])

    def test_15_valid_current_password_changes_successfully(self):
        """15. valid current password changes successfully"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "NewSecretPass456!",
            "confirm_password": "NewSecretPass456!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["message"], "Password changed successfully.")

    def test_16_incorrect_current_password_rejected(self):
        """16. incorrect current password rejected"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": "WrongPassword999!",
            "new_password": "NewSecretPass456!",
            "confirm_password": "NewSecretPass456!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Current password is incorrect", res.json()["detail"])

    def test_17_password_shorter_than_8_rejected(self):
        """17. password shorter than 8 rejected"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "short",
            "confirm_password": "short",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 422)

    def test_18_password_longer_than_128_rejected(self):
        """18. password longer than 128 rejected"""
        cookies = self._auth_cookie(self.learner_user)
        too_long = "A" * 129
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": too_long,
            "confirm_password": too_long,
        }, cookies=cookies)
        self.assertEqual(res.status_code, 422)

    def test_19_mismatched_confirmation_rejected(self):
        """19. mismatched confirmation rejected"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "NewSecretPass456!",
            "confirm_password": "DifferentPass789!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 422)

    def test_20_identical_current_and_new_password_rejected(self):
        """20. identical current/new password rejected"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": self.learner_raw_pw,
            "confirm_password": self.learner_raw_pw,
        }, cookies=cookies)
        self.assertEqual(res.status_code, 422)

    def test_21_google_only_password_null_account_rejected(self):
        """21. Google-only/password=NULL account rejected"""
        cookies = self._auth_cookie(self.google_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": "AnyPassword123!",
            "new_password": "NewSecretPass456!",
            "confirm_password": "NewSecretPass456!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not have a password configured", res.json()["detail"])

    def test_22_stored_password_is_bcrypt(self):
        """22. stored password is bcrypt"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "BrandNewBcryptPass123!",
            "confirm_password": "BrandNewBcryptPass123!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 200)

        db_user = self.mock_user_service.get_by_id(self.learner_user["id"], include_password=True)
        stored_hash = db_user["password"]
        self.assertTrue(stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"))

    def test_23_bcrypt_cost_is_12(self):
        """23. bcrypt cost is 12"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "BrandNewBcryptPass123!",
            "confirm_password": "BrandNewBcryptPass123!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 200)

        db_user = self.mock_user_service.get_by_id(self.learner_user["id"], include_password=True)
        stored_hash = db_user["password"]
        parts = stored_hash.split("$")
        self.assertEqual(parts[2], "12")

    def test_24_old_password_fails_login(self):
        """24. old password fails login"""
        cookies = self._auth_cookie(self.learner_user)
        # Change password
        self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "BrandNewPassword999!",
            "confirm_password": "BrandNewPassword999!",
        }, cookies=cookies)

        # Attempt login with old password
        res = self.client.post("/api/v1/auth/login", json={
            "identifier": self.learner_user["email"],
            "password": self.learner_raw_pw,
        })
        self.assertEqual(res.status_code, 401)

    def test_25_new_password_succeeds_login(self):
        """25. new password succeeds login"""
        cookies = self._auth_cookie(self.learner_user)
        # Change password
        self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "BrandNewPassword999!",
            "confirm_password": "BrandNewPassword999!",
        }, cookies=cookies)

        # Attempt login with new password
        res = self.client.post("/api/v1/auth/login", json={
            "identifier": self.learner_user["email"],
            "password": "BrandNewPassword999!",
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["email"], self.learner_user["email"])

    def test_26_existing_stage4_reset_token_becomes_invalid_after_password_change(self):
        """26. existing Stage 4 reset token becomes invalid after password change"""
        # Issue a reset token before password change
        db_user_before = self.mock_user_service.get_by_id(self.learner_user["id"], include_password=True)
        reset_token = create_password_reset_token(
            user_id=db_user_before["id"],
            email=db_user_before["email"],
            current_password_hash=db_user_before["password"]
        )

        # Change password via authenticated endpoint
        cookies = self._auth_cookie(self.learner_user)
        change_res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "RotatedPassword123!",
            "confirm_password": "RotatedPassword123!",
        }, cookies=cookies)
        self.assertEqual(change_res.status_code, 200)

        # Now attempt to use old reset token
        reset_res = self.client.post("/api/v1/auth/reset-password", json={
            "token": reset_token,
            "new_password": "AnotherNewPassword456!",
            "confirm_password": "AnotherNewPassword456!",
        })
        self.assertEqual(reset_res.status_code, 400)
        self.assertIn("Invalid or expired password reset token", reset_res.json()["detail"])

    def test_27_successful_password_change_reissues_access_cookie(self):
        """27. successful password change reissues access cookie"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "RotatedPassword123!",
            "confirm_password": "RotatedPassword123!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 200)
        self.assertIn(settings.AUTH_COOKIE_NAME, res.cookies)

        token = res.cookies.get(settings.AUTH_COOKIE_NAME)
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], str(self.learner_user["id"]))
        self.assertEqual(payload["type"], "access")

    def test_28_jwt_is_not_exposed_in_response(self):
        """28. JWT is not exposed in response body"""
        cookies = self._auth_cookie(self.learner_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "RotatedPassword123!",
            "confirm_password": "RotatedPassword123!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertNotIn("token", body)
        self.assertNotIn("access_token", body)
        self.assertNotIn("jwt", body)

    def test_29_password_and_hash_never_logged(self):
        """29. password/hash never logged"""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        orig_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)

        try:
            cookies = self._auth_cookie(self.learner_user)
            self.client.post("/api/v1/auth/change-password", json={
                "current_password": self.learner_raw_pw,
                "new_password": "SuperSecretNewPassword999!",
                "confirm_password": "SuperSecretNewPassword999!",
            }, cookies=cookies)

            logs = log_stream.getvalue()
            self.assertNotIn(self.learner_raw_pw, logs)
            self.assertNotIn("SuperSecretNewPassword999!", logs)
            self.assertNotIn(self.learner_pw_hash, logs)
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(orig_level)

    # =========================================================================
    # ADDITIONAL EDGE CASES & RESILIENCE
    # =========================================================================

    def test_30_whitespace_and_case_normalization_in_set_role(self):
        """Normalize whitespace and case in set-role payload."""
        cookies = self._auth_cookie(self.unassigned_user)
        res = self.client.post("/api/v1/auth/set-role", json={"role": "  LEARNER  "}, cookies=cookies)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["role"], "learner")

    def test_31_werkzeug_legacy_password_change_succeeds(self):
        """User with legacy Werkzeug hash can successfully change their password."""
        # Add user with pbkdf2 werkzeug hash
        legacy_hash = "pbkdf2:sha256:260000$test$6a32dcf121b658514125d1988941cfb442bd3be91fc02fae38e6ca6f5d40cb97"
        # We can simulate legacy password verification using werkzeug or directly test with mock
        # But let's verify if verify_and_maybe_migrate_password handles it:
        from werkzeug.security import generate_password_hash
        w_pw = "LegacyWerkzeugPass1!"
        w_hash = generate_password_hash(w_pw)
        w_user = self.mock_user_service.add_user(
            name="Legacy User",
            email="legacy@example.com",
            password_hash=w_hash,
            role="learner",
        )
        cookies = self._auth_cookie(w_user)
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": w_pw,
            "new_password": "UpgradedBcryptPass123!",
            "confirm_password": "UpgradedBcryptPass123!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 200)

        # Confirm new stored hash is bcrypt 12
        db_user = self.mock_user_service.get_by_id(w_user["id"], include_password=True)
        self.assertTrue(db_user["password"].startswith("$2b$12$"))

    def test_32_database_error_on_set_role_returns_503(self):
        """Database error during set-role returns 503."""
        cookies = self._auth_cookie(self.unassigned_user)
        self.mock_user_service.simulate_db_failure = True
        res = self.client.post("/api/v1/auth/set-role", json={"role": "learner"}, cookies=cookies)
        self.assertEqual(res.status_code, 503)

    def test_33_database_error_on_change_password_returns_503(self):
        """Database error during change-password returns 503."""
        cookies = self._auth_cookie(self.learner_user)
        self.mock_user_service.simulate_db_failure = True
        res = self.client.post("/api/v1/auth/change-password", json={
            "current_password": self.learner_raw_pw,
            "new_password": "NewSecretPass456!",
            "confirm_password": "NewSecretPass456!",
        }, cookies=cookies)
        self.assertEqual(res.status_code, 503)


if __name__ == "__main__":
    unittest.main()
