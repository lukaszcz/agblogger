"""Test crosspost credential decryption fallback handles corruption."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from backend.models.base import Base
from backend.models.crosspost import SocialAccount
from backend.services.crosspost_service import crosspost
from backend.services.datetime_service import format_datetime, now_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.fixture
async def _create_tables(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def session(db_session: AsyncSession, _create_tables: None) -> AsyncSession:
    return db_session


class TestCrosspostDecryptFallback:
    async def test_corrupted_credentials_produce_clear_error(self, session):
        """When credentials cannot be decrypted or parsed, produce a clear error."""
        now = format_datetime(now_utc())
        account = SocialAccount(
            user_id=1,
            platform="bluesky",
            account_name="test",
            credentials="corrupted-not-json-not-encrypted",
            created_at=now,
            updated_at=now,
        )
        session.add(account)
        await session.commit()

        mock_cm = MagicMock()
        mock_cm.read_post.return_value = MagicMock(
            title="Test", content="content", labels=[], is_draft=False
        )
        mock_cm.get_plain_excerpt.return_value = "excerpt"

        # This should not raise an unhandled JSONDecodeError
        results = await crosspost(
            session=session,
            content_manager=mock_cm,
            post_path="posts/test.md",
            platforms=["bluesky"],
            user_id=1,
            site_url="https://example.com",
            secret_key="wrong-key",
        )
        assert len(results) == 1
        assert not results[0].success
        assert "corrupted" in results[0].error.lower() or "credential" in results[0].error.lower()
