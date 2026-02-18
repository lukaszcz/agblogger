"""DAG utilities for label hierarchy cycle detection."""

from __future__ import annotations

WHITE, GRAY, BLACK = 0, 1, 2


def break_cycles(
    edges: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Remove back-edges to make an edge list acyclic.

    Uses iterative DFS with white/gray/black coloring. Edges that would
    close a cycle (back-edges to gray nodes) are dropped. O(V+E) time.
    Traverses child -> parent direction; a back-edge (to a GRAY node)
    indicates a cycle in the label hierarchy.

    Args:
        edges: list of (child, parent) tuples.

    Returns:
        (accepted_edges, dropped_edges)
    """
    adj: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for child, parent in edges:
        adj.setdefault(child, []).append(parent)
        nodes.add(child)
        nodes.add(parent)

    color: dict[str, int] = {n: WHITE for n in nodes}
    accepted: list[tuple[str, str]] = []
    dropped: list[tuple[str, str]] = []

    for start in nodes:
        if color[start] != WHITE:
            continue
        # Stack entries: (node, parent_index). parent_index tracks iteration
        # progress through adj[node].
        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = GRAY
        while stack:
            node, idx = stack[-1]
            parents = adj.get(node, [])
            if idx < len(parents):
                stack[-1] = (node, idx + 1)
                parent = parents[idx]
                if color[parent] == GRAY:
                    dropped.append((node, parent))
                elif color[parent] == WHITE:
                    accepted.append((node, parent))
                    color[parent] = GRAY
                    stack.append((parent, 0))
                else:  # BLACK
                    accepted.append((node, parent))
            else:
                color[node] = BLACK
                stack.pop()

    return accepted, dropped
