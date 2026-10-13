"""
Comprehensive Unit Tests for Phase 4 — Stage 6A: Google OAuth Service & Identity Validation
Tests:
- Google authorization URL generation, parameters, scopes
- Calendar scopes strictly absent
- Anti-CSRF state token generation, expiration, signature verification
- Double-submit cookie binding / replayed state prevention
- Open redirect sanitization
- Authorization code exchange via HTTP (success, errors, timeouts, malformed payloads)
- ID token cryptographic validation (RS256, issuer, audience, expiration, claims)
- Verified email enforcement (rejecting unverified emails)
- HTTP /url endpoint with HttpOnly state cookie
- Complete isolation using mocks and synthetic RSA key pairs. Real Google servers and DB are NEVER touched.
"""

import time
import unittest
import urllib.parse
from unittest.mock import MagicMock, patch

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from api.app.config import settings
from api.app.main import app
from api.app.services.google_auth import (
    ExpiredIdTokenError,
    ExpiredStateError,
    GoogleAuthConfigurationError,
    GoogleAuthError,
    GoogleAuthService,
    InvalidCodeError,
    InvalidIdTokenError,
    InvalidStateError,
    UnverifiedEmailError,
    get_google_auth_service,
)


class TestGoogleAuthStage6A(unittest.TestCase):
    """Test suite for Stage 6A: Google OAuth Service & Identity Validation."""

    @classmethod
    def setUpClass(cls):
        # Generate a test RSA 2048-bit key pair for synthetic Google ID tokens
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()
        cls.public_pem = cls.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        cls.test_client_id = "test-nexora-google-client-id.apps.googleusercontent.com"
        cls.test_client_secret = "test-nexora-google-client-secret"
        cls.test_redirect_uri = "http://localhost:3000/api/auth/callback/google"

    def setUp(self):
        self.service = GoogleAuthService(
            client_id=self.test_client_id,
            client_secret=self.test_client_secret,
            redirect_uri=self.test_redirect_uri,
        )
        self.client = TestClient(app)

    def _create_synthetic_id_token(
        self,
        sub: str = "google-sub-123456",
        email: str = "alice@example.com",
        email_verified: bool = True,
        name: str = "Alice Learner",
        picture: str = "https://example.com/alice.jpg",
        aud: str = None,
        iss: str = "https://accounts.google.com",
        exp_delta: int = 3600,
        sign_key=None,
    ) -> str:
        """Helper to create a cryptographically signed RS256 Google ID token."""
        now = int(time.time())
        payload = {
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
            "name": name,
            "picture": picture,
            "aud": aud or self.test_client_id,
            "iss": iss,
            "iat": now,
            "exp": now + exp_delta,
        }
        key_to_use = sign_key or self.private_key
        return jwt.encode(payload, key_to_use, algorithm="RS256", headers={"kid": "synthetic-kid-1"})

    # =========================================================================
    # 1. AUTHORIZATION URL GENERATION & SCOPES
    # =========================================================================

    def test_01_authorization_url_generation_success(self):
        """Generates valid Google OAuth 2.0 authorization URL."""
        state, _ = self.service.generate_state()
        url = self.service.get_authorization_url(state=state)
        self.assertTrue(url.startswith("https://accounts.google.com/o/oauth2/v2/auth?"))

        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)

        self.assertEqual(params["client_id"][0], self.test_client_id)
        self.assertEqual(params["redirect_uri"][0], self.test_redirect_uri)
        self.assertEqual(params["response_type"][0], "code")
        self.assertEqual(params["state"][0], state)
        self.assertEqual(params["prompt"][0], "select_account")

    def test_02_correct_scopes_present(self):
        """Scopes must contain openid, email, and profile."""
        state, _ = self.service.generate_state()
        url = self.service.get_authorization_url(state=state)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        scopes = params["scope"][0].split()

        self.assertIn("openid", scopes)
        self.assertIn("email", scopes)
        self.assertIn("profile", scopes)

    def test_03_calendar_scopes_strictly_absent(self):
        """Google Calendar, Meet, and offline scopes must NEVER be requested in Stage 6A."""
        state, _ = self.service.generate_state()
        url = self.service.get_authorization_url(state=state)
        url_lower = url.lower()

        self.assertNotIn("calendar", url_lower)
        self.assertNotIn("calendar.events", url_lower)
        self.assertNotIn("meet", url_lower)
        self.assertNotIn("access_type=offline", url_lower)

    def test_04_missing_client_id_raises_configuration_error(self):
        """Missing client_id raises GoogleAuthConfigurationError."""
        bad_service = GoogleAuthService(client_id="", client_secret="secret", redirect_uri="http://uri")
        with self.assertRaises(GoogleAuthConfigurationError):
            bad_service.get_authorization_url(state="dummy-state")

    def test_05_missing_redirect_uri_raises_configuration_error(self):
        """Missing redirect_uri raises GoogleAuthConfigurationError."""
        bad_service = GoogleAuthService(client_id="client", client_secret="secret", redirect_uri="")
        with self.assertRaises(GoogleAuthConfigurationError):
            bad_service.get_authorization_url(state="dummy-state")

    # =========================================================================
    # 2. STATE TOKEN SECURITY & ANTI-CSRF
    # =========================================================================

    def test_06_state_generation_contains_nonce_and_binding(self):
        """State generation produces cryptographically strong signed token and cookie nonce."""
        signed_state, nonce = self.service.generate_state()
        self.assertIsInstance(signed_state, str)
        self.assertIsInstance(nonce, str)
        self.assertGreater(len(nonce), 20)

        # Verification succeeds with matching cookie nonce
        payload = self.service.verify_state(signed_state, nonce)
        self.assertEqual(payload["nonce"], nonce)
        self.assertEqual(payload["redirect"], "/dashboard")

    def test_07_invalid_state_signature_rejected(self):
        """Tampered state token signature is rejected."""
        signed_state, nonce = self.service.generate_state()
        tampered_state = signed_state[:-5] + "XXXXX"
        with self.assertRaises(InvalidStateError):
            self.service.verify_state(tampered_state, nonce)

    def test_08_expired_state_token_rejected(self):
        """Expired state token is rejected with ExpiredStateError."""
        # Create an already expired state token
        now = int(time.time()) - 100
        expired_payload = {
            "nonce": "test-nonce",
            "redirect": "/dashboard",
            "type": "google_oauth_state",
            "iat": now - 600,
            "exp": now,  # expired
        }
        expired_state = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with self.assertRaises(ExpiredStateError):
            self.service.verify_state(expired_state, "test-nonce")

    def test_09_mismatched_cookie_nonce_rejected_anti_csrf(self):
        """Mismatched cookie nonce indicates possible CSRF and is rejected."""
        signed_state, _ = self.service.generate_state()
        attacker_nonce = "attacker-forged-cookie-nonce"
        with self.assertRaises(InvalidStateError) as ctx:
            self.service.verify_state(signed_state, attacker_nonce)
        self.assertIn("mismatch", str(ctx.exception).lower())

    def test_10_missing_state_or_cookie_rejected(self):
        """Missing state or missing cookie is rejected immediately."""
        with self.assertRaises(InvalidStateError):
            self.service.verify_state("", "nonce")
        with self.assertRaises(InvalidStateError):
            self.service.verify_state("state", "")
        with self.assertRaises(InvalidStateError):
            self.service.verify_state(None, None)

    # =========================================================================
    # 3. OPEN REDIRECT PREVENTION
    # =========================================================================

    def test_11_open_redirect_external_urls_sanitized_to_default(self):
        """External absolute URLs must be sanitized to safe default path."""
        dangerous_targets = [
            "https://attacker.com",
            "http://evil.com/phish",
            "//attacker.com",
            "\\\\attacker.com",
            "javascript:alert(1)",
            "ftp://files.com",
        ]
        for target in dangerous_targets:
            sanitized = self.service.sanitize_redirect_url(target)
            self.assertEqual(sanitized, "/dashboard", f"Failed to sanitize: {target}")

    def test_12_safe_internal_relative_redirect_preserved(self):
        """Safe internal relative paths are preserved."""
        safe_targets = [
            "/dashboard",
            "/onboarding",
            "/courses/123",
            "/profile?tab=settings",
            "/",
        ]
        for target in safe_targets:
            sanitized = self.service.sanitize_redirect_url(target)
            self.assertEqual(sanitized, target)

    # =========================================================================
    # 4. AUTHORIZATION CODE EXCHANGE
    # =========================================================================

    def test_13_code_exchange_success(self):
        """Successful authorization code exchange returns tokens payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "mock-google-access-token",
            "id_token": "mock-google-id-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        mock_http = MagicMock()
        mock_http.post.return_value = mock_response

        service = GoogleAuthService(
            client_id=self.test_client_id,
            client_secret=self.test_client_secret,
            redirect_uri=self.test_redirect_uri,
            http_client=mock_http,
        )

        tokens = service.exchange_code("valid-auth-code")
        self.assertEqual(tokens["id_token"], "mock-google-id-token")
        self.assertEqual(tokens["access_token"], "mock-google-access-token")

        # Verify POST payload sent to Google
        mock_http.post.assert_called_once()
        args, kwargs = mock_http.post.call_args
        self.assertEqual(kwargs["data"]["code"], "valid-auth-code")
        self.assertEqual(kwargs["data"]["client_id"], self.test_client_id)
        self.assertEqual(kwargs["data"]["client_secret"], self.test_client_secret)
        self.assertEqual(kwargs["data"]["grant_type"], "authorization_code")

    def test_14_code_exchange_failure_http_error(self):
        """Google token endpoint error raises InvalidCodeError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "invalid_grant", "error_description": "Code expired"}'
        mock_response.json.return_value = {"error": "invalid_grant", "error_description": "Code expired"}

        mock_http = MagicMock()
        mock_http.post.return_value = mock_response

        service = GoogleAuthService(
            client_id=self.test_client_id,
            client_secret=self.test_client_secret,
            redirect_uri=self.test_redirect_uri,
            http_client=mock_http,
        )

        with self.assertRaises(InvalidCodeError) as ctx:
            service.exchange_code("expired-code")
        self.assertIn("Code expired", str(ctx.exception))

    def test_15_code_exchange_missing_id_token_raises_error(self):
        """Response lacking 'id_token' raises GoogleAuthError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "token-only"}

        mock_http = MagicMock()
        mock_http.post.return_value = mock_response

        service = GoogleAuthService(
            client_id=self.test_client_id,
            client_secret=self.test_client_secret,
            redirect_uri=self.test_redirect_uri,
            http_client=mock_http,
        )

        with self.assertRaises(GoogleAuthError):
            service.exchange_code("code-without-id-token")

    def test_16_code_exchange_network_failure(self):
        """Network exception during exchange raises GoogleAuthError."""
        mock_http = MagicMock()
        mock_http.post.side_effect = httpx.ConnectTimeout("Connection timed out")

        service = GoogleAuthService(
            client_id=self.test_client_id,
            client_secret=self.test_client_secret,
            redirect_uri=self.test_redirect_uri,
            http_client=mock_http,
        )

        with self.assertRaises(GoogleAuthError):
            service.exchange_code("code-network-fail")

    # =========================================================================
    # 5. ID TOKEN CRYPTOGRAPHIC VALIDATION
    # =========================================================================

    def test_17_valid_id_token_succeeds(self):
        """Valid RS256 Google ID token correctly validates identity claims."""
        token = self._create_synthetic_id_token(
            sub="user-google-999",
            email="alice@example.com",
            email_verified=True,
            name="Alice",
            picture="https://example.com/alice.jpg",
        )

        identity = self.service.validate_id_token(token, signing_key_override=self.public_pem)
        self.assertEqual(identity.sub, "user-google-999")
        self.assertEqual(identity.email, "alice@example.com")
        self.assertTrue(identity.email_verified)
        self.assertEqual(identity.name, "Alice")
        self.assertEqual(identity.picture, "https://example.com/alice.jpg")

    def test_18_id_token_invalid_signature_rejected(self):
        """ID token signed with wrong RSA private key is rejected."""
        wrong_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        tampered_token = self._create_synthetic_id_token(sign_key=wrong_private_key)

        with self.assertRaises(InvalidIdTokenError) as ctx:
            self.service.validate_id_token(tampered_token, signing_key_override=self.public_pem)
        self.assertIn("signature", str(ctx.exception).lower())

    def test_19_id_token_wrong_audience_rejected(self):
        """ID token with mismatched audience is rejected."""
        token = self._create_synthetic_id_token(aud="completely-different-client-id")
        with self.assertRaises(InvalidIdTokenError) as ctx:
            self.service.validate_id_token(token, signing_key_override=self.public_pem)
        self.assertIn("audience mismatch", str(ctx.exception).lower())

    def test_20_id_token_wrong_issuer_rejected(self):
        """ID token with forged issuer is rejected."""
        token = self._create_synthetic_id_token(iss="https://fake-accounts.evil.com")
        with self.assertRaises(InvalidIdTokenError) as ctx:
            self.service.validate_id_token(token, signing_key_override=self.public_pem)
        self.assertIn("issuer", str(ctx.exception).lower())

    def test_21_id_token_expired_rejected(self):
        """Expired ID token is rejected with ExpiredIdTokenError."""
        token = self._create_synthetic_id_token(exp_delta=-60)
        with self.assertRaises(ExpiredIdTokenError):
            self.service.validate_id_token(token, signing_key_override=self.public_pem)

    def test_22_unverified_email_strictly_rejected(self):
        """Google account where email_verified is False is rejected with UnverifiedEmailError."""
        token = self._create_synthetic_id_token(email="unverified@example.com", email_verified=False)
        with self.assertRaises(UnverifiedEmailError):
            self.service.validate_id_token(token, signing_key_override=self.public_pem)

    def test_23_missing_email_claim_rejected(self):
        """ID token missing email claim is rejected."""
        now = int(time.time())
        payload = {
            "sub": "user-123",
            "aud": self.test_client_id,
            "iss": "https://accounts.google.com",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        with self.assertRaises(InvalidIdTokenError):
            self.service.validate_id_token(token, signing_key_override=self.public_pem)

    def test_24_missing_sub_claim_rejected(self):
        """ID token missing subject claim is rejected."""
        now = int(time.time())
        payload = {
            "email": "user@example.com",
            "email_verified": True,
            "aud": self.test_client_id,
            "iss": "https://accounts.google.com",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        with self.assertRaises(InvalidIdTokenError):
            self.service.validate_id_token(token, signing_key_override=self.public_pem)

    # =========================================================================
    # 6. HTTP ENDPOINT & COOKIE BEHAVIOR
    # =========================================================================

    def test_25_get_google_url_endpoint_sets_httponly_state_cookie(self):
        """GET /api/v1/auth/google/url returns authorization URL and sets HttpOnly state cookie."""
        # Override get_google_auth_service in FastAPI app
        app.dependency_overrides[get_google_auth_service] = lambda: self.service
        try:
            res = self.client.get("/api/v1/auth/google/url?redirect_to=/dashboard")
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertIn("url", data)
            self.assertTrue(data["url"].startswith("https://accounts.google.com"))

            # State cookie present in response
            self.assertIn(settings.GOOGLE_OAUTH_STATE_COOKIE_NAME, res.cookies)
            cookie_val = res.cookies[settings.GOOGLE_OAUTH_STATE_COOKIE_NAME]
            self.assertIsNotNone(cookie_val)

            # State parameter in URL decodes and matches cookie nonce
            parsed = urllib.parse.urlparse(data["url"])
            params = urllib.parse.parse_qs(parsed.query)
            state_in_url = params["state"][0]

            verified_payload = self.service.verify_state(state_in_url, cookie_val)
            self.assertEqual(verified_payload["redirect"], "/dashboard")
        finally:
            app.dependency_overrides.pop(get_google_auth_service, None)

    def test_26_get_google_url_endpoint_never_exposes_secrets(self):
        """Endpoint response never leaks Google client_secret or internal credentials."""
        app.dependency_overrides[get_google_auth_service] = lambda: self.service
        try:
            res = self.client.get("/api/v1/auth/google/url")
            self.assertEqual(res.status_code, 200)
            body_text = res.text.lower()

            self.assertNotIn(self.test_client_secret.lower(), body_text)
            self.assertNotIn("client_secret", body_text)
            self.assertNotIn("secret", body_text)
        finally:
            app.dependency_overrides.pop(get_google_auth_service, None)

    def test_27_get_google_url_endpoint_unconfigured_returns_500(self):
        """Unconfigured Google OAuth returns clean 500 error without stack trace."""
        unconfigured_service = GoogleAuthService(client_id="", client_secret="", redirect_uri="")
        app.dependency_overrides[get_google_auth_service] = lambda: unconfigured_service
        try:
            res = self.client.get("/api/v1/auth/google/url")
            self.assertEqual(res.status_code, 500)
            self.assertIn("Google OAuth is not configured", res.json()["detail"])
        finally:
            app.dependency_overrides.pop(get_google_auth_service, None)


if __name__ == "__main__":
    unittest.main()
