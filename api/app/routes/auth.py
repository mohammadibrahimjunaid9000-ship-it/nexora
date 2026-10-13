"""
Nexora API - Authentication Endpoints
Provides registration, login, logout, and current user retrieval.
Uses HttpOnly cookie-based JWT authentication and connects strictly to the existing Supabase users table.
"""

import hmac
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from api.app.config import settings

from api.app.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    CurrentUserResponse,
    MessageResponse,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    SetRoleRequest,
    ChangePasswordRequest,
    GoogleAuthUrlResponse,
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
    set_oauth_state_cookie,
    delete_oauth_state_cookie,
    get_oauth_state_from_request,
)
from api.app.auth.dependencies import get_current_user
from api.app.services.users import get_user_service, UserService
from api.app.services.email import get_email_service, EmailService
from api.app.services.google_auth import (
    get_google_auth_service,
    GoogleAuthService,
    GoogleAuthError,
    GoogleAuthConfigurationError,
    InvalidStateError,
    ExpiredStateError,
    InvalidCodeError,
    InvalidIdTokenError,
    ExpiredIdTokenError,
    UnverifiedEmailError,
)

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


@router.post(
    "/set-role",
    status_code=status.HTTP_200_OK,
    response_model=AuthResponse,
    summary="Set initial onboarding role for user"
)
def set_role(
    payload: SetRoleRequest,
    response: Response,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
) -> AuthResponse:
    """
    Onboarding role assignment endpoint.
    A user may only call /set-role if their CURRENT database role is NULL/unassigned.
    Allowed initial roles: 'learner' or 'creator'. Admin can NEVER be self-assigned.
    The database's current role is authoritative.
    Updates only users.role, reissues a fresh access token with the updated role claim,
    and sets the HttpOnly cookie.
    """
    # 1. Authoritative check: fetch user from database
    try:
        db_user = user_service.get_by_id(current_user.id)
    except Exception as e:
        logger.error(f"Database error during set-role lookup: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists."
        )

    # 2. Strict onboarding rule: current database role must be NULL / unassigned
    if db_user.get("role"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role has already been assigned. Role cannot be changed once set."
        )

    # 3. Update only the role column
    try:
        updated_user = user_service.update_role(current_user.id, payload.role)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to update user role."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error updating user role: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    # 4. Issue a fresh access JWT containing the updated role claim and set HttpOnly cookie
    token = create_access_token(
        user_id=updated_user["id"],
        email=updated_user["email"],
        role=updated_user.get("role")
    )
    set_auth_cookie(response, token)

    return AuthResponse(
        message=f"Role set to {payload.role} successfully.",
        user=UserResponse(**updated_user)
    )


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Change password for authenticated user"
)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
) -> MessageResponse:
    """
    Authenticated password rotation endpoint.
    Verifies current_password (supports legacy Werkzeug migration), hashes new_password with bcrypt cost 12,
    updates only users.password, and issues a fresh HttpOnly access token.
    Automatically invalidates any outstanding Stage 4 password reset tokens via fingerprint mechanism.
    Accounts with NULL password (Google-only) are rejected.
    """
    # 1. Fetch authoritative user including password hash
    try:
        db_user = user_service.get_by_id(current_user.id, include_password=True)
    except Exception as e:
        logger.error(f"Database error during change-password lookup: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists."
        )

    # 2. Reject Google-only accounts (NULL password)
    stored_password = db_user.get("password")
    if not stored_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account does not have a password configured. Please authenticate using your configured external login method."
        )

    # 3. Verify current password
    is_valid, _ = verify_and_maybe_migrate_password(payload.current_password, stored_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )

    # 4. Hash new password with bcrypt cost factor 12
    new_password_hash = hash_password(payload.new_password)

    # 5. Update only users.password
    try:
        updated = user_service.update_password(current_user.id, new_password_hash)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to update password."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error updating password: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    # 6. Issue a fresh access token and set HttpOnly cookie
    token = create_access_token(
        user_id=db_user["id"],
        email=db_user["email"],
        role=db_user.get("role")
    )
    set_auth_cookie(response, token)

    return MessageResponse(
        message="Password changed successfully."
    )


