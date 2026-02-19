"""Authentication schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request."""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class RegisterRequest(BaseModel):
    """User registration request."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)
    display_name: str | None = None
    invite_code: str | None = Field(default=None, min_length=1, max_length=200)


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str | None = Field(default=None, min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    """Logout request."""

    refresh_token: str | None = Field(default=None, min_length=1, max_length=512)


class InviteCreateRequest(BaseModel):
    """Request to create a registration invite code."""

    expires_days: int | None = Field(default=None, ge=1, le=90)


class InviteCreateResponse(BaseModel):
    """Response containing a new invite code."""

    invite_code: str
    created_at: str
    expires_at: str


class PersonalAccessTokenCreateRequest(BaseModel):
    """Request to create a personal access token."""

    name: str = Field(min_length=1, max_length=100)
    expires_days: int | None = Field(default=30, ge=1, le=3650)


class PersonalAccessTokenResponse(BaseModel):
    """Personal access token metadata."""

    id: int
    name: str
    created_at: str
    expires_at: str | None = None
    last_used_at: str | None = None
    revoked_at: str | None = None


class PersonalAccessTokenCreateResponse(PersonalAccessTokenResponse):
    """Created token metadata including one-time plaintext token."""

    token: str


class UserResponse(BaseModel):
    """User info response."""

    id: int
    username: str
    email: str
    display_name: str | None = None
    is_admin: bool = False
