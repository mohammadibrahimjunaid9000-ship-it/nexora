"""
Nexora API - Authentication Endpoints
Provides registration, login, logout, and current user retrieval.
Uses HttpOnly cookie-based JWT authentication and connects strictly to the existing Supabase users table.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.app.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    CurrentUserResponse,
    MessageResponse,
    UserResponse,
)
from api.app.auth.security import (
    hash_password,
    verify_and_maybe_migrate_password,
    create_access_token,
    set_auth_cookie,
    delete_auth_cookie,
)
from api.app.auth.dependencies import get_current_user
from api.app.services.users import get_user_service, UserService

logger = logging.getLogger("nexora.api.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthResponse,
    summary="Register a new user account"
)
def register(
    payload: RegisterRequest,
    response: Response,
    user_service: UserService = Depends(get_user_service)
) -> AuthResponse:
    """
    Registers a new learner or creator account.
    Validates name, normalized email, password length, and role.
    Sets HttpOnly authentication cookie on success. Never exposes password or JWT in body.
    """
    # 1. Check for existing account with the same email case-insensitively
    existing_user = user_service.get_by_email(payload.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    # 2. Hash password with bcrypt cost factor 12
    password_hash = hash_password(payload.password)

    # 3. Create user record with existing core schema
    created_user = user_service.create_user(
        name=payload.name,
        email=payload.email,
        password_hash=password_hash,
        role=payload.role
    )

    # 4. Create access token and set HttpOnly cookie
    token = create_access_token(
        user_id=created_user["id"],
        email=created_user["email"],
        role=created_user.get("role")
    )
    set_auth_cookie(response, token)

    return AuthResponse(
        message="Account created successfully.",
        user=UserResponse(**created_user)
    )


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=AuthResponse,
    summary="Log in with email/name and password"
)
def login(
    payload: LoginRequest,
    response: Response,
    user_service: UserService = Depends(get_user_service)
) -> AuthResponse:
    """
    Authenticates an existing user by email or name.
    Verifies passwords using bcrypt with transparent legacy Werkzeug hash migration.
    Sets HttpOnly authentication cookie on success. Never exposes password or JWT in body.
    """
    # 1. Retrieve user by identifier (email or name)
    user = user_service.get_by_identifier(payload.identifier)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # 2. Check for Google-only / null-password accounts
    stored_password = user.get("password")
    if not stored_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account does not have a password configured. Please sign in using your configured external login method."
        )

    # 3. Verify password & check for legacy hash upgrade
    is_valid, new_hash = verify_and_maybe_migrate_password(payload.password, stored_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # 4. Transparently update legacy password hash to bcrypt if upgraded
    if new_hash:
        try:
            user_service.update_password(user["id"], new_hash)
            logger.info(f"Successfully migrated legacy password hash for user ID {user['id']}")
        except Exception as e:
            logger.warning(f"Failed to save migrated password hash: {type(e).__name__}")

    # 5. Create access token and set HttpOnly cookie
    token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        role=user.get("role")
    )
    set_auth_cookie(response, token)

    safe_user_data = {k: v for k, v in user.items() if k != "password"}
    return AuthResponse(
        message="Login successful.",
        user=UserResponse(**safe_user_data)
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Log out and clear authentication cookie"
)
def logout(response: Response) -> MessageResponse:
    """
    Clears the HttpOnly authentication cookie. Safe and idempotent.
    """
    delete_auth_cookie(response)
    return MessageResponse(message="Logged out successfully.")


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=CurrentUserResponse,
    summary="Get current authenticated user profile"
)
def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_user)
) -> CurrentUserResponse:
    """
    Retrieves the current authenticated user profile.
    Uses the canonical get_current_user dependency to validate credentials and fetch authoritative data.
    """
    return CurrentUserResponse(user=current_user)
