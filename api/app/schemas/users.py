"""
Nexora API - User Profile Pydantic Schemas
Strictly validated request and response models for Stage 7 user profile operations.
Adheres strictly to the authoritative live database columns (no non-existent fields).
"""

from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UpdateProfileRequest(BaseModel):
    """
    Request payload for updating the authenticated user's profile.
    The ONLY mutable field in this stage is `name`.
    Extra fields are strictly forbidden (extra='forbid') to prevent unauthorized attribute modifications.
    """
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=150, description="User full display name")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Name must be a valid string.")
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("Name must be at least 2 characters long after trimming whitespace.")
        if len(clean) > 150:
            raise ValueError("Name must not exceed 150 characters.")
        return clean


class UserProfileResponse(BaseModel):
    """
    Authoritative safe profile representation for the authenticated user.
    Exposes only the verified live database columns.
    Never exposes passwords, password hashes, or internal tokens.
    """
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    email: str
    role: Optional[str] = None
    points: int = 0
    joined_at: Optional[Union[str, datetime]] = None


class PublicUserProfileResponse(BaseModel):
    """
    Minimal non-sensitive public profile representation (e.g. for course/instructor cards).
    Strictly excludes email, password, points, joined_at, and internal metadata.
    """
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    role: Optional[str] = None
