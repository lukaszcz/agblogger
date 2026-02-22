"""Tests for semantic front matter merging."""

from __future__ import annotations

from backend.services.sync_service import merge_frontmatter


class TestMergeFrontmatter:
    def test_no_changes(self) -> None:
        base = {"title": "T", "author": "A", "labels": ["#a"], "created_at": "2026-01-01"}
        server = dict(base)
        client = dict(base)
        result = merge_frontmatter(base, server, client)
        assert result.merged == base
        assert result.field_conflicts == []

    def test_labels_set_union(self) -> None:
        base = {"labels": ["#a", "#b"]}
        server = {"labels": ["#a", "#b", "#c"]}
        client = {"labels": ["#a", "#b", "#d"]}
        result = merge_frontmatter(base, server, client)
        assert set(result.merged["labels"]) == {"#a", "#b", "#c", "#d"}
        assert result.field_conflicts == []

    def test_labels_removal_both_sides(self) -> None:
        base = {"labels": ["#a", "#b", "#c"]}
        server = {"labels": ["#a", "#c"]}
        client = {"labels": ["#a", "#b"]}
        result = merge_frontmatter(base, server, client)
        assert set(result.merged["labels"]) == {"#a"}
        assert result.field_conflicts == []

    def test_labels_add_and_remove(self) -> None:
        base = {"labels": ["#a", "#b"]}
        server = {"labels": ["#a"]}
        client = {"labels": ["#a", "#b", "#c"]}
        result = merge_frontmatter(base, server, client)
        assert set(result.merged["labels"]) == {"#a", "#c"}
        assert result.field_conflicts == []

    def test_modified_at_ignored(self) -> None:
        base = {"modified_at": "2026-01-01"}
        server = {"modified_at": "2026-01-02"}
        client = {"modified_at": "2026-01-03"}
        result = merge_frontmatter(base, server, client)
        assert "modified_at" not in result.merged
        assert result.field_conflicts == []

    def test_title_one_side_changed(self) -> None:
        base = {"title": "Original"}
        server = {"title": "Original"}
        client = {"title": "New Title"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["title"] == "New Title"
        assert result.field_conflicts == []

    def test_title_both_changed_same(self) -> None:
        base = {"title": "Original"}
        server = {"title": "Same New"}
        client = {"title": "Same New"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["title"] == "Same New"
        assert result.field_conflicts == []

    def test_title_conflict(self) -> None:
        base = {"title": "Original"}
        server = {"title": "Server Title"}
        client = {"title": "Client Title"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["title"] == "Server Title"
        assert "title" in result.field_conflicts

    def test_author_conflict(self) -> None:
        base = {"author": "Alice"}
        server = {"author": "Bob"}
        client = {"author": "Charlie"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["author"] == "Bob"
        assert "author" in result.field_conflicts

    def test_draft_server_changed_client_unchanged(self) -> None:
        base = {"draft": True}
        server = {"draft": False}
        client = {"draft": True}
        result = merge_frontmatter(base, server, client)
        assert result.merged["draft"] is False
        assert result.field_conflicts == []

    def test_preserves_unrecognized_fields(self) -> None:
        base = {"title": "T", "custom": "value"}
        server = {"title": "T", "custom": "value"}
        client = {"title": "T", "custom": "new"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["custom"] == "new"

    def test_no_base_returns_server_with_conflicts(self) -> None:
        server = {"title": "Server", "labels": ["#a"]}
        client = {"title": "Client", "labels": ["#b"]}
        result = merge_frontmatter(None, server, client)
        assert result.merged == server
        assert "title" in result.field_conflicts

    def test_server_deletes_field_client_unchanged(self) -> None:
        """Field present in base, removed by server, unchanged by client → deleted."""
        base = {"title": "T", "author": "Alice"}
        server = {"title": "T"}
        client = {"title": "T", "author": "Alice"}
        result = merge_frontmatter(base, server, client)
        assert "author" not in result.merged
        assert result.field_conflicts == []

    def test_client_deletes_field_server_unchanged(self) -> None:
        """Field present in base, removed by client, unchanged by server → deleted."""
        base = {"title": "T", "custom": "val"}
        server = {"title": "T", "custom": "val"}
        client = {"title": "T"}
        result = merge_frontmatter(base, server, client)
        assert "custom" not in result.merged
        assert result.field_conflicts == []

    def test_both_delete_field(self) -> None:
        """Both sides delete same field → deleted, no conflict."""
        base = {"title": "T", "draft": True}
        server = {"title": "T"}
        client = {"title": "T"}
        result = merge_frontmatter(base, server, client)
        assert "draft" not in result.merged
        assert result.field_conflicts == []

    def test_server_deletes_field_client_changes_it(self) -> None:
        """Server removes a recognized field while client changed it → conflict reported."""
        base = {"title": "T", "author": "Alice"}
        server = {"title": "T"}  # server deleted author
        client = {"title": "T", "author": "Bob"}  # client changed author
        result = merge_frontmatter(base, server, client)
        # Server wins (deletion), but conflict should be reported for recognized fields
        assert "author" not in result.merged
        assert "author" in result.field_conflicts

    def test_labels_with_none_value(self) -> None:
        """Labels as None should be treated as empty set."""
        base = {"labels": None}
        server = {"labels": ["#a"]}
        client = {"labels": None}
        result = merge_frontmatter(base, server, client)
        assert set(result.merged["labels"]) == {"#a"}

    def test_labels_with_string_value(self) -> None:
        """Labels as a string (not list) should be treated as empty set."""
        base = {"labels": "not-a-list"}
        server = {"labels": ["#a"]}
        client = {"labels": "not-a-list"}
        result = merge_frontmatter(base, server, client)
        assert set(result.merged["labels"]) == {"#a"}

    def test_draft_server_changed_only(self) -> None:
        """Server changes draft, client unchanged → no conflict (was test_draft_conflict)."""
        base = {"draft": True}
        server = {"draft": False}
        client = {"draft": True}
        result = merge_frontmatter(base, server, client)
        assert result.merged["draft"] is False
        assert result.field_conflicts == []

    def test_draft_both_changed_differently(self) -> None:
        """Both sides changed draft differently → actual conflict."""
        base = {"draft": True}
        server = {"draft": False}
        client = {"draft": "maybe"}  # unusual value but tests conflict path
        result = merge_frontmatter(base, server, client)
        assert result.merged["draft"] is False
        assert "draft" in result.field_conflicts
