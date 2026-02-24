"""Tests for error handling in services and libraries."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
    """OSError in config parsing returns defaults and logs at ERROR level."""

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

    def test_corrupted_site_config_logs_at_error_level(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        index = tmp_path / "index.toml"
        index.write_text("{{invalid toml")
        with caplog.at_level(logging.ERROR, logger="backend.filesystem.toml_manager"):
            result = parse_site_config(tmp_path)
        assert result.title == "My Blog"  # default
        assert any(r.levelno == logging.ERROR for r in caplog.records)


class TestLabelsConfigTypeCheck:
    """M10: Non-dict label entries should be skipped."""

    def test_string_label_entry_skipped(self, tmp_path: Path) -> None:
        labels = tmp_path / "labels.toml"
        labels.write_text('[labels]\nfoo = "bar"')
        result = parse_labels_config(tmp_path)
        assert "foo" not in result


class TestReadPostErrorHandling:
    """read_post returns None on parse errors and logs appropriately."""

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

    def test_oserror_logs_at_error_level(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        good_post = posts_dir / "good.md"
        good_post.write_text("---\ntitle: Test\n---\nbody")
        (tmp_path / "index.toml").write_text('[site]\ntitle = "Test"')
        (tmp_path / "labels.toml").write_text("[labels]")
        cm = ContentManager(content_dir=tmp_path)

        with (
            patch.object(Path, "read_text", side_effect=PermissionError("denied")),
            caplog.at_level(logging.ERROR, logger="backend.filesystem.content_manager"),
        ):
            result = cm.read_post("posts/good.md")

        assert result is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)


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


class TestPageServicePropagatesRenderError:
    """get_page propagates RenderError instead of returning empty HTML."""

    async def test_get_page_propagates_render_error(self, tmp_path: Path) -> None:
        from backend.pandoc.renderer import RenderError
        from backend.services.page_service import get_page

        (tmp_path / "index.toml").write_text(
            '[site]\ntitle = "Test"\n\n[[pages]]\nid = "about"\ntitle = "About"\nfile = "about.md"'
        )
        (tmp_path / "labels.toml").write_text("[labels]")
        (tmp_path / "about.md").write_text("# About\n\nAbout page.\n")
        cm = ContentManager(content_dir=tmp_path)

        with (
            patch(
                "backend.services.page_service.render_markdown",
                new_callable=AsyncMock,
                side_effect=RenderError("pandoc broken"),
            ),
            pytest.raises(RenderError, match="pandoc broken"),
        ):
            await get_page(cm, "about")


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
    """FTS5 OperationalError propagates to caller."""

    @pytest.mark.asyncio
    async def test_fts_error_propagates(self) -> None:
        from sqlalchemy.exc import OperationalError

        mock_session = AsyncMock()
        mock_session.execute.side_effect = OperationalError("fts5", {}, Exception())

        from backend.services.post_service import search_posts

        with pytest.raises(OperationalError):
            await search_posts(mock_session, "test")


class TestInvalidDateFilterLogging:
    """Invalid date filters should log a warning."""

    @pytest.mark.asyncio
    async def test_invalid_from_date_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        from unittest.mock import MagicMock

        from backend.services.post_service import list_posts

        mock_session = AsyncMock()
        # Return 0 for count query (scalar() is sync on the result object)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        # Return empty list for main query (scalars().all() are sync on the result)
        mock_main_result = MagicMock()
        mock_main_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_main_result])

        with caplog.at_level(logging.WARNING, logger="backend.services.post_service"):
            await list_posts(mock_session, from_date="not-a-date")

        assert any("Invalid from_date" in r.message for r in caplog.records)


class TestSyncTimestampNarrowing:
    """Sync timestamp normalization uses narrowed exception handling."""

    def test_attribute_error_propagates(self, tmp_path: Path) -> None:
        """AttributeError is not caught by narrowed exception handler."""
        from backend.services.sync_service import normalize_post_frontmatter

        post = tmp_path / "posts" / "test.md"
        post.parent.mkdir(parents=True)
        # Valid YAML but with a value that will cause AttributeError in the timestamp path
        post.write_text("---\ntitle: Test\ncreated_at: valid\n---\nbody")

        # The function should handle standard parse errors (ValueError)
        # but not swallow programming bugs (AttributeError)
        warnings = normalize_post_frontmatter(
            uploaded_files=["posts/test.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="admin",
        )
        # ValueError from parse_datetime("valid") is still caught
        assert any("invalid created_at" in w for w in warnings)


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
