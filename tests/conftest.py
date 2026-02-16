"""Shared test fixtures for AgBlogger."""


from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import Settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


@pytest.fixture
def tmp_content_dir(tmp_path: Path) -> Path:
    """Create a temporary content directory with default structure."""
    content = tmp_path / "content"
    content.mkdir()
    (content / "posts").mkdir()
    (content / "assets").mkdir()

    # Write minimal index.toml
    (content / "index.toml").write_text(
        '[site]\ntitle = "Test Blog"\ntimezone = "UTC"\n\n'
        '[[pages]]\nid = "timeline"\ntitle = "Posts"\n'
    )
    (content / "labels.toml").write_text("[labels]\n")

    return content


@pytest.fixture
def test_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
    """Create test settings with temporary paths."""
    db_path = tmp_path / "test.db"
    return Settings(
        secret_key="test-secret-key",
        debug=True,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        content_dir=tmp_content_dir,
        frontend_dir=tmp_path / "frontend",
    )


@pytest.fixture
async def db_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine]:
    """Create a test database engine."""
    engine = create_async_engine(
        test_settings.database_url,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession]:
    """Create a test database session."""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
