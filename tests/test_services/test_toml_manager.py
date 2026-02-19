"""Tests for TOML manager read/write roundtrip."""

from __future__ import annotations

from pathlib import Path

from backend.filesystem.toml_manager import (
    PageConfig,
    SiteConfig,
    parse_site_config,
    write_site_config,
)


def test_write_site_config_roundtrip(tmp_path: Path) -> None:
    config = SiteConfig(
        title="My Test Blog",
        description="A test blog",
        default_author="Test Author",
        timezone="America/New_York",
        pages=[
            PageConfig(id="timeline", title="Posts"),
            PageConfig(id="about", title="About", file="about.md"),
            PageConfig(id="labels", title="Tags"),
        ],
    )
    (tmp_path / "index.toml").write_text("[site]\n")

    write_site_config(tmp_path, config)
    result = parse_site_config(tmp_path)

    assert result.title == "My Test Blog"
    assert result.description == "A test blog"
    assert result.default_author == "Test Author"
    assert result.timezone == "America/New_York"
    assert len(result.pages) == 3
    assert result.pages[0].id == "timeline"
    assert result.pages[1].id == "about"
    assert result.pages[1].file == "about.md"
    assert result.pages[2].id == "labels"
    assert result.pages[2].file is None


def test_write_site_config_preserves_pages_without_file(tmp_path: Path) -> None:
    config = SiteConfig(
        title="Blog",
        pages=[
            PageConfig(id="timeline", title="Posts"),
        ],
    )
    (tmp_path / "index.toml").write_text("[site]\n")

    write_site_config(tmp_path, config)
    result = parse_site_config(tmp_path)

    assert result.pages[0].file is None
