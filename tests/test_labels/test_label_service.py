"""Tests for label service cycle detection."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.models.label import LabelCache, LabelParentCache
from backend.services.cache_service import ensure_tables
from backend.services.label_service import would_create_cycle

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestWouldCreateCycle:
    async def test_no_cycle_simple(self, db_session: AsyncSession) -> None:
        await ensure_tables(db_session)
        db_session.add(LabelCache(id="cs", names=json.dumps(["CS"])))
        db_session.add(LabelCache(id="swe", names=json.dumps(["SWE"])))
        await db_session.flush()

        assert not await would_create_cycle(db_session, "swe", "cs")

    async def test_direct_cycle(self, db_session: AsyncSession) -> None:
        await ensure_tables(db_session)
        db_session.add(LabelCache(id="a", names="[]"))
        db_session.add(LabelCache(id="b", names="[]"))
        db_session.add(LabelParentCache(label_id="a", parent_id="b"))
        await db_session.flush()

        # b -> a would create cycle (a already has parent b)
        assert await would_create_cycle(db_session, "b", "a")

    async def test_indirect_cycle(self, db_session: AsyncSession) -> None:
        await ensure_tables(db_session)
        db_session.add(LabelCache(id="a", names="[]"))
        db_session.add(LabelCache(id="b", names="[]"))
        db_session.add(LabelCache(id="c", names="[]"))
        db_session.add(LabelParentCache(label_id="a", parent_id="b"))
        db_session.add(LabelParentCache(label_id="b", parent_id="c"))
        await db_session.flush()

        # c -> a would create cycle (a -> b -> c already exists)
        assert await would_create_cycle(db_session, "c", "a")

    async def test_self_loop(self, db_session: AsyncSession) -> None:
        await ensure_tables(db_session)
        db_session.add(LabelCache(id="a", names="[]"))
        await db_session.flush()

        assert await would_create_cycle(db_session, "a", "a")

    async def test_multi_parent_no_cycle(self, db_session: AsyncSession) -> None:
        await ensure_tables(db_session)
        for lid in ["a", "b", "c", "d"]:
            db_session.add(LabelCache(id=lid, names="[]"))
        db_session.add(LabelParentCache(label_id="a", parent_id="b"))
        db_session.add(LabelParentCache(label_id="a", parent_id="c"))
        db_session.add(LabelParentCache(label_id="b", parent_id="d"))
        await db_session.flush()

        # c -> d is fine (diamond shape, no cycle)
        assert not await would_create_cycle(db_session, "c", "d")

    async def test_no_existing_edges(self, db_session: AsyncSession) -> None:
        await ensure_tables(db_session)
        db_session.add(LabelCache(id="x", names="[]"))
        db_session.add(LabelCache(id="y", names="[]"))
        await db_session.flush()

        assert not await would_create_cycle(db_session, "x", "y")
        assert not await would_create_cycle(db_session, "y", "x")
