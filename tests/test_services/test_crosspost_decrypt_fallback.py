"""Test crosspost credential decryption fallback handles corruption."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from backend.models.base import Base
from backend.models.crosspost import SocialAccount
from backend.services.crosspost_service import crosspost
from backend.services.crypto_service import decrypt_value, encrypt_value
from backend.services.datetime_service import format_datetime, now_utc
from tests.conftest import TEST_SECRET_KEY

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
            actor=MagicMock(id=1, username="tester", display_name="Tester", is_admin=False),
            site_url="https://example.com",
            secret_key="wrong-key",
        )
        assert len(results) == 1
        assert not results[0].success
        assert "corrupted" in results[0].error.lower() or "credential" in results[0].error.lower()


class TestCrosspostTokenRefreshPersistence:
    async def test_updated_credentials_are_persisted(self, session, monkeypatch):
        """When BlueskyCrossPoster refreshes tokens during post(), the new tokens
        should be encrypted and saved back to the SocialAccount."""
        import json

        from backend.crosspost.base import CrossPostResult

        class MockPoster:
            platform = "bluesky"
            _updated = {"access_token": "new_at", "refresh_token": "new_rt"}

            async def authenticate(self, creds):
                return True

            async def post(self, content):
                return CrossPostResult(
                    platform_id="at://post/1",
                    url="https://bsky.app/post/1",
                    success=True,
                )

            def get_updated_credentials(self):
                return self._updated

        async def mock_get_poster(platform, creds):
            return MockPoster()

        monkeypatch.setattr("backend.services.crosspost_service.get_poster", mock_get_poster)

        creds = json.dumps({"access_token": "old_at", "refresh_token": "old_rt"})
        encrypted = encrypt_value(creds, TEST_SECRET_KEY)
        now = format_datetime(now_utc())
        account = SocialAccount(
            user_id=1,
            platform="bluesky",
            account_name="test",
            credentials=encrypted,
            created_at=now,
            updated_at=now,
        )
        session.add(account)
        await session.commit()

        mock_cm = MagicMock()
        mock_cm.read_post.return_value = MagicMock(
            title="Test",
            content="content",
            labels=[],
            is_draft=False,
        )
        mock_cm.get_plain_excerpt.return_value = "excerpt"

        results = await crosspost(
            session=session,
            content_manager=mock_cm,
            post_path="posts/test.md",
            platforms=["bluesky"],
            actor=MagicMock(id=1, username="tester", display_name="Tester", is_admin=False),
            site_url="https://example.com",
            secret_key=TEST_SECRET_KEY,
        )
        assert results[0].success

        from sqlalchemy import select

        stmt = select(SocialAccount).where(SocialAccount.id == account.id)
        result = await session.execute(stmt)
        updated_acct = result.scalar_one()
        stored = json.loads(decrypt_value(updated_acct.credentials, TEST_SECRET_KEY))
        assert stored["access_token"] == "new_at"
        assert stored["refresh_token"] == "new_rt"
