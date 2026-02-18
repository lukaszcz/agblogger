"""Tests for YAML front matter parsing."""

from __future__ import annotations

import datetime

import frontmatter


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
