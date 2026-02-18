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
    password: str = Field(min_length=6)
    display_name: str | None = None


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class UserResponse(BaseModel):
    """User info response."""

    id: int
    username: str
    email: str
    display_name: str | None = None
    is_admin: bool = False
