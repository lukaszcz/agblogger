"""Shared test fixtures for AgBlogger."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import Settings
from backend.main import create_app
from backend.services.git_service import GitService

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

TEST_SECRET_KEY = "test-secret-key-with-at-least-32-characters"


@asynccontextmanager
async def create_test_client(settings: Settings) -> AsyncGenerator[AsyncClient]:
    """Create an HTTP test client with a fully initialized app.

    Manually performs the work of the application lifespan (DB, FTS, git,
    admin user, cache rebuild) because ASGITransport does not trigger it.
    """
    from sqlalchemy import text

    from backend.database import create_engine as create_db_engine
    from backend.filesystem.content_manager import ContentManager
    from backend.models.base import Base
    from backend.services.auth_service import ensure_admin_user
    from backend.services.cache_service import rebuild_cache

    app = create_app(settings)
    settings.validate_runtime_security()

    engine, session_factory = create_db_engine(settings)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.settings = settings

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await session.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5("
                "title, content, content='posts_cache', content_rowid='id')"
            )
        )
        await session.commit()

    content_manager = ContentManager(content_dir=settings.content_dir)
    app.state.content_manager = content_manager

    git_service = GitService(content_dir=settings.content_dir)
    git_service.init_repo()
    app.state.git_service = git_service

    from backend.crosspost.atproto_oauth import load_or_create_keypair
    from backend.crosspost.bluesky_oauth_state import OAuthStateStore

    oauth_key_path = settings.content_dir / ".atproto-oauth-key.json"
    atproto_key, atproto_jwk = load_or_create_keypair(oauth_key_path)
    app.state.atproto_oauth_key = atproto_key
    app.state.atproto_oauth_jwk = atproto_jwk
    app.state.bluesky_oauth_state = OAuthStateStore(ttl_seconds=600)
    app.state.mastodon_oauth_state = OAuthStateStore(ttl_seconds=600)

    async with session_factory() as session:
        await ensure_admin_user(session, settings)

    async with session_factory() as session:
        await rebuild_cache(session, content_manager)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    await engine.dispose()


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
        secret_key=TEST_SECRET_KEY,
        debug=True,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        content_dir=tmp_content_dir,
        frontend_dir=tmp_path / "frontend",
    )


@pytest.fixture
def git_service(tmp_content_dir: Path) -> GitService:
    """Create a git service for the temporary content directory."""
    gs = GitService(tmp_content_dir)
    gs.init_repo()
    return gs


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
