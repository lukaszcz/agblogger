"""Tests for TOML parsing validation (Issue 34)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from backend.filesystem.toml_manager import parse_labels_config, parse_site_config


class TestSiteConfigValidation:
    def test_page_missing_id_returns_defaults(self, tmp_path: Path) -> None:
        """Issue 34: Page entries without 'id' should fall back to defaults."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "index.toml").write_text(
            '[site]\ntitle = "Test"\n\n[[pages]]\ntitle = "No ID Page"\n'
        )
        config = parse_site_config(content_dir)
        assert config.title == "My Blog"
        assert config.pages == []

    def test_valid_page_config(self, tmp_path: Path) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "index.toml").write_text(
            '[site]\ntitle = "Test"\n\n[[pages]]\nid = "timeline"\ntitle = "Posts"\n'
        )
        config = parse_site_config(content_dir)
        assert len(config.pages) == 1
        assert config.pages[0].id == "timeline"

    def test_missing_index_toml_returns_defaults(self, tmp_path: Path) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        config = parse_site_config(content_dir)
        assert config.title == "My Blog"
        assert config.pages == []


class TestLabelsConfigParsing:
    def test_single_parent(self, tmp_path: Path) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "labels.toml").write_text(
            '[labels]\n[labels.swe]\nnames = ["software engineering"]\nparent = "#cs"\n'
        )
        labels = parse_labels_config(content_dir)
        assert labels["swe"].parents == ["cs"]

    def test_multiple_parents(self, tmp_path: Path) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "labels.toml").write_text(
            '[labels]\n[labels.quantum]\nnames = ["quantum"]\nparents = ["#math", "#physics"]\n'
        )
        labels = parse_labels_config(content_dir)
        assert labels["quantum"].parents == ["math", "physics"]

    def test_missing_labels_toml_returns_empty(self, tmp_path: Path) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        labels = parse_labels_config(content_dir)
        assert labels == {}
