"""Tests for ensure_content_dir() in backend.main."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, select

from backend.config import Settings
from backend.main import ensure_content_dir
from backend.models.post import PostCache

if TYPE_CHECKING:
    from pathlib import Path


def test_creates_default_structure(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"

    ensure_content_dir(content_dir)

    assert content_dir.is_dir()
    assert (content_dir / "posts").is_dir()
    assert (content_dir / "index.toml").is_file()
    assert (content_dir / "labels.toml").is_file()


def test_index_toml_is_valid(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"

    ensure_content_dir(content_dir)

    config = tomllib.loads((content_dir / "index.toml").read_text())
    assert config["site"]["title"] == "My Blog"
    assert config["site"]["timezone"] == "UTC"
    assert config["pages"][0]["id"] == "timeline"


def test_labels_toml_is_valid(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"

    ensure_content_dir(content_dir)

    config = tomllib.loads((content_dir / "labels.toml").read_text())
    assert config["labels"] == {}


def test_backfills_when_dir_exists(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    marker = content_dir / "existing.txt"
    marker.write_text("keep me")

    ensure_content_dir(content_dir)

    assert marker.read_text() == "keep me"
    assert (content_dir / "posts").is_dir()
    assert (content_dir / "index.toml").is_file()
    assert (content_dir / "labels.toml").is_file()


@pytest.mark.asyncio
async def test_startup_backfilled_files_are_committed_and_cache_rebuilt(tmp_path: Path) -> None:
    from backend.main import create_app

    content_dir = tmp_path / "content"
    posts_dir = content_dir / "posts"
    posts_dir.mkdir(parents=True)
    (posts_dir / "hello.md").write_text(
        "---\n"
        "title: Hello World\n"
        "created_at: 2026-02-02 22:21:29.975359+00\n"
        "author: Admin\n"
        "---\n"
        "Post body.\n",
        encoding="utf-8",
    )

    settings = Settings(
        secret_key="test-secret-key-with-at-least-32-characters",
        debug=True,
        content_dir=content_dir,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        frontend_dir=tmp_path,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        assert (content_dir / "index.toml").is_file()
        assert (content_dir / "labels.toml").is_file()

        git_service = app.state.git_service
        head = git_service.head_commit()
        assert head is not None
        assert git_service.show_file_at_commit(head, "index.toml") is not None
        assert git_service.show_file_at_commit(head, "labels.toml") is not None

        async with app.state.session_factory() as session:
            result = await session.execute(select(func.count(PostCache.id)))
            assert result.scalar_one() == 1
