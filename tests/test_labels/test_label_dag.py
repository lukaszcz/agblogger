"""Tests for label DAG operations."""

from __future__ import annotations

import tomllib
from collections import defaultdict, deque
from typing import TYPE_CHECKING

from backend.services.dag import break_cycles

if TYPE_CHECKING:
    from pathlib import Path


class TestLabelParsing:
    def test_parse_empty_labels_toml(self, tmp_content_dir: Path) -> None:
        labels_path = tmp_content_dir / "labels.toml"
        data = tomllib.loads(labels_path.read_text())
        assert "labels" in data
        assert data["labels"] == {}

    def test_parse_labels_toml_with_entries(self, tmp_path: Path) -> None:
        toml_content = """\
[labels]
  [labels.cs]
  names = ["computer science"]

  [labels.swe]
  names = ["software engineering", "programming"]
  parent = "#cs"
"""
        labels_path = tmp_path / "labels.toml"
        labels_path.write_text(toml_content)

        data = tomllib.loads(labels_path.read_text())
        assert "cs" in data["labels"]
        assert "swe" in data["labels"]
        assert data["labels"]["swe"]["parent"] == "#cs"
        assert "programming" in data["labels"]["swe"]["names"]


class TestBreakCycles:
    def test_no_cycles(self) -> None:
        edges = [("swe", "cs"), ("ai", "cs")]
        accepted, dropped = break_cycles(edges)
        assert set(accepted) == {("swe", "cs"), ("ai", "cs")}
        assert dropped == []

    def test_single_cycle(self) -> None:
        edges = [("a", "b"), ("b", "c"), ("c", "a")]
        accepted, dropped = break_cycles(edges)
        assert len(dropped) == 1
        assert _is_dag(accepted)

    def test_self_loop(self) -> None:
        edges = [("a", "a")]
        accepted, dropped = break_cycles(edges)
        assert accepted == []
        assert dropped == [("a", "a")]

    def test_multiple_cycles(self) -> None:
        edges = [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")]
        accepted, dropped = break_cycles(edges)
        assert len(dropped) == 2
        assert _is_dag(accepted)

    def test_diamond_no_cycle(self) -> None:
        edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
        accepted, dropped = break_cycles(edges)
        assert set(accepted) == set(edges)
        assert dropped == []

    def test_diamond_with_cycle(self) -> None:
        edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "a")]
        accepted, dropped = break_cycles(edges)
        assert len(dropped) >= 1
        assert _is_dag(accepted)

    def test_empty(self) -> None:
        accepted, dropped = break_cycles([])
        assert accepted == []
        assert dropped == []


def _is_dag(edges: list[tuple[str, str]]) -> bool:
    """Verify edges form a DAG using Kahn's algorithm."""
    children: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)
    nodes: set[str] = set()
    for child, parent in edges:
        children[parent].append(child)
        in_degree[child] += 1
        nodes.add(child)
        nodes.add(parent)

    queue = deque(n for n in nodes if in_degree[n] == 0)
    count = 0
    while queue:
        node = queue.popleft()
        count += 1
        for c in children[node]:
            in_degree[c] -= 1
            if in_degree[c] == 0:
                queue.append(c)
    return count == len(nodes)
