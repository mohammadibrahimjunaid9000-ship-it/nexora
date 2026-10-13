"""
Nexora API - Google OAuth & Identity Validation Service
Handles:
- OpenID Connect (OIDC) Google Sign-In authorization URL generation
- Cryptographically secure anti-CSRF state token generation and verification
- Google authorization code exchange for tokens via HTTP
- Full cryptographic validation of Google ID tokens (RS256, JWKS, aud, iss, exp, email_verified)
- Safe internal redirect URI sanitization
"""

import hmac
import logging
import re
import secrets
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple, Union

import httpx
import jwt
from jwt import PyJWKClient

from api.app.auth.schemas import GoogleIdentity
from api.app.config import settings

logger = logging.getLogger("nexora.api.google_auth")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

ALLOWED_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]
ALLOWED_SCOPES = "openid email profile"


# ─── Custom Exceptions ────────────────────────────────────────────────────────

class GoogleAuthError(Exception):
    """Base exception for Google OAuth errors."""
    pass


class GoogleAuthConfigurationError(GoogleAuthError):
    """Raised when required Google OAuth configuration is missing."""
    pass


class InvalidStateError(GoogleAuthError):
    """Raised when OAuth state is invalid, missing, or mismatched."""
    pass


class ExpiredStateError(InvalidStateError):
    """Raised when OAuth state token has expired."""
    pass


class InvalidCodeError(GoogleAuthError):
    """Raised when authorization code exchange fails."""
    pass


class InvalidIdTokenError(GoogleAuthError):
    """Raised when Google ID token validation fails."""
    pass


class ExpiredIdTokenError(InvalidIdTokenError):
    """Raised when Google ID token has expired."""
    pass


class UnverifiedEmailError(GoogleAuthError):
    """Raised when Google account email is not verified."""
    pass


# ─── GoogleAuthService ────────────────────────────────────────────────────────

