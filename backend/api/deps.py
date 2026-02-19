"""Shared API dependencies: DB session, auth, content manager."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.filesystem.content_manager import ContentManager
from backend.models.user import User
from backend.services.auth_service import decode_access_token
from backend.services.git_service import GitService

security = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    """Get application settings from app state."""
    settings: Settings = request.app.state.settings
    return settings


def get_git_service(request: Request) -> GitService:
    """Get git service from app state."""
    gs: GitService = request.app.state.git_service
    return gs


def get_content_manager(request: Request) -> ContentManager:
    """Get content manager from app state."""
    cm: ContentManager = request.app.state.content_manager
    return cm


async def get_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """Get a database session."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Get current authenticated user, or None if not authenticated."""
    if credentials is None:
        return None

    settings: Settings = request.app.state.settings
    payload = decode_access_token(credentials.credentials, settings.secret_key)
    if payload is None:
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    if not isinstance(user_id, (str, int)) or (isinstance(user_id, str) and not user_id.isdigit()):
        return None

    user = await session.get(User, int(user_id))
    return user


async def require_auth(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    """Require authentication. Raises 401 if not authenticated."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    user: Annotated[User, Depends(require_auth)],
) -> User:
    """Require admin role. Raises 403 if not admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
