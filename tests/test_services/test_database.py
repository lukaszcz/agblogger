"""Tests for database engine and session management."""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestDatabase:
    @pytest.mark.asyncio
    async def test_engine_connects(self, db_engine) -> None:  # type: ignore[no-untyped-def]
        async with db_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_session_works(self, db_session: AsyncSession) -> None:
        result = await db_session.execute(text("SELECT 42"))
        assert result.scalar() == 42

    @pytest.mark.asyncio
    async def test_sqlite_wal_mode(self, db_engine) -> None:  # type: ignore[no-untyped-def]
        """Verify SQLite WAL mode can be enabled."""
        async with db_engine.connect() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            result = await conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            assert mode in ("wal", "memory")  # memory for in-memory DBs
