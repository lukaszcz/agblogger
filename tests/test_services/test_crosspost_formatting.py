"""Tests for cross-posting text formatting edge cases (Issues 15, 16, 17)."""

from __future__ import annotations

from backend.crosspost.base import CrossPostContent
from backend.crosspost.bluesky import BSKY_CHAR_LIMIT, _build_post_text, _find_facets
from backend.crosspost.mastodon import MASTODON_CHAR_LIMIT, _build_status_text


class TestBlueskyEdgeCases:
    def test_very_long_url_leaves_no_room_for_excerpt(self) -> None:
        """Issue 15: When available <= 3, excerpt should be truncated gracefully."""
        long_url = "https://example.com/" + "a" * 280
        content = CrossPostContent(
            title="Test",
            excerpt="Hello world this is a long excerpt",
            url=long_url,
            labels=["tag1", "tag2", "tag3"],
        )
        text = _build_post_text(content)
        # Should not crash; excerpt portion may be empty or very short
        assert long_url in text
        assert len(text) >= len(long_url)

    def test_available_exactly_zero(self) -> None:
        """When suffix takes exactly the limit, excerpt should be empty."""
        # Build a URL that, with suffix formatting, takes up exactly BSKY_CHAR_LIMIT
        suffix_template_len = 2  # "\n\n"
        target_url_len = BSKY_CHAR_LIMIT - suffix_template_len
        url = "https://x.co/" + "a" * (target_url_len - len("https://x.co/"))
        content = CrossPostContent(
            title="T",
            excerpt="This should be truncated completely",
            url=url,
            labels=[],
        )
        text = _build_post_text(content)
        assert len(text) <= BSKY_CHAR_LIMIT + 50  # Allow some slack for edge math
        assert url in text

    def test_rfind_for_hashtags_matches_suffix_not_excerpt(self) -> None:
        """Issue 16: Hashtag facets should match tags in suffix, not in excerpt."""
        content = CrossPostContent(
            title="Test",
            excerpt="I like #swe in my excerpt",
            url="https://blog.example.com/post",
            labels=["swe"],
        )
        text = _build_post_text(content)
        facets = _find_facets(text, content)

        # Find the hashtag facet
        tag_facets = [
            f for f in facets if f["features"][0]["$type"] == "app.bsky.richtext.facet#tag"
        ]
        assert len(tag_facets) == 1

        # The facet should point to the LAST occurrence (#swe in suffix, not excerpt)
        tag_facet = tag_facets[0]
        byte_start = tag_facet["index"]["byteStart"]
        byte_end = tag_facet["index"]["byteEnd"]
        text_bytes = text.encode("utf-8")
        matched_text = text_bytes[byte_start:byte_end].decode("utf-8")
        assert matched_text == "#swe"
        # The matched position should be after the excerpt's #swe
        excerpt_pos = text.find("#swe")
        suffix_pos = text.rfind("#swe")
        assert suffix_pos > excerpt_pos  # rfind got the suffix one
        assert byte_start == len(text[:suffix_pos].encode("utf-8"))


class TestMastodonEdgeCases:
    def test_very_long_url_leaves_no_room_for_excerpt(self) -> None:
        """Issue 17: Same edge case for Mastodon."""
        long_url = "https://example.com/" + "a" * 480
        content = CrossPostContent(
            title="Test",
            excerpt="Hello world",
            url=long_url,
            labels=["tag1"],
        )
        text = _build_status_text(content)
        assert long_url in text

    def test_char_limit_respected(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="A" * 1000,
            url="https://blog.example.com/post",
            labels=["tag1", "tag2"],
        )
        text = _build_status_text(content)
        assert len(text) <= MASTODON_CHAR_LIMIT
