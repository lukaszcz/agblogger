"""Tests for ensure_content_dir() in backend.main."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

from backend.main import ensure_content_dir

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


def test_noop_when_dir_exists(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    marker = content_dir / "existing.txt"
    marker.write_text("keep me")

    ensure_content_dir(content_dir)

    assert marker.read_text() == "keep me"
    assert not (content_dir / "index.toml").exists()
