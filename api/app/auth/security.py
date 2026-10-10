"""
Nexora API - Backend Security Module
Provides cryptographic primitives for bcrypt password hashing, PyJWT creation & verification,
and HttpOnly authentication cookie configuration.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Union
import logging
import bcrypt
import jwt
from fastapi import Request, Response
from api.app.config import settings

logger = logging.getLogger("nexora.api.security")

# Cost factor for bcrypt password hashing
BCRYPT_ROUNDS = 12


# ─── Security Exceptions ───────────────────────────────────────────────────────

class AuthError(Exception):
    """Base exception for authentication errors."""
    pass


class InvalidTokenError(AuthError):
    """Raised when an authentication token is malformed, has invalid claims, or fails signature verification."""
    pass


class ExpiredTokenError(AuthError):
    """Raised when an authentication token has expired."""
    pass


# ─── Password Security (Bcrypt) ────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using bcrypt with a cost factor of 12.
    Never stores or logs plaintext passwords.
    """
    if not password or not isinstance(password, str):
        raise ValueError("Password must be a non-empty string.")

    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifies a plaintext password against a bcrypt password hash.
    Fails safely without raising exceptions or leaking timing/details.
    """
    if not password or not password_hash or not isinstance(password, str) or not isinstance(password_hash, str):
        return False

    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ─── JWT Security (PyJWT) ──────────────────────────────────────────────────────

def create_access_token(
    user_id: Union[int, str],
    email: str,
    role: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Creates a signed JWT access token.
    Payload contains only non-sensitive standard claims (sub, email, role, iat, exp, type).
    Never includes passwords, credentials, or private keys.
    """
    if not user_id:
        raise ValueError("user_id is required to create an access token.")
    if not email or not isinstance(email, str):
        raise ValueError("email is required to create an access token.")

    now = datetime.now(timezone.utc)
    delta = expires_delta if expires_delta is not None else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + delta

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access"
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and verifies a JWT access token.
    Enforces signature validation, algorithm check, and expiration check.
    Fails safely with custom exceptions without leaking internal PyJWT details.
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Authentication token is required.")

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": True}
        )
    except jwt.ExpiredSignatureError:
        raise ExpiredTokenError("Authentication token has expired.")
    except (jwt.InvalidTokenError, jwt.PyJWTError, Exception) as exc:
        logger.debug(f"JWT decode failure: {type(exc).__name__}")
        raise InvalidTokenError("Invalid authentication token.")

    if not payload.get("sub"):
        raise InvalidTokenError("Token missing subject identifier.")

    return payload


# ─── HttpOnly Auth Cookie Helpers ─────────────────────────────────────────────

def get_auth_cookie_config() -> Dict[str, Any]:
    """
    Returns the secure cookie configuration dictionary.
    Always specifies HttpOnly=True and an explicit path.
    """
    return {
        "key": settings.AUTH_COOKIE_NAME,
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE.lower(),
        "path": settings.AUTH_COOKIE_PATH,
        "max_age": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def set_auth_cookie(response: Response, token: str) -> None:
    """
    Attaches the authentication token inside an HttpOnly cookie on the HTTP response.
    Inaccessible to frontend JavaScript.
    """
    config = get_auth_cookie_config()
    response.set_cookie(
        key=config["key"],
        value=token,
        max_age=config["max_age"],
        httponly=config["httponly"],
        secure=config["secure"],
        samesite=config["samesite"],
        path=config["path"],
    )


def delete_auth_cookie(response: Response) -> None:
    """
    Clears the authentication cookie from the client by setting an expired cookie.
    """
    config = get_auth_cookie_config()
    response.delete_cookie(
        key=config["key"],
        path=config["path"],
        samesite=config["samesite"],
        secure=config["secure"],
        httponly=config["httponly"],
    )


def get_token_from_request(request: Request) -> Optional[str]:
    """
    Extracts the authentication token strictly from the HttpOnly cookie.
    Does not read from localStorage or JavaScript-accessible mechanisms.
    """
    return request.cookies.get(settings.AUTH_COOKIE_NAME)
