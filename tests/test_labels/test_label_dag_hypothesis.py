"""Property-based tests for label DAG cycle breaking."""

from __future__ import annotations

import string
from collections import Counter

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from backend.services.dag import break_cycles

PROPERTY_SETTINGS = settings(
    max_examples=260,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

_NODE = st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=4)
_EDGE_LIST = st.lists(st.tuples(_NODE, _NODE), max_size=35)


def _is_dag(edges: list[tuple[str, str]]) -> bool:
    adjacency: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for child, parent in edges:
        adjacency.setdefault(child, []).append(parent)
        nodes.add(child)
        nodes.add(parent)

    white, gray, black = 0, 1, 2
    color = {node: white for node in nodes}

    def _visit(node: str) -> bool:
        color[node] = gray
        for parent in adjacency.get(node, []):
            if color[parent] == gray:
                return False
            if color[parent] == white and not _visit(parent):
                return False
        color[node] = black
        return True

    return all(not (color[node] == white and not _visit(node)) for node in list(nodes))


@st.composite
def _acyclic_edges(draw: st.DrawFn) -> list[tuple[str, str]]:
    nodes = draw(st.lists(_NODE, unique=True, min_size=1, max_size=10))
    possible_edges: list[tuple[str, str]] = []
    for child_index in range(len(nodes)):
        for parent_index in range(child_index):
            possible_edges.append((nodes[child_index], nodes[parent_index]))
    assume(possible_edges)
    return draw(
        st.lists(
            st.sampled_from(possible_edges),
            unique=True,
            max_size=min(25, len(possible_edges)),
        )
    )


class TestBreakCyclesProperties:
    @PROPERTY_SETTINGS
    @given(edges=_EDGE_LIST)
    def test_output_partitions_input_multiset_and_accepts_are_acyclic(
        self,
        edges: list[tuple[str, str]],
    ) -> None:
        accepted, dropped = break_cycles(edges)

        assert Counter(accepted) + Counter(dropped) == Counter(edges)
        assert _is_dag(accepted)

    @PROPERTY_SETTINGS
    @given(edges=_EDGE_LIST)
    def test_breaking_cycles_is_idempotent_on_accepted_graph(
        self,
        edges: list[tuple[str, str]],
    ) -> None:
        accepted, _dropped = break_cycles(edges)
        accepted_again, dropped_again = break_cycles(accepted)

        assert Counter(accepted_again) == Counter(accepted)
        assert dropped_again == []

    @PROPERTY_SETTINGS
    @given(edges=_acyclic_edges())
    def test_no_edges_are_dropped_for_acyclic_input(self, edges: list[tuple[str, str]]) -> None:
        accepted, dropped = break_cycles(edges)

        assert dropped == []
        assert Counter(accepted) == Counter(edges)
