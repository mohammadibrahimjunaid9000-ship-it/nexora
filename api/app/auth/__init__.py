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
from api.app.auth.schemas import (
    UserRole,
    UserResponse,
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    CurrentUserResponse,
    MessageResponse,
)
from api.app.auth.dependencies import (
    get_current_user,
    RoleChecker,
    require_learner,
    require_creator,
    require_admin,
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
    "UserRole",
    "UserResponse",
    "RegisterRequest",
    "LoginRequest",
    "AuthResponse",
    "CurrentUserResponse",
    "MessageResponse",
    "get_current_user",
    "RoleChecker",
    "require_learner",
    "require_creator",
    "require_admin",
]
