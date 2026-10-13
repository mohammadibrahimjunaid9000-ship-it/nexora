"""
Comprehensive Unit Tests for Phase 4 — Stage 6B: Google OAuth Account Resolution & Callback Implementation
Tests:
- Callback endpoint GET /api/v1/auth/google/callback
- State verification, cookie binding, anti-CSRF, and cookie deletion on consumption
- Authorization code exchange handling (errors, timeouts, missing parameters)
- Identity verification (RS256, audience, issuer, expiration, unverified email)
- Account resolution: existing users (learner, creator, admin) with role/points/password preservation
- Account creation: new Google users with password=None, role=None, points=0, normalized email
- Concurrent account creation race condition handling
- Nexora HttpOnly access cookie issuance and frontend redirection
- Security invariants: zero secret leakage, no Google tokens in Nexora JWT, open redirect prevention
- Complete database and network isolation using mocks and synthetic RSA key pairs.
"""

import time
import unittest
import urllib.parse
from typing import Any, Dict, Optional, Union
from unittest.mock import MagicMock, patch

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from api.app.auth.security import decode_access_token
from api.app.config import settings
from api.app.main import app
from api.app.services.google_auth import (
    GoogleAuthService,
    get_google_auth_service,
)
from api.app.services.users import UserService, get_user_service


