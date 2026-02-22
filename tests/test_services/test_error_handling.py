"""Tests for error handling in services and libraries."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.filesystem.content_manager import ContentManager
from backend.filesystem.toml_manager import (
    LabelDef,
    SiteConfig,
    parse_labels_config,
    parse_site_config,
    write_labels_config,
    write_site_config,
)
from backend.pandoc.renderer import _render_markdown_sync
from backend.services.datetime_service import parse_datetime


class TestParseDatetimeParserError:
    """H3: pendulum.ParserError should be converted to ValueError."""

    def test_invalid_date_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            parse_datetime("not-a-date")

    def test_gibberish_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            parse_datetime("xyz123!@#")


class TestConfigParsingOSError:
    """H4: OSError in config parsing returns defaults."""

    def test_site_config_permission_error(self, tmp_path: Path) -> None:
        index = tmp_path / "index.toml"
        index.write_text('[site]\ntitle = "Test"')
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            result = parse_site_config(tmp_path)
        assert result.title == "My Blog"  # default

    def test_labels_config_permission_error(self, tmp_path: Path) -> None:
        labels = tmp_path / "labels.toml"
        labels.write_text("[labels.foo]\nnames = ['foo']")
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            result = parse_labels_config(tmp_path)
        assert result == {}


class TestLabelsConfigTypeCheck:
    """M10: Non-dict label entries should be skipped."""

    def test_string_label_entry_skipped(self, tmp_path: Path) -> None:
        labels = tmp_path / "labels.toml"
        labels.write_text('[labels]\nfoo = "bar"')
        result = parse_labels_config(tmp_path)
        assert "foo" not in result


class TestReadPostErrorHandling:
    """H5: read_post returns None on parse errors."""

    def test_invalid_yaml_returns_none(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        bad_post = posts_dir / "bad.md"
        bad_post.write_text("---\ntitle: [\n---\nbody")
        (tmp_path / "index.toml").write_text('[site]\ntitle = "Test"')
        (tmp_path / "labels.toml").write_text("[labels]")
        cm = ContentManager(content_dir=tmp_path)
        result = cm.read_post("posts/bad.md")
        assert result is None

    def test_binary_file_returns_none(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        bad_post = posts_dir / "binary.md"
        bad_post.write_bytes(b"\x80\x81\x82\x83")
        (tmp_path / "index.toml").write_text('[site]\ntitle = "Test"')
        (tmp_path / "labels.toml").write_text("[labels]")
        cm = ContentManager(content_dir=tmp_path)
        result = cm.read_post("posts/binary.md")
        assert result is None


class TestReadPageErrorHandling:
    """M11: read_page returns None on I/O errors."""

    def test_binary_page_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "index.toml").write_text(
            '[site]\ntitle = "Test"\n\n[[pages]]\nid = "about"\ntitle = "About"\nfile = "about.md"'
        )
        (tmp_path / "labels.toml").write_text("[labels]")
        about = tmp_path / "about.md"
        about.write_bytes(b"\x80\x81\x82\x83")
        cm = ContentManager(content_dir=tmp_path)
        result = cm.read_page("about")
        assert result is None


class TestPandocOSError:
    """M13: OSError from subprocess.run caught and raised as RuntimeError."""

    def test_oserror_raises_runtime_error(self) -> None:
        with (
            patch("subprocess.run", side_effect=OSError("Too many open files")),
            pytest.raises(RuntimeError, match="system error"),
        ):
            _render_markdown_sync("# hello")


class TestSafeParseNames:
    """M7: _safe_parse_names handles corrupted JSON gracefully."""

    def test_valid_json_list(self) -> None:
        from backend.services.label_service import _safe_parse_names

        assert _safe_parse_names('["foo", "bar"]') == ["foo", "bar"]

    def test_invalid_json(self) -> None:
        from backend.services.label_service import _safe_parse_names

        assert _safe_parse_names("not valid json {") == []

    def test_json_non_list(self) -> None:
        from backend.services.label_service import _safe_parse_names

        assert _safe_parse_names('{"key": "value"}') == []

    def test_json_null(self) -> None:
        from backend.services.label_service import _safe_parse_names

        assert _safe_parse_names("null") == []


class TestSyncYamlError:
    """H6: yaml.YAMLError caught in normalize_post_frontmatter."""

    def test_malformed_yaml_skipped(self, tmp_path: Path) -> None:
        post = tmp_path / "posts" / "bad.md"
        post.parent.mkdir(parents=True)
        post.write_text("---\ntitle: [\n---\nbody")
        from backend.services.sync_service import normalize_post_frontmatter

        warnings = normalize_post_frontmatter(
            uploaded_files=["posts/bad.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="admin",
        )
        assert any("parse error" in w for w in warnings)


class TestFTSOperationalError:
    """M8: FTS5 OperationalError returns empty results."""

    @pytest.mark.asyncio
    async def test_fts_error_returns_empty(self) -> None:
        from sqlalchemy.exc import OperationalError

        mock_session = AsyncMock()
        mock_session.execute.side_effect = OperationalError("fts5", {}, Exception())

        from backend.services.post_service import search_posts

        results = await search_posts(mock_session, "test")
        assert results == []


class TestAtomicWrites:
    """M9: TOML writes are atomic."""

    def test_write_labels_uses_temp_file(self, tmp_path: Path) -> None:
        labels = {"test": LabelDef(id="test", names=["test"])}
        write_labels_config(tmp_path, labels)
        # File should exist and be valid TOML
        import tomllib

        data = tomllib.loads((tmp_path / "labels.toml").read_text())
        assert "test" in data["labels"]
        # No .tmp file left behind
        assert not (tmp_path / "labels.toml.tmp").exists()

    def test_write_site_config_uses_temp_file(self, tmp_path: Path) -> None:
        config = SiteConfig(title="Test Blog")
        write_site_config(tmp_path, config)
        import tomllib

        data = tomllib.loads((tmp_path / "index.toml").read_text())
        assert data["site"]["title"] == "Test Blog"
        assert not (tmp_path / "index.toml.tmp").exists()
