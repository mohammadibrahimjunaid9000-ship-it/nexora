"""
Unit tests for Stage 1 Backend Security Foundation.
Verifies bcrypt password hashing, PyJWT creation & verification, HttpOnly cookie configuration,
and security failure modes. Does not require database connectivity.
"""

import unittest
from datetime import timedelta
import jwt
from starlette.requests import Request
from starlette.responses import Response

from api.app.config import Settings
from api.app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_auth_cookie_config,
    set_auth_cookie,
    delete_auth_cookie,
    get_token_from_request,
    InvalidTokenError,
    ExpiredTokenError,
    BCRYPT_ROUNDS,
)


class TestBackendSecurityFoundation(unittest.TestCase):

    def setUp(self):
        self.plain_password = "SecurePassword123!"
        self.wrong_password = "WrongPassword456!"

    # ─── 1. Password Hashing & Verification Tests ──────────────────────────────

    def test_01_password_hashing_produces_bcrypt_hash(self):
        """1. Password hashing produces a bcrypt hash (starts with $2b$ and round 12)."""
        hashed = hash_password(self.plain_password)
        self.assertIsInstance(hashed, str)
        self.assertTrue(hashed.startswith("$2b$"), "Bcrypt hash must start with $2b$")
        parts = hashed.split("$")
        self.assertEqual(int(parts[2]), BCRYPT_ROUNDS, "Bcrypt cost factor must match configured rounds")

    def test_02_correct_password_verifies_successfully(self):
        """2. Correct password verifies successfully against bcrypt hash."""
        hashed = hash_password(self.plain_password)
        self.assertTrue(verify_password(self.plain_password, hashed))

    def test_03_incorrect_password_fails(self):
        """3. Incorrect password fails verification."""
        hashed = hash_password(self.plain_password)
        self.assertFalse(verify_password(self.wrong_password, hashed))
        self.assertFalse(verify_password("", hashed))
        self.assertFalse(verify_password(self.plain_password, ""))

    def test_04_hashes_of_same_password_differ_due_to_salting(self):
        """4. Two hashes of the same password should not simply be identical because of bcrypt salting."""
        hash_1 = hash_password(self.plain_password)
        hash_2 = hash_password(self.plain_password)
        self.assertNotEqual(hash_1, hash_2, "Bcrypt hashes must differ due to unique salts")
        self.assertTrue(verify_password(self.plain_password, hash_1))
        self.assertTrue(verify_password(self.plain_password, hash_2))

    # ─── 2. JWT Creation & Verification Tests ─────────────────────────────────

    def test_05_jwt_creation_succeeds(self):
        """5. JWT creation succeeds and returns a non-empty string."""
        token = create_access_token(user_id=42, email="user@nexora.com", role="creator")
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 20)

    def test_06_jwt_contains_required_non_sensitive_claims(self):
        """6. JWT contains required non-sensitive claims (sub, email, role, iat, exp, type)."""
        token = create_access_token(user_id="101", email="learner@nexora.com", role="learner")
        claims = decode_access_token(token)
        self.assertEqual(claims.get("sub"), "101")
        self.assertEqual(claims.get("email"), "learner@nexora.com")
        self.assertEqual(claims.get("role"), "learner")
        self.assertEqual(claims.get("type"), "access")
        self.assertIn("iat", claims)
        self.assertIn("exp", claims)
        self.assertGreater(claims["exp"], claims["iat"])

    def test_07_jwt_verification_succeeds_for_valid_token(self):
        """7. JWT verification succeeds for a valid token."""
        token = create_access_token(user_id=1, email="test@nexora.com", role="creator")
        decoded = decode_access_token(token)
        self.assertEqual(decoded["sub"], "1")
        self.assertEqual(decoded["email"], "test@nexora.com")

    def test_08_expired_jwt_is_rejected(self):
        """8. Expired JWT is rejected with ExpiredTokenError."""
        expired_token = create_access_token(
            user_id=1,
            email="test@nexora.com",
            role="learner",
            expires_delta=timedelta(seconds=-10)  # Created in the past
        )
        with self.assertRaises(ExpiredTokenError):
            decode_access_token(expired_token)

    def test_09_invalid_or_tampered_jwt_is_rejected(self):
        """9. Invalid or tampered JWT is rejected with InvalidTokenError."""
        valid_token = create_access_token(user_id=1, email="test@nexora.com", role="learner")
        tampered_token = valid_token[:-4] + "xyz9"

        with self.assertRaises(InvalidTokenError):
            decode_access_token(tampered_token)

        with self.assertRaises(InvalidTokenError):
            decode_access_token("completely.invalid.token")

        with self.assertRaises(InvalidTokenError):
            decode_access_token("")

    def test_10_jwt_does_not_contain_password_or_sensitive_fields(self):
        """10. JWT does not contain password or password hash."""
        token = create_access_token(user_id=99, email="safe@nexora.com", role="learner")
        # Insecurely decode without verifying to inspect all raw payload keys
        raw_payload = jwt.decode(token, options={"verify_signature": False})
        forbidden_keys = {"password", "password_hash", "hash", "secret", "google_token", "access_token"}
        for k in raw_payload.keys():
            self.assertNotIn(k.lower(), forbidden_keys)

    # ─── 3. HttpOnly Cookie Foundation Tests ──────────────────────────────────

    def test_11_cookie_configuration_is_httponly(self):
        """11. Cookie configuration is HttpOnly and has an explicit path."""
        config = get_auth_cookie_config()
        self.assertTrue(config["httponly"], "Cookie must always be HttpOnly=True")
        self.assertEqual(config["path"], "/", "Cookie must have an explicit path")
        self.assertIn("samesite", config)
        self.assertIn("key", config)
        self.assertIn("max_age", config)

    def test_12_production_cookie_configuration_can_be_configured_securely(self):
        """12. Production settings enforce a non-default SECRET_KEY and secure cookies."""
        # 1. Dev mode allows debug settings
        dev_settings = Settings(
            DEBUG=True,
            SECRET_KEY="dev_placeholder",
            AUTH_COOKIE_SECURE=False
        )
        self.assertTrue(dev_settings.DEBUG)
        self.assertFalse(dev_settings.AUTH_COOKIE_SECURE)

        # 2. Production mode requires secure key and secure cookie flag
        with self.assertRaises(ValueError):
            Settings(
                DEBUG=False,
                SECRET_KEY="nexora_production_jwt_secret_dev_key",  # Default placeholder
                AUTH_COOKIE_SECURE=True
            )

        with self.assertRaises(ValueError):
            Settings(
                DEBUG=False,
                SECRET_KEY="valid-high-entropy-production-secret-value-32chars",
                AUTH_COOKIE_SECURE=False  # Insecure cookie flag in production
            )

        # 3. Valid production configuration passes
        prod_settings = Settings(
            DEBUG=False,
            SECRET_KEY="valid-high-entropy-production-secret-value-32chars",
            AUTH_COOKIE_SECURE=True
        )
        self.assertFalse(prod_settings.DEBUG)
        self.assertTrue(prod_settings.AUTH_COOKIE_SECURE)

    # ─── 4. Cookie Set / Extract / Delete Helpers ─────────────────────────────

    def test_13_cookie_helpers_interaction(self):
        """Verify set_auth_cookie sets cookie and get_token_from_request extracts strictly from cookies."""
        token = create_access_token(user_id=1, email="cookie@nexora.com", role="learner")
        response = Response()
        set_auth_cookie(response, token)

        # Inspect set-cookie header in response
        raw_cookie = response.headers.get("set-cookie", "")
        self.assertIn("httponly", raw_cookie.lower())

        # Verify get_token_from_request with mock request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/me",
            "headers": [
                (b"cookie", f"nexora_access_token={token}".encode("utf-8"))
            ]
        }
        req = Request(scope)
        extracted = get_token_from_request(req)
        self.assertEqual(extracted, token)

        # Verify delete_auth_cookie
        delete_response = Response()
        delete_auth_cookie(delete_response)
        del_cookie = delete_response.headers.get("set-cookie", "")
        self.assertTrue("max-age=0" in del_cookie.lower() or "expires=" in del_cookie.lower())


if __name__ == "__main__":
    unittest.main()
