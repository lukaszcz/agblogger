"""Label service: DAG operations and queries."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text

from backend.models.label import LabelCache, LabelParentCache, PostLabelCache
from backend.schemas.label import (
    LabelGraphEdge,
    LabelGraphNode,
    LabelGraphResponse,
    LabelResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_all_labels(session: AsyncSession) -> list[LabelResponse]:
    """Get all labels with parent/child info and post counts."""
    # Get all labels
    stmt = select(LabelCache)
    result = await session.execute(stmt)
    labels = result.scalars().all()

    # Batch: get all parent relationships in one query
    parent_stmt = select(LabelParentCache)
    parent_result = await session.execute(parent_stmt)
    all_parents = parent_result.scalars().all()

    parents_map: dict[str, list[str]] = {}
    children_map: dict[str, list[str]] = {}
    for rel in all_parents:
        parents_map.setdefault(rel.label_id, []).append(rel.parent_id)
        children_map.setdefault(rel.parent_id, []).append(rel.label_id)

    # Batch: get all post counts in one query
    count_stmt = select(PostLabelCache.label_id, func.count()).group_by(PostLabelCache.label_id)
    count_result = await session.execute(count_stmt)
    post_counts: dict[str, int] = {row[0]: row[1] for row in count_result.all()}

    responses: list[LabelResponse] = []
    for label in labels:
        responses.append(
            LabelResponse(
                id=label.id,
                names=json.loads(label.names),
                is_implicit=label.is_implicit,
                parents=parents_map.get(label.id, []),
                children=children_map.get(label.id, []),
                post_count=post_counts.get(label.id, 0),
            )
        )

    return responses


async def get_label(session: AsyncSession, label_id: str) -> LabelResponse | None:
    """Get a single label by ID."""
    label = await session.get(LabelCache, label_id)
    if label is None:
        return None

    parent_stmt = select(LabelParentCache.parent_id).where(LabelParentCache.label_id == label_id)
    parent_result = await session.execute(parent_stmt)
    parents = [r[0] for r in parent_result.all()]

    child_stmt = select(LabelParentCache.label_id).where(LabelParentCache.parent_id == label_id)
    child_result = await session.execute(child_stmt)
    children = [r[0] for r in child_result.all()]

    count_stmt = (
        select(func.count()).select_from(PostLabelCache).where(PostLabelCache.label_id == label_id)
    )
    count_result = await session.execute(count_stmt)
    post_count = count_result.scalar() or 0

    return LabelResponse(
        id=label.id,
        names=json.loads(label.names),
        is_implicit=label.is_implicit,
        parents=parents,
        children=children,
        post_count=post_count,
    )


async def get_label_descendant_ids(session: AsyncSession, label_id: str) -> list[str]:
    """Get all descendant label IDs using recursive CTE."""
    stmt = text("""
        WITH RECURSIVE descendants(id) AS (
            SELECT :label_id
            UNION ALL
            SELECT lp.label_id
            FROM label_parents_cache lp
            JOIN descendants d ON lp.parent_id = d.id
        )
        SELECT DISTINCT id FROM descendants
    """)
    result = await session.execute(stmt, {"label_id": label_id})
    return [r[0] for r in result.all()]


async def create_label(session: AsyncSession, label_id: str) -> LabelResponse | None:
    """Create a new label. Returns None if it already exists."""
    existing = await session.get(LabelCache, label_id)
    if existing is not None:
        return None

    label = LabelCache(
        id=label_id,
        names=json.dumps([label_id]),
        is_implicit=False,
    )
    session.add(label)
    await session.flush()

    return LabelResponse(
        id=label_id,
        names=[label_id],
        is_implicit=False,
        parents=[],
        children=[],
        post_count=0,
    )


async def get_label_graph(session: AsyncSession) -> LabelGraphResponse:
    """Get the full label DAG for visualization."""
    labels = await get_all_labels(session)

    nodes = [
        LabelGraphNode(
            id=label.id,
            names=label.names,
            post_count=label.post_count,
        )
        for label in labels
    ]

    edge_stmt = select(LabelParentCache)
    edge_result = await session.execute(edge_stmt)
    edges = [
        LabelGraphEdge(source=e.label_id, target=e.parent_id) for e in edge_result.scalars().all()
    ]

    return LabelGraphResponse(nodes=nodes, edges=edges)
