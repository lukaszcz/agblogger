"""DAG utilities for label hierarchy cycle detection."""

from __future__ import annotations

WHITE, GRAY, BLACK = 0, 1, 2


def break_cycles(
    edges: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Remove back-edges to make an edge list acyclic.

    Uses DFS with white/gray/black coloring. Edges that would close a cycle
    (back-edges to gray nodes) are dropped. O(V+E) time.

    Args:
        edges: list of (child, parent) tuples.

    Returns:
        (accepted_edges, dropped_edges)
    """
    # Build adjacency: child -> list of parents
    adj: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for child, parent in edges:
        adj.setdefault(child, []).append(parent)
        nodes.add(child)
        nodes.add(parent)

    color: dict[str, int] = {n: WHITE for n in nodes}
    accepted: list[tuple[str, str]] = []
    dropped: list[tuple[str, str]] = []

    def dfs(node: str) -> None:
        color[node] = GRAY
        for parent in adj.get(node, []):
            if color[parent] == GRAY:
                dropped.append((node, parent))
            elif color[parent] == WHITE:
                accepted.append((node, parent))
                dfs(parent)
            else:  # BLACK
                accepted.append((node, parent))
        color[node] = BLACK

    for node in nodes:
        if color[node] == WHITE:
            dfs(node)

    return accepted, dropped
