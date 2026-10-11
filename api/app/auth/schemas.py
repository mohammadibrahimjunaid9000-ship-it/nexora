"""
Nexora API - Authentication Pydantic Schemas
Strictly validated request and response models for Stage 2 auth flows.
"""

from enum import Enum
from typing import Optional
import re
from pydantic import BaseModel, Field, field_validator, model_validator


class UserRole(str, Enum):
    """Authoritative user roles supported by the Nexora platform."""
    LEARNER = "learner"
    CREATOR = "creator"
    ADMIN = "admin"


class UserResponse(BaseModel):
    """Safe user profile response representation (never exposes passwords or hashes)."""
    id: int
    name: str
    email: str
    role: Optional[str] = "learner"
    points: int = 0
    joined_at: Optional[str] = None


class RegisterRequest(BaseModel):
    """Payload for user registration."""
    name: str = Field(..., min_length=1, max_length=150, description="Full Name")
    email: str = Field(..., min_length=3, max_length=150, description="Email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")
    confirm_password: str = Field(..., min_length=8, max_length=128, description="Password confirmation")
    role: Optional[str] = Field("learner", description="Role: 'learner' or 'creator'")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Full Name is required.")
        return clean

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(regex, clean):
            raise ValueError("Please enter a valid email address.")
        return clean

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> str:
        if not v:
            return "learner"
        clean = v.strip().lower()
        if clean == "admin":
            raise ValueError("Registration as admin is strictly prohibited.")
        if clean not in ("learner", "creator"):
            raise ValueError("Role must be either 'learner' or 'creator'.")
        return clean

    @model_validator(mode="after")
    def validate_passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(BaseModel):
    """Payload for user login."""
    identifier: Optional[str] = Field(None, description="Email address or username")
    email: Optional[str] = Field(None, description="Email address fallback")
    name: Optional[str] = Field(None, description="Name fallback")
    password: str = Field(..., min_length=1, description="Password")

    @model_validator(mode="after")
    def resolve_identifier(self):
        ident = self.identifier or self.email or self.name
        if not ident or not ident.strip():
            raise ValueError("Email address or username is required.")
        self.identifier = ident.strip()
        return self


class AuthResponse(BaseModel):
    """Authentication success response (tokens are set in HttpOnly cookie only)."""
    message: str
    user: UserResponse


class MessageResponse(BaseModel):
    """Standard message response."""
    message: str


class CurrentUserResponse(BaseModel):
    """Current authenticated user response."""
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    """Payload for requesting a password reset email."""
    email: str = Field(..., min_length=3, max_length=150, description="Account email address")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(regex, clean):
            raise ValueError("Please enter a valid email address.")
        return clean


class ResetPasswordRequest(BaseModel):
    """Payload for completing password reset with signed token."""
    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password (8-128 chars)")
    confirm_password: str = Field(..., min_length=8, max_length=128, description="Confirm new password")

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Reset token is required.")
        return clean

    @model_validator(mode="after")
    def validate_passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self
