"""
Nexora API - Authentication Endpoints
Provides registration, login, logout, and current user retrieval.
Uses HttpOnly cookie-based JWT authentication and connects strictly to the existing Supabase users table.
"""

import hmac
import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.app.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    CurrentUserResponse,
    MessageResponse,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from api.app.auth.security import (
    hash_password,
    verify_and_maybe_migrate_password,
    create_access_token,
    set_auth_cookie,
    delete_auth_cookie,
    generate_password_hash_fingerprint,
    create_password_reset_token,
    decode_password_reset_token,
    InvalidTokenError,
    ExpiredTokenError,
)
from api.app.auth.dependencies import get_current_user
from api.app.services.users import get_user_service, UserService
from api.app.services.email import get_email_service, EmailService

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


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Request password reset instructions"
)
def forgot_password(
    payload: ForgotPasswordRequest,
    user_service: UserService = Depends(get_user_service),
    email_service: EmailService = Depends(get_email_service)
) -> MessageResponse:
    """
    Initiates password recovery for an account.
    Returns the same generic HTTP 200 message regardless of whether the account exists,
    is Google-only, or has a password, completely preventing account enumeration.
    """
    generic_message = "If an account exists with this email, password reset instructions have been sent."

    # 1. Look up user case-insensitively with password
    try:
        user = user_service.get_by_email(payload.email, include_password=True)
    except Exception as e:
        logger.error(f"Database error during forgot-password lookup: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    # 2. Skip token generation if user does not exist or account has NULL password (Google-only)
    if not user or not user.get("password"):
        return MessageResponse(message=generic_message)

    # 3. Generate signed stateless reset token
    reset_token = create_password_reset_token(
        user_id=user["id"],
        email=user["email"],
        current_password_hash=user["password"]
    )

    # 4. Dispatch notification via EmailService
    try:
        email_service.send_password_reset_email(
            to_email=user["email"],
            user_name=user.get("name", "User"),
            reset_token=reset_token
        )
    except Exception as e:
        logger.error(f"Failed to dispatch password reset email: {type(e).__name__}")

    return MessageResponse(message=generic_message)


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Reset password using reset token"
)
def reset_password(
    payload: ResetPasswordRequest,
    user_service: UserService = Depends(get_user_service)
) -> MessageResponse:
    """
    Resets account password using a signed reset token.
    Validates token signature, expiration, type ('reset'), subject, and single-use hash fingerprint.
    Updates only the password column with a new bcrypt cost factor 12 hash.
    """
    invalid_token_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired password reset token."
    )

    # 1. Decode and validate reset JWT
    try:
        token_payload = decode_password_reset_token(payload.token)
    except (InvalidTokenError, ExpiredTokenError):
        raise invalid_token_error

    user_id = token_payload.get("sub")
    token_fingerprint = token_payload.get("fingerprint")

    if not user_id or not token_fingerprint:
        raise invalid_token_error

    # 2. Retrieve authoritative user from database
    try:
        user = user_service.get_by_id(user_id, include_password=True)
    except Exception as e:
        logger.error(f"Database error during password reset: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    if not user or not user.get("password"):
        raise invalid_token_error

    # 3. Recompute expected fingerprint from CURRENT password hash and compare securely
    expected_fingerprint = generate_password_hash_fingerprint(user["password"])
    if not hmac.compare_digest(expected_fingerprint, token_fingerprint):
        raise invalid_token_error

    # 4. Hash new password with bcrypt cost factor 12
    new_password_hash = hash_password(payload.new_password)

    # 5. Update only the password column in Supabase
    try:
        updated = user_service.update_password(user["id"], new_password_hash)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to update password."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database update error during password reset: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    return MessageResponse(
        message="Password reset successfully. You can now log in with your new password."
    )
