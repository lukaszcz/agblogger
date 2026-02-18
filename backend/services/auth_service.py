"""Authentication service: JWT tokens and password hashing."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select

from backend.models.user import RefreshToken, User
from backend.services.datetime_service import format_iso, now_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.config import Settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict[str, Any], secret_key: str, expires_minutes: int = 15) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return str(jwt.encode(to_encode, secret_key, algorithm=ALGORITHM))


def create_refresh_token_value() -> str:
    """Generate a cryptographically secure refresh token."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str, secret_key: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token."""
    try:
        payload: dict[str, Any] = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    """Authenticate a user by username and password."""
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


async def create_tokens(session: AsyncSession, user: User, settings: Settings) -> tuple[str, str]:
    """Create access and refresh token pair for a user."""
    access_token = create_access_token(
        {"sub": str(user.id), "username": user.username, "is_admin": user.is_admin},
        settings.secret_key,
        settings.access_token_expire_minutes,
    )

    refresh_token_value = create_refresh_token_value()
    token_hash = hash_token(refresh_token_value)
    now = now_utc()
    expires = now + timedelta(days=settings.refresh_token_expire_days)

    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=format_iso(expires),
        created_at=format_iso(now),
    )
    session.add(refresh_token)
    await session.commit()

    return access_token, refresh_token_value


async def refresh_tokens(
    session: AsyncSession, refresh_token_value: str, settings: Settings
) -> tuple[str, str] | None:
    """Refresh an access token using a refresh token.

    Implements token rotation: old refresh token is revoked.
    """
    token_h = hash_token(refresh_token_value)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_h)
    result = await session.execute(stmt)
    stored_token = result.scalar_one_or_none()

    if stored_token is None:
        return None

    try:
        expires = datetime.fromisoformat(stored_token.expires_at)
    except ValueError:
        await session.delete(stored_token)
        await session.commit()
        return None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        await session.delete(stored_token)
        await session.commit()
        return None

    user = await session.get(User, stored_token.user_id)
    if user is None:
        return None

    await session.delete(stored_token)
    return await create_tokens(session, user, settings)


async def ensure_admin_user(session: AsyncSession, settings: Settings) -> None:
    """Create the admin user if it doesn't exist."""
    stmt = select(User).where(User.username == settings.admin_username)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is None:
        now = format_iso(now_utc())
        admin = User(
            username=settings.admin_username,
            email=f"{settings.admin_username}@localhost",
            password_hash=hash_password(settings.admin_password),
            display_name="Admin",
            is_admin=True,
            created_at=now,
            updated_at=now,
        )
        session.add(admin)
        await session.commit()
