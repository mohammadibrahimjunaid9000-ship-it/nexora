"""
Nexora API - Authentication Package
Stage 1: Backend Security Foundation
"""

from api.app.auth.security import (
    hash_password,
    verify_password,
    verify_and_maybe_migrate_password,
    create_access_token,
    decode_access_token,
    get_auth_cookie_config,
    set_auth_cookie,
    delete_auth_cookie,
    get_token_from_request,
    AuthError,
    InvalidTokenError,
    ExpiredTokenError,
    BCRYPT_ROUNDS,
)

__all__ = [
    "hash_password",
    "verify_password",
    "verify_and_maybe_migrate_password",
    "create_access_token",
    "decode_access_token",
    "get_auth_cookie_config",
    "set_auth_cookie",
    "delete_auth_cookie",
    "get_token_from_request",
    "AuthError",
    "InvalidTokenError",
    "ExpiredTokenError",
    "BCRYPT_ROUNDS",
]