class GoogleAuthService:
    """
    Encapsulates Google OAuth 2.0 / OpenID Connect identity operations.
    Validates identity claims without storing Google tokens or touching database.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        jwks_client: Optional[PyJWKClient] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.client_id = client_id if client_id is not None else settings.GOOGLE_CLIENT_ID
        self.client_secret = client_secret if client_secret is not None else settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = redirect_uri if redirect_uri is not None else settings.GOOGLE_REDIRECT_URI
        self._jwks_client = jwks_client
        self._http_client = http_client

    # ─── Redirect Sanitization ────────────────────────────────────────────────

    def sanitize_redirect_url(self, target: Optional[str]) -> str:
        """
        Sanitizes and enforces internal relative paths for post-auth redirection.
        Strictly prevents open redirect attacks.
        """
        default_target = "/dashboard"
        if not target or not isinstance(target, str):
            return default_target

        target = target.strip()
        # Reject external protocols (http://, https://, ftp://), scheme-relative (//), and backslashes (\)
        if re.search(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//") or "\\" in target:
            logger.warning(f"Rejected open redirect attempt with external target: {target}")
            return default_target

        # Reject path traversal (e.g., /dashboard/../admin)
        if "/.." in target or "..\\" in target or target.startswith(".."):
            logger.warning(f"Rejected path traversal in redirect target: {target}")
            return default_target

        # Verify path against safe characters (letters, numbers, /, -, _, ., ?, =, &)
        if not re.match(r"^/[a-zA-Z0-9_\-./?=&]*$", target):
            logger.warning(f"Rejected unsafe characters in redirect target: {target}")
            return default_target

        return target

    # ─── State Generation & Verification (Anti-CSRF) ──────────────────────────

    def generate_state(self, redirect_target: Optional[str] = None) -> Tuple[str, str]:
        """
        Generates a cryptographically strong signed OAuth state parameter and binding nonce.
        Returns:
            Tuple[signed_state_token, state_nonce]
        The state_nonce must be placed in a short-lived HttpOnly cookie;
        the signed_state_token is transmitted in the Google authorization URL.
        """
        nonce = secrets.token_urlsafe(32)
        safe_redirect = self.sanitize_redirect_url(redirect_target)
        now = int(time.time())
        expires = now + (settings.GOOGLE_OAUTH_STATE_EXPIRE_MINUTES * 60)

        payload = {
            "nonce": nonce,
            "redirect": safe_redirect,
            "type": "google_oauth_state",
            "iat": now,
            "exp": expires,
        }

        signed_state = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return signed_state, nonce

    def verify_state(self, state: Optional[str], cookie_nonce: Optional[str]) -> Dict[str, Any]:
        """
        Verifies the OAuth state token against the HttpOnly cookie nonce (double-submit / cookie-binding).
        Validates signature, expiration, and ensures payload nonce matches cookie nonce.
        """
        if not state or not isinstance(state, str) or not state.strip():
            raise InvalidStateError("Missing OAuth state parameter.")

        if not cookie_nonce or not isinstance(cookie_nonce, str) or not cookie_nonce.strip():
            raise InvalidStateError("Missing OAuth state cookie.")

        try:
            payload = jwt.decode(
                state.strip(),
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"require": ["nonce", "exp", "type"]}
            )
        except jwt.ExpiredSignatureError:
            raise ExpiredStateError("OAuth state has expired. Please initiate sign-in again.")
        except jwt.PyJWTError as e:
            raise InvalidStateError(f"Invalid OAuth state signature: {e}")

        if payload.get("type") != "google_oauth_state":
            raise InvalidStateError("Invalid state token type.")

        expected_nonce = payload.get("nonce", "")
        if not hmac.compare_digest(expected_nonce, cookie_nonce.strip()):
            logger.warning("OAuth state cookie binding mismatch - possible CSRF attack.")
            raise InvalidStateError("OAuth state mismatch. Session verification failed.")

        return payload

    # ─── Authorization URL Generation ─────────────────────────────────────────

    def get_authorization_url(self, state: str) -> str:
        """
        Builds the Google OAuth 2.0 authorization URL.
        Scopes are strictly limited to 'openid email profile'.
        Never requests calendar, meet, or offline access.
        """
        if not self.client_id or self.client_id.strip() == "your_google_client_id_here":
            raise GoogleAuthConfigurationError("Google OAuth client ID is not configured.")

        if not self.redirect_uri:
            raise GoogleAuthConfigurationError("Google OAuth redirect URI is not configured.")

        if not state or not state.strip():
            raise InvalidStateError("OAuth state is required to generate authorization URL.")

        params = {
            "client_id": self.client_id.strip(),
            "redirect_uri": self.redirect_uri.strip(),
            "response_type": "code",
            "scope": ALLOWED_SCOPES,
            "state": state.strip(),
            "prompt": "select_account",
        }

        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    # ─── Code Exchange ────────────────────────────────────────────────────────

    def exchange_code(self, code: str) -> Dict[str, Any]:
        """
        Exchanges the authorization code for Google tokens.
        Makes HTTP POST to https://oauth2.googleapis.com/token.
        """
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise GoogleAuthConfigurationError("Google OAuth credentials are not fully configured.")

        if not code or not isinstance(code, str) or not code.strip():
            raise InvalidCodeError("Authorization code is required.")

        data = {
            "code": code.strip(),
            "client_id": self.client_id.strip(),
            "client_secret": self.client_secret.strip(),
            "redirect_uri": self.redirect_uri.strip(),
            "grant_type": "authorization_code",
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        try:
            if self._http_client:
                res = self._http_client.post(GOOGLE_TOKEN_URL, data=data, headers=headers)
            else:
                with httpx.Client(timeout=10.0) as client:
                    res = client.post(GOOGLE_TOKEN_URL, data=data, headers=headers)

            if res.status_code != 200:
                logger.error(f"Google token exchange HTTP {res.status_code}: {res.text}")
                try:
                    err_json = res.json()
                    err_desc = err_json.get("error_description") or err_json.get("error") or res.text
                except Exception:
                    err_desc = res.text
                raise InvalidCodeError(f"Google authorization code exchange failed: {err_desc}")

            tokens = res.json()
            if not tokens.get("id_token"):
                raise GoogleAuthError("Google token response missing 'id_token'.")

            return tokens

        except (InvalidCodeError, GoogleAuthError):
            raise
        except Exception as e:
            logger.error(f"Network error during Google token exchange: {type(e).__name__}")
            raise GoogleAuthError(f"Failed to communicate with Google authentication server: {e}")

    # ─── ID Token Cryptographic Validation ────────────────────────────────────

    def validate_id_token(
        self,
        id_token: str,
        signing_key_override: Optional[Any] = None,
    ) -> GoogleIdentity:
        """
        Cryptographically validates a Google OpenID Connect ID token.
        Verifies:
        - RS256 signature against Google JWKS (or injected test key)
        - Issuer is https://accounts.google.com or accounts.google.com
        - Audience matches GOOGLE_CLIENT_ID
        - Expiration (token not expired)
        - Required claims ('sub', 'email', 'email_verified')
        - Email address is verified (email_verified is True)
        """
        if not id_token or not isinstance(id_token, str) or not id_token.strip():
            raise InvalidIdTokenError("Google ID token is required.")

        if not self.client_id:
            raise GoogleAuthConfigurationError("Google OAuth client ID is not configured for validation.")

        # Determine signing key
        if signing_key_override is not None:
            key = signing_key_override
        else:
            try:
                jwks = self._jwks_client or PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True)
                signing_key = jwks.get_signing_key_from_jwt(id_token)
                key = signing_key.key
            except Exception as e:
                logger.error(f"Failed to obtain Google JWKS signing key: {e}")
                raise InvalidIdTokenError(f"Failed to resolve Google JWKS key: {e}")

        # Decode and verify token
        try:
            payload = jwt.decode(
                id_token.strip(),
                key,
                algorithms=["RS256"],
                audience=self.client_id.strip(),
                issuer=ALLOWED_ISSUERS,
                options={
                    "require": ["sub", "email", "exp", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                }
            )
        except jwt.ExpiredSignatureError:
            raise ExpiredIdTokenError("Google ID token has expired.")
        except jwt.InvalidAudienceError:
            raise InvalidIdTokenError(f"Google ID token audience mismatch (expected {self.client_id}).")
        except jwt.InvalidIssuerError:
            raise InvalidIdTokenError("Google ID token has an invalid issuer.")
        except jwt.PyJWTError as e:
            raise InvalidIdTokenError(f"Google ID token signature verification failed: {e}")

        # Validate subject
        sub = str(payload.get("sub", "")).strip()
        if not sub:
            raise InvalidIdTokenError("Google ID token missing 'sub' subject claim.")

        # Validate email
        email = payload.get("email")
        if not email or not isinstance(email, str) or "@" not in email:
            raise InvalidIdTokenError("Google ID token missing valid 'email' claim.")

        # Strict verified email validation
        email_verified = payload.get("email_verified")
        if email_verified is not True:
            logger.warning(f"Rejected Google login for unverified email: {email}")
            raise UnverifiedEmailError("Google account email is not verified.")

        return GoogleIdentity(
            sub=sub,
            email=email.strip().lower(),
            email_verified=True,
            name=payload.get("name"),
            picture=payload.get("picture"),
        )


# ─── Dependency Provider / Singleton Accessor ─────────────────────────────────

_google_auth_service_instance: Optional[GoogleAuthService] = None


def get_google_auth_service() -> GoogleAuthService:
    """Dependency provider / singleton accessor for GoogleAuthService."""
    global _google_auth_service_instance
    if _google_auth_service_instance is None:
        _google_auth_service_instance = GoogleAuthService()
    return _google_auth_service_instance