class MockUserServiceStage6B:
    """In-memory mock user service supporting Stage 6B account resolution tests."""

    def __init__(self):
        self.users: Dict[Union[int, str], Dict[str, Any]] = {}
        self.next_id = 1
        self.simulate_lookup_failure = False
        self.simulate_insert_failure = False
        self.simulate_race_condition = False

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
            "joined_at": "2026-10-13T00:00:00Z"
        }
        self.users[uid] = record
        return dict(record)

    def get_by_id(self, user_id: Union[int, str], include_password: bool = False) -> Optional[Dict[str, Any]]:
        if self.simulate_lookup_failure:
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
        if self.simulate_lookup_failure:
            raise RuntimeError("PostgREST connection pool timeout")

        clean_email = email.strip().lower()
        for u in self.users.values():
            if u["email"].lower() == clean_email:
                res = dict(u)
                if not include_password:
                    res.pop("password", None)
                return res
        return None

    def resolve_google_account(self, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Simulates atomic resolution of Google user with race condition handling."""
        if self.simulate_lookup_failure:
            raise RuntimeError("PostgREST database connection timeout during user lookup")

        clean_email = email.strip().lower()

        # Check existing
        existing = self.get_by_email(clean_email)
        if existing:
            return existing

        if self.simulate_insert_failure:
            raise RuntimeError("Database disk full during user insert")

        # Simulate concurrent race: another thread created the user right before this insert
        if self.simulate_race_condition:
            self.simulate_race_condition = False  # race happens once
            # Simulate another worker inserting
            created_by_worker = self.add_user(
                name=name or "Concurrent Worker User",
                email=clean_email,
                password_hash=None,
                role=None,
                points=0
            )
            # Re-query existing
            res = dict(created_by_worker)
            res.pop("password", None)
            return res

        # Insert new
        clean_name = (name or "").strip()
        if not clean_name:
            clean_name = clean_email.split("@")[0].replace(".", " ").title() or "Nexora User"

        new_user = self.add_user(
            name=clean_name[:150],
            email=clean_email,
            password_hash=None,
            role=None,
            points=0
        )
        safe = dict(new_user)
        safe.pop("password", None)
        return safe


class TestGoogleAuthStage6B(unittest.TestCase):
    """Test suite for Stage 6B: Google OAuth Account Resolution & Callback Implementation."""

    @classmethod
    def setUpClass(cls):
        # Generate test RSA 2048-bit key pair for synthetic Google ID tokens
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()
        cls.public_pem = cls.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        cls.test_client_id = "test-nexora-google-client-id.apps.googleusercontent.com"
        cls.test_client_secret = "test-nexora-google-client-secret"
        cls.test_redirect_uri = "http://127.0.0.1:8000/api/v1/auth/google/callback"

    def setUp(self):
        self.mock_user_service = MockUserServiceStage6B()
        self.mock_google_service = GoogleAuthService(
            client_id=self.test_client_id,
            client_secret=self.test_client_secret,
            redirect_uri=self.test_redirect_uri,
        )

        # Prepopulate users in mock service
        self.existing_password_user = self.mock_user_service.add_user(
            name="Bob Learner",
            email="bob.password@example.com",
            password_hash="$2b$12$syntheticExistingBcryptHashForBob123",
            role="learner",
            points=150
        )

        self.existing_creator_user = self.mock_user_service.add_user(
            name="Carol Creator",
            email="carol.creator@example.com",
            password_hash="$2b$12$syntheticExistingBcryptHashForCarol456",
            role="creator",
            points=300
        )

        self.existing_admin_user = self.mock_user_service.add_user(
            name="Dave Admin",
            email="dave.admin@example.com",
            password_hash="$2b$12$syntheticExistingBcryptHashForDave789",
            role="admin",
            points=500
        )

        self.existing_google_only_user = self.mock_user_service.add_user(
            name="Eve GoogleOnly",
            email="eve.google@example.com",
            password_hash=None,
            role="learner",
            points=50
        )

        # Wire dependency overrides
        app.dependency_overrides[get_user_service] = lambda: self.mock_user_service
        app.dependency_overrides[get_google_auth_service] = lambda: self.mock_google_service
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

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

    def _setup_mock_code_exchange(self, id_token: str, access_token: str = "mock-google-access-token"):
        """Patches exchange_code and validate_id_token to use synthetic credentials."""
        self.mock_google_service.exchange_code = MagicMock(return_value={
            "id_token": id_token,
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600
        })
        # Use synthetic RSA public key to validate ID token
        real_validate = self.mock_google_service.validate_id_token
        self.mock_google_service.validate_id_token = lambda tok: real_validate(tok, signing_key_override=self.public_pem)

    # =========================================================================
    # 1. CALLBACK: EXISTING USER LOGIN & INVARIANTS
    # =========================================================================

    def test_01_existing_user_login_success_preserves_role_and_points(self):
        """Existing learner logs in via Google: preserves id, role='learner', points, and joined_at."""
        id_token = self._create_synthetic_id_token(
            sub="sub-bob",
            email=self.existing_password_user["email"],
            name="Bob Updated Google Name"
        )
        self._setup_mock_code_exchange(id_token)

        state, nonce = self.mock_google_service.generate_state(redirect_target="/dashboard")
        cookies = {settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}

        res = self.client.get(
            f"/api/v1/auth/google/callback?code=mock-valid-code&state={state}",
            cookies=cookies,
            follow_redirects=False
        )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers["location"], f"{settings.FRONTEND_URL}/dashboard")

        # Session cookie issued
        self.assertIn(settings.AUTH_COOKIE_NAME, res.cookies)
        token = res.cookies[settings.AUTH_COOKIE_NAME]
        claims = decode_access_token(token)
        self.assertEqual(claims["sub"], str(self.existing_password_user["id"]))
        self.assertEqual(claims["email"], self.existing_password_user["email"])
        self.assertEqual(claims["role"], "learner")

        # State cookie deleted
        self.assertIn(res.cookies.get(settings.GOOGLE_OAUTH_STATE_COOKIE_NAME), [None, ""])
        self.assertIn(f'{settings.GOOGLE_OAUTH_STATE_COOKIE_NAME}=""', res.headers.get("set-cookie", ""))

        # Verify DB user is completely preserved
        db_user = self.mock_user_service.get_by_id(self.existing_password_user["id"], include_password=True)
        self.assertEqual(db_user["password"], self.existing_password_user["password"])
        self.assertEqual(db_user["role"], "learner")
        self.assertEqual(db_user["points"], 150)

    def test_02_existing_creator_preserves_creator_role(self):
        """Existing creator logs in via Google: role remains 'creator'."""
        id_token = self._create_synthetic_id_token(
            sub="sub-carol",
            email=self.existing_creator_user["email"]
        )
        self._setup_mock_code_exchange(id_token)

        state, nonce = self.mock_google_service.generate_state(redirect_target="/dashboard")
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=valid-code&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )

        self.assertEqual(res.status_code, 302)
        token = res.cookies[settings.AUTH_COOKIE_NAME]
        claims = decode_access_token(token)
        self.assertEqual(claims["role"], "creator")

    def test_03_existing_admin_preserves_admin_role(self):
        """Existing admin logs in via Google: role remains 'admin' without tampering."""
        id_token = self._create_synthetic_id_token(
            sub="sub-dave",
            email=self.existing_admin_user["email"]
        )
        self._setup_mock_code_exchange(id_token)

        state, nonce = self.mock_google_service.generate_state(redirect_target="/dashboard")
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=valid-code&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )

        self.assertEqual(res.status_code, 302)
        token = res.cookies[settings.AUTH_COOKIE_NAME]
        claims = decode_access_token(token)
        self.assertEqual(claims["role"], "admin")

    def test_04_existing_password_account_preserves_password_hash(self):
        """Existing password account logging in with Google does not erase or modify password hash."""
        id_token = self._create_synthetic_id_token(
            email=self.existing_password_user["email"]
        )
        self._setup_mock_code_exchange(id_token)

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-123&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )
        self.assertEqual(res.status_code, 302)

        db_user = self.mock_user_service.get_by_id(self.existing_password_user["id"], include_password=True)
        self.assertIsNotNone(db_user["password"])
        self.assertEqual(db_user["password"], self.existing_password_user["password"])

    def test_05_existing_google_only_account_preserves_null_password(self):
        """Existing Google-only account logging in retains password=None."""
        id_token = self._create_synthetic_id_token(
            email=self.existing_google_only_user["email"]
        )
        self._setup_mock_code_exchange(id_token)

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-123&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )
        self.assertEqual(res.status_code, 302)

        db_user = self.mock_user_service.get_by_id(self.existing_google_only_user["id"], include_password=True)
        self.assertIsNone(db_user["password"])
        self.assertEqual(db_user["role"], "learner")

    # =========================================================================
    # 2. CALLBACK: NEW USER REGISTRATION
    # =========================================================================

    def test_06_new_google_user_creation_invariants(self):
        """New Google user is created with: name, normalized email, password=None, role=None, points=0."""
        new_email = "  NEWBIE.Student@Example.COM  "
        id_token = self._create_synthetic_id_token(
            sub="sub-newbie-999",
            email=new_email,
            name="Newbie Student"
        )
        self._setup_mock_code_exchange(id_token)

        state, nonce = self.mock_google_service.generate_state(redirect_target="/onboarding")
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-newbie&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers["location"], f"{settings.FRONTEND_URL}/onboarding")

        # Session token contains role=None
        token = res.cookies[settings.AUTH_COOKIE_NAME]
        claims = decode_access_token(token)
        self.assertEqual(claims["email"], "newbie.student@example.com")
        self.assertIsNone(claims["role"])

        # Check DB record
        db_user = self.mock_user_service.get_by_email("newbie.student@example.com", include_password=True)
        self.assertIsNotNone(db_user)
        self.assertEqual(db_user["name"], "Newbie Student")
        self.assertEqual(db_user["email"], "newbie.student@example.com")
        self.assertIsNone(db_user["password"])
        self.assertIsNone(db_user["role"])
        self.assertEqual(db_user["points"], 0)

    def test_07_new_google_user_fallback_name_when_missing(self):
        """When Google profile lacks display name, falls back safely to email local part."""
        id_token = self._create_synthetic_id_token(
            email="sam.smith@example.com",
            name=""
        )
        self._setup_mock_code_exchange(id_token)

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-sam&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )
        self.assertEqual(res.status_code, 302)

        db_user = self.mock_user_service.get_by_email("sam.smith@example.com")
        self.assertIsNotNone(db_user)
        self.assertEqual(db_user["name"], "Sam Smith")

    # =========================================================================
    # 3. STATE SECURITY & REPLAY PROTECTION
    # =========================================================================

    def test_08_missing_state_parameter_rejected(self):
        """Callback missing 'state' parameter returns 400."""
        res = self.client.get("/api/v1/auth/google/callback?code=valid-code")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Missing OAuth state parameter", res.json()["detail"])

    def test_09_missing_state_cookie_rejected(self):
        """Callback with state parameter but missing state cookie returns 400."""
        state, _ = self.mock_google_service.generate_state()
        res = self.client.get(f"/api/v1/auth/google/callback?code=valid-code&state={state}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Missing OAuth state cookie", res.json()["detail"])

    def test_10_invalid_state_signature_rejected(self):
        """Tampered state token returns 400."""
        state, nonce = self.mock_google_service.generate_state()
        tampered_state = state[:-5] + "XXXXX"
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=valid-code&state={tampered_state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid OAuth state", res.json()["detail"])

    def test_11_expired_state_token_rejected(self):
        """Expired state token returns 400."""
        now = int(time.time()) - 200
        expired_payload = {
            "nonce": "test-nonce",
            "redirect": "/dashboard",
            "type": "google_oauth_state",
            "iat": now - 600,
            "exp": now,
        }
        expired_state = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=valid-code&state={expired_state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: "test-nonce"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("OAuth state has expired", res.json()["detail"])

    def test_12_state_cookie_mismatch_rejected(self):
        """State nonce mismatching cookie nonce returns 400 (Anti-CSRF)."""
        state, _ = self.mock_google_service.generate_state()
        attacker_nonce = "attacker-cookie-nonce"
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=valid-code&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: attacker_nonce}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("session mismatch", res.json()["detail"].lower())

    def test_13_successful_callback_deletes_oauth_state_cookie(self):
        """Successful callback response explicitly deletes nexora_oauth_state cookie."""
        id_token = self._create_synthetic_id_token()
        self._setup_mock_code_exchange(id_token)

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=valid-code&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )

        self.assertEqual(res.status_code, 302)
        # Verify state cookie deletion in Set-Cookie header
        set_cookie_header = res.headers.get("set-cookie", "")
        self.assertIn(f'{settings.GOOGLE_OAUTH_STATE_COOKIE_NAME}=""', set_cookie_header)
        self.assertIn("Max-Age=0", set_cookie_header)
        self.assertIn(res.cookies.get(settings.GOOGLE_OAUTH_STATE_COOKIE_NAME), [None, ""])

    # =========================================================================
    # 4. CODE & EXCHANGE ERROR HANDLING
    # =========================================================================

    def test_14_missing_code_parameter_rejected(self):
        """Callback missing 'code' parameter returns 400."""
        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Missing authorization code", res.json()["detail"])

    def test_15_google_oauth_error_parameter_rejected(self):
        """Google reporting error parameter (e.g. access_denied) returns 400."""
        res = self.client.get("/api/v1/auth/google/callback?error=access_denied")
        self.assertEqual(res.status_code, 400)
        self.assertIn("access_denied", res.json()["detail"])

    def test_16_invalid_or_expired_code_exchange_returns_400(self):
        """Failed code exchange with Google token endpoint returns 400."""
        state, nonce = self.mock_google_service.generate_state()

        # Simulate Google rejecting code
        mock_http = MagicMock()
        mock_res = MagicMock()
        mock_res.status_code = 400
        mock_res.text = '{"error": "invalid_grant", "error_description": "Code expired"}'
        mock_res.json.return_value = {"error": "invalid_grant", "error_description": "Code expired"}
        mock_http.post.return_value = mock_res
        self.mock_google_service._http_client = mock_http

        res = self.client.get(
            f"/api/v1/auth/google/callback?code=bad-code&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid or expired authorization code", res.json()["detail"])

    def test_17_google_server_timeout_returns_502(self):
        """Network timeout communicating with Google returns 502 Bad Gateway."""
        state, nonce = self.mock_google_service.generate_state()

        mock_http = MagicMock()
        mock_http.post.side_effect = httpx.ConnectTimeout("Google server unreachable")
        self.mock_google_service._http_client = mock_http

        res = self.client.get(
            f"/api/v1/auth/google/callback?code=timeout-code&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 502)
        self.assertIn("Failed to communicate with Google authentication server", res.json()["detail"])

    # =========================================================================
    # 5. IDENTITY VERIFICATION FAILURES
    # =========================================================================

    def test_18_id_token_invalid_signature_rejected(self):
        """ID token signed with untrusted RSA key returns 400."""
        untrusted_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        tampered_token = self._create_synthetic_id_token(sign_key=untrusted_key)
        self._setup_mock_code_exchange(tampered_token)

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-1&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("validation failed", res.json()["detail"].lower())

    def test_19_id_token_audience_mismatch_rejected(self):
        """ID token with wrong audience returns 400."""
        token = self._create_synthetic_id_token(aud="attacker-fake-client-id")
        self._setup_mock_code_exchange(token)

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-1&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("validation failed", res.json()["detail"].lower())

    def test_20_id_token_issuer_mismatch_rejected(self):
        """ID token with wrong issuer returns 400."""
        token = self._create_synthetic_id_token(iss="https://evil-issuer.com")
        self._setup_mock_code_exchange(token)

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-1&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("validation failed", res.json()["detail"].lower())

    def test_21_id_token_expired_rejected(self):
        """Expired Google ID token returns 400."""
        token = self._create_synthetic_id_token(exp_delta=-100)
        self._setup_mock_code_exchange(token)

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-1&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Google ID token has expired", res.json()["detail"])

    def test_22_unverified_email_strictly_rejected(self):
        """Google account where email_verified is False is rejected with 400."""
        token = self._create_synthetic_id_token(email="unverified@example.com", email_verified=False)
        self._setup_mock_code_exchange(token)

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-1&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Google account email is not verified", res.json()["detail"])

    # =========================================================================
    # 6. DATABASE CONCURRENCY & RESILIENCE
    # =========================================================================

    def test_23_concurrent_signup_race_condition_handled(self):
        """Simultaneous signup race condition resolves transparently without failure."""
        id_token = self._create_synthetic_id_token(
            email="race.condition@example.com",
            name="Race User"
        )
        self._setup_mock_code_exchange(id_token)

        self.mock_user_service.simulate_race_condition = True

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-race&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )

        self.assertEqual(res.status_code, 302)
        token = res.cookies[settings.AUTH_COOKIE_NAME]
        claims = decode_access_token(token)
        self.assertEqual(claims["email"], "race.condition@example.com")

    def test_24_database_failure_returns_503(self):
        """Database lookup or insert failure returns clean 503."""
        id_token = self._create_synthetic_id_token()
        self._setup_mock_code_exchange(id_token)

        self.mock_user_service.simulate_lookup_failure = True

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-1&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce}
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("Database service is currently unavailable", res.json()["detail"])

    # =========================================================================
    # 7. SECURITY & SECRETS ISOLATION
    # =========================================================================

    def test_25_no_google_tokens_or_secrets_in_cookie_or_jwt(self):
        """Nexora access token cookie strictly contains Nexora claims; zero Google tokens or secrets."""
        id_token = self._create_synthetic_id_token()
        self._setup_mock_code_exchange(id_token, access_token="super-secret-google-access-token-12345")

        state, nonce = self.mock_google_service.generate_state()
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-1&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )

        token = res.cookies[settings.AUTH_COOKIE_NAME]
        claims = decode_access_token(token)

        self.assertNotIn("access_token", claims)
        self.assertNotIn("id_token", claims)
        self.assertNotIn("refresh_token", claims)
        self.assertNotIn("google", claims)
        self.assertNotIn(self.test_client_secret, str(claims))

    def test_26_open_redirect_sanitized_to_safe_target(self):
        """Malicious redirect target in state is sanitized to /dashboard."""
        id_token = self._create_synthetic_id_token()
        self._setup_mock_code_exchange(id_token)

        state, nonce = self.mock_google_service.generate_state(redirect_target="https://attacker.com/evil")
        res = self.client.get(
            f"/api/v1/auth/google/callback?code=code-1&state={state}",
            cookies={settings.GOOGLE_OAUTH_STATE_COOKIE_NAME: nonce},
            follow_redirects=False
        )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers["location"], f"{settings.FRONTEND_URL}/dashboard")


if __name__ == "__main__":
    unittest.main()
