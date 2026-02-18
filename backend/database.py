"""Database engine and session management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from backend.config import Settings


def create_engine(
    settings: Settings,
) -> tuple[
    AsyncEngine,
    async_sessionmaker[AsyncSession],
]:
    """Create async engine and session factory.

    Returns (engine, session_factory) tuple.
    """
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """Yield an async database session."""
    async with session_factory() as session:
        yield session
