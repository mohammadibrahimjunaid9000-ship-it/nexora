"""
Nexora API - User Profile Endpoints
Provides authenticated current user profile retrieval and name updates,
as well as safe public user profile lookups.
Strictly reuses existing UserService and Supabase live columns without schema mutations.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.app.auth.dependencies import get_current_user
from api.app.auth.schemas import UserResponse
from api.app.schemas.users import (
    UpdateProfileRequest,
    UserProfileResponse,
    PublicUserProfileResponse,
)
from api.app.services.users import get_user_service, UserService

logger = logging.getLogger("nexora.api.users")

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=UserProfileResponse,
    summary="Get current authenticated user profile"
)
def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfileResponse:
    """
    Retrieves the authoritative profile for the currently authenticated user.
    Authentication is required via HttpOnly access cookie.
    Extracts the user identity strictly from the validated session.
    Never exposes passwords, tokens, or unauthoritative attributes.
    """
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    try:
        user = user_service.get_by_id(user_id)
    except Exception as e:
        logger.error(f"Database error during get_current_user_profile lookup: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists."
        )

    return UserProfileResponse(**user)


@router.put(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=UserProfileResponse,
    summary="Update current authenticated user profile name"
)
def update_current_user_profile(
    payload: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfileResponse:
    """
    Updates the authenticated user's display name.
    Anti-IDOR guarantee: The target user ID is derived strictly from current_user["id"].
    The client cannot specify or alter the target user ID via body, query, or path.
    Only the 'name' field is mutable.
    """
    user_id = current_user.id if hasattr(current_user, "id") else current_user["id"]
    try:
        updated_user = user_service.update_name(user_id=user_id, name=payload.name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Database error during user profile update: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found."
        )

    return UserProfileResponse(**updated_user)


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=PublicUserProfileResponse,
    summary="Get public user profile"
)
def get_public_user_profile(
    user_id: str = Path(..., description="Target user identifier (positive integer)"),
    user_service: UserService = Depends(get_user_service),
) -> PublicUserProfileResponse:
    """
    Retrieves minimal, non-sensitive public user information (id, name, role).
    Does NOT require authentication.
    Strictly excludes email, password, points, joined_at, and internal credentials.
    Invalid or nonexistent user IDs safely return 404 Not Found.
    """
    try:
        parsed_id = int(user_id)
        if parsed_id <= 0:
            raise ValueError("user_id must be a positive integer.")
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    try:
        profile = user_service.get_public_profile(parsed_id)
    except Exception as e:
        logger.error(f"Database error during public profile lookup: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable."
        )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    return PublicUserProfileResponse(**profile)