@router.get(
    "/google/url",
    status_code=status.HTTP_200_OK,
    response_model=GoogleAuthUrlResponse,
    summary="Get Google OAuth authorization URL"
)
def get_google_auth_url(
    response: Response,
    redirect_to: Optional[str] = None,
    google_service: GoogleAuthService = Depends(get_google_auth_service)
) -> GoogleAuthUrlResponse:
    """
    Generates a secure Google OAuth 2.0 authorization URL with anti-CSRF state.
    Sets HttpOnly state cookie on the response.
    Never exposes client secret or credentials.
    """
    try:
        signed_state, state_nonce = google_service.generate_state(redirect_target=redirect_to)
        set_oauth_state_cookie(response, state_nonce)
        auth_url = google_service.get_authorization_url(state=signed_state)
        return GoogleAuthUrlResponse(url=auth_url)
    except GoogleAuthConfigurationError as e:
        logger.error(f"Google OAuth configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured on this server."
        )


@router.get(
    "/google/callback",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Google OAuth 2.0 callback endpoint"
)
def google_auth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    google_service: GoogleAuthService = Depends(get_google_auth_service),
    user_service: UserService = Depends(get_user_service),
) -> RedirectResponse:
    """
    Google OAuth 2.0 callback endpoint.
    1. Validates absence of Google OAuth errors.
    2. Validates code, state, and cookie state binding (anti-CSRF).
    3. Verifies state signature, expiration, and extracts trusted redirect target.
    4. Exchanges authorization code for tokens (single-use code).
    5. Validates Google ID token cryptographically (RS256, aud, iss, exp, verified email).
    6. Resolves or creates user via UserService.
    7. Issues standard HttpOnly nexora_access_token cookie.
    8. Deletes the nexora_oauth_state cookie.
    9. Redirects 302 to frontend origin + safe redirect path.
    """
    # 1. Handle error reported by Google (e.g. user canceled consent)
    if error:
        logger.warning(f"Google OAuth error received in callback: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication error: {error}"
        )

    # 2. Check for required code and state parameters
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code."
        )

    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth state parameter."
        )

    # 3. Retrieve and validate state cookie binding
    cookie_nonce = get_oauth_state_from_request(request)
    if not cookie_nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth state cookie."
        )

    try:
        state_payload = google_service.verify_state(state=state, cookie_nonce=cookie_nonce)
    except ExpiredStateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state has expired. Please initiate sign-in again."
        )
    except InvalidStateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state or session mismatch."
        )

    safe_redirect = state_payload.get("redirect", "/dashboard")

    # 4. Exchange authorization code with Google
    try:
        tokens = google_service.exchange_code(code)
    except InvalidCodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired authorization code."
        )
    except GoogleAuthConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured on this server."
        )
    except GoogleAuthError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to communicate with Google authentication server."
        )

    # 5. Cryptographically validate Google ID token
    try:
        identity = google_service.validate_id_token(tokens["id_token"])
    except ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token has expired."
        )
    except UnverifiedEmailError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account email is not verified."
        )
    except InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token validation failed."
        )

    # 6. Resolve or create user in Supabase
    try:
        user = user_service.resolve_google_account(
            email=identity.email,
            name=identity.name
        )
    except RuntimeError as e:
        logger.error(f"Database unavailable during Google resolution: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )
    except Exception as e:
        logger.error(f"Database error during Google resolution: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    # 7. Issue standard Nexora access JWT
    access_token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        role=user.get("role")
    )

    # 8. Build safe frontend redirect URL
    frontend_base = settings.FRONTEND_URL.rstrip("/")
    if not safe_redirect.startswith("/"):
        safe_redirect = "/" + safe_redirect
    target_url = f"{frontend_base}{safe_redirect}"

    # 9. Create RedirectResponse, attach access cookie, and delete OAuth state cookie
    redirect_response = RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
    set_auth_cookie(redirect_response, access_token)
    delete_oauth_state_cookie(redirect_response)

    return redirect_response
