"""
Nexora API - Authentication & Role Authorization Dependencies
Provides reusable FastAPI dependencies for current user retrieval and role-based access control.
Authoritative user data is queried strictly from the database.
"""

from typing import Union, Set, List
import logging
from fastapi import Depends, HTTPException, Request, status

from api.app.auth.schemas import UserResponse, UserRole
from api.app.auth.security import (
    get_token_from_request,
    decode_access_token,
    ExpiredTokenError,
    InvalidTokenError,
)
from api.app.services.users import get_user_service, UserService

logger = logging.getLogger("nexora.api.auth.dependencies")


def get_current_user(
    request: Request,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """
    Canonical authentication dependency.
    Extracts JWT strictly from the HttpOnly cookie, validates signature, expiration,
    and type ('access'), then retrieves the authoritative user profile from Supabase.

    Raises:
        HTTPException(401): If unauthenticated, token is invalid/expired/wrong-type, or user is deleted.
        HTTPException(503): If the database service is unreachable or encounters an infrastructure error.
    """
    # 1. Read token strictly from HttpOnly cookie
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    # 2. Decode and validate JWT (signature, algorithm, expiration, type=='access')
    try:
        payload = decode_access_token(token)
    except ExpiredTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired."
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )

    # 3. Query authoritative database for user record
    try:
        user = user_service.get_by_id(user_id)
    except Exception as e:
        logger.error(f"Database lookup error during authentication: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    # 4. Check user existence
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists."
        )

    return UserResponse(**user)


class RoleChecker:
    """
    Reusable dependency factory to authorize requests by authoritative database role.
    Always receives the authenticated user via get_current_user and checks current_user.role.
    Never trusts JWT claims or client-supplied inputs for role verification.
    """

    def __init__(self, allowed_roles: Union[Set[str], List[str], str], role_label: str):
        if isinstance(allowed_roles, str):
            self.allowed_roles = {allowed_roles.lower()}
        else:
            self.allowed_roles = {str(r).lower() for r in allowed_roles}
        self.role_label = role_label

    def __call__(self, current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        user_role = (current_user.role or "").strip().lower()
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{self.role_label} privileges required."
            )
        return current_user


# Pre-bound role authorization dependencies
require_learner = RoleChecker(allowed_roles={UserRole.LEARNER.value}, role_label="Learner")
require_creator = RoleChecker(allowed_roles={UserRole.CREATOR.value}, role_label="Creator")
require_admin = RoleChecker(allowed_roles={UserRole.ADMIN.value}, role_label="Admin")
