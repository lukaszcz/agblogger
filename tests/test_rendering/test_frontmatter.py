"""Tests for YAML front matter parsing."""

from __future__ import annotations

import datetime

import frontmatter

from backend.filesystem.frontmatter import RECOGNIZED_FIELDS, PostData, parse_post, serialize_post
from backend.services.datetime_service import now_utc


class TestRecognizedFields:
    def test_recognized_fields_contains_expected(self) -> None:
        assert "created_at" in RECOGNIZED_FIELDS
        assert "modified_at" in RECOGNIZED_FIELDS
        assert "author" in RECOGNIZED_FIELDS
        assert "labels" in RECOGNIZED_FIELDS
        assert "draft" in RECOGNIZED_FIELDS

    def test_recognized_fields_is_frozenset(self) -> None:
        assert isinstance(RECOGNIZED_FIELDS, frozenset)


class TestFrontmatterParsing:
    def test_parse_basic_post(self) -> None:
        content = """\
---
created_at: 2026-02-02 22:21:29.975359+00
modified_at: 2026-02-02 22:21:35.000000+00
labels: ["#swe", "#ai"]
---
# Title

Blog post content
"""
        post = frontmatter.loads(content)
        # YAML auto-parses timestamps into datetime objects
        assert isinstance(post["created_at"], datetime.datetime)
        assert post["created_at"].year == 2026
        assert post["created_at"].month == 2
        assert post["created_at"].microsecond == 975359
        assert post["labels"] == ["#swe", "#ai"]
        assert post.content.startswith("# Title")

    def test_parse_minimal_post(self) -> None:
        content = """\
---
created_at: 2026-02-02
---
# Hello

Content here.
"""
        post = frontmatter.loads(content)
        # YAML auto-parses date-only values into date objects
        assert isinstance(post["created_at"], datetime.date)
        assert post["created_at"] == datetime.date(2026, 2, 2)
        assert "Hello" in post.content

    def test_parse_post_without_frontmatter(self) -> None:
        content = "# Just a title\n\nSome content.\n"
        post = frontmatter.loads(content)
        assert post.metadata == {}
        assert "Just a title" in post.content

    def test_title_extraction_from_heading(self) -> None:
        content = """\
---
created_at: 2026-01-01
---
# My Blog Post Title

Content follows the title.
"""
        post = frontmatter.loads(content)
        # Extract title from first # heading
        lines = post.content.strip().split("\n")
        title_line = next(
            (line for line in lines if line.startswith("# ")),
            None,
        )
        assert title_line is not None
        title = title_line.removeprefix("# ").strip()
        assert title == "My Blog Post Title"

    def test_roundtrip_frontmatter(self) -> None:
        post = frontmatter.Post(
            "# Title\n\nContent",
            created_at="2026-02-02 22:21:29.975359+00",
            labels=["#swe"],
        )
        dumped = frontmatter.dumps(post)
        reparsed = frontmatter.loads(dumped)
        assert reparsed["created_at"] == "2026-02-02 22:21:29.975359+00"
        assert reparsed["labels"] == ["#swe"]
        assert "# Title" in reparsed.content


class TestSerializePost:
    def test_labels_serialized_with_hash_prefix(self) -> None:
        now = now_utc()
        post_data = PostData(
            title="Test",
            content="# Test\n\nBody",
            raw_content="",
            created_at=now,
            modified_at=now,
            labels=["swe", "ai"],
        )
        result = serialize_post(post_data)
        parsed = frontmatter.loads(result)
        assert parsed["labels"] == ["#swe", "#ai"]

    def test_draft_flag_present_when_true(self) -> None:
        now = now_utc()
        post_data = PostData(
            title="Draft",
            content="# Draft\n\nContent",
            raw_content="",
            created_at=now,
            modified_at=now,
            is_draft=True,
        )
        result = serialize_post(post_data)
        parsed = frontmatter.loads(result)
        assert parsed["draft"] is True

    def test_draft_flag_absent_when_false(self) -> None:
        now = now_utc()
        post_data = PostData(
            title="Published",
            content="# Published\n\nContent",
            raw_content="",
            created_at=now,
            modified_at=now,
            is_draft=False,
        )
        result = serialize_post(post_data)
        parsed = frontmatter.loads(result)
        assert "draft" not in parsed.metadata

    def test_author_included_when_present(self) -> None:
        now = now_utc()
        post_data = PostData(
            title="Test",
            content="# Test\n\nBody",
            raw_content="",
            created_at=now,
            modified_at=now,
            author="Alice",
        )
        result = serialize_post(post_data)
        parsed = frontmatter.loads(result)
        assert parsed["author"] == "Alice"

    def test_author_omitted_when_none(self) -> None:
        now = now_utc()
        post_data = PostData(
            title="Test",
            content="# Test\n\nBody",
            raw_content="",
            created_at=now,
            modified_at=now,
            author=None,
        )
        result = serialize_post(post_data)
        parsed = frontmatter.loads(result)
        assert "author" not in parsed.metadata

    def test_timestamps_roundtrip(self) -> None:
        now = now_utc()
        post_data = PostData(
            title="Test",
            content="# Test\n\nBody",
            raw_content="",
            created_at=now,
            modified_at=now,
        )
        result = serialize_post(post_data)
        reparsed = parse_post(result)
        assert reparsed.created_at.year == now.year
        assert reparsed.created_at.month == now.month
        assert reparsed.created_at.day == now.day

    def test_full_roundtrip_through_parse(self) -> None:
        now = now_utc()
        original = PostData(
            title="Round Trip",
            content="# Round Trip\n\nFull content here.",
            raw_content="",
            created_at=now,
            modified_at=now,
            author="Admin",
            labels=["swe", "ai"],
            is_draft=True,
            file_path="posts/roundtrip.md",
        )
        serialized = serialize_post(original)
        reparsed = parse_post(serialized, file_path="posts/roundtrip.md")
        assert reparsed.title == "Round Trip"
        assert reparsed.labels == ["swe", "ai"]
        assert reparsed.is_draft is True
        assert reparsed.author == "Admin"
        assert "Full content here." in reparsed.content
