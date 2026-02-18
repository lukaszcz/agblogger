# Multi-Parent Labels Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable labels to have multiple parents in the DAG, with cycle detection at both API and cache-rebuild levels, plus frontend editing in the label settings page and graph page.

**Architecture:** Backend already supports multi-parent at the DB/service/response level. We add `break_cycles()` for O(V+E) batch cycle detection during cache rebuild, `would_create_cycle()` CTE for per-edge API validation, PUT/DELETE label endpoints, and frontend label settings + graph editing pages.

**Tech Stack:** Python/FastAPI, SQLAlchemy, SQLite recursive CTEs, React 19, React Flow, Zustand, Vitest

---

### Task 1: `break_cycles()` — batch cycle detection

**Files:**
- Create: `backend/services/dag.py`
- Test: `tests/test_labels/test_label_dag.py`

**Step 1: Write failing tests for `break_cycles()`**

Add to `tests/test_labels/test_label_dag.py`:

```python
from backend.services.dag import break_cycles


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
        # All accepted edges must form a DAG
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
        # a -> b, a -> c, b -> d, c -> d (diamond, no cycle)
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
    from collections import defaultdict, deque

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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_labels/test_label_dag.py::TestBreakCycles -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.dag'`

**Step 3: Implement `break_cycles()`**

Create `backend/services/dag.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_labels/test_label_dag.py::TestBreakCycles -v`
Expected: All PASS

**Step 5: Commit**

```
feat: add break_cycles() for O(V+E) batch DAG enforcement
```

---

### Task 2: Integrate `break_cycles()` into cache rebuild

**Files:**
- Modify: `backend/services/cache_service.py:23-66` (the `rebuild_cache` function)

**Step 1: Write failing test for cycle-safe cache rebuild**

Add to `tests/test_labels/test_label_dag.py`:

```python
import json
from pathlib import Path

from backend.filesystem.content_manager import ContentManager
from backend.models.label import LabelCache, LabelParentCache
from backend.services.cache_service import ensure_tables, rebuild_cache
from sqlalchemy import select


class TestCacheCycleEnforcement:
    async def test_rebuild_cache_drops_cyclic_edges(
        self, db_session: AsyncSession, tmp_content_dir: Path
    ) -> None:
        # Write labels.toml with a cycle: a -> b -> c -> a
        (tmp_content_dir / "labels.toml").write_text(
            '[labels]\n'
            '[labels.a]\nnames = ["A"]\nparent = "#b"\n'
            '[labels.b]\nnames = ["B"]\nparent = "#c"\n'
            '[labels.c]\nnames = ["C"]\nparent = "#a"\n'
        )
        await ensure_tables(db_session)
        cm = ContentManager(tmp_content_dir)
        warnings = await rebuild_cache(db_session, cm)

        # All 3 labels should exist
        result = await db_session.execute(select(LabelCache))
        labels = {r.id for r in result.scalars().all()}
        assert labels == {"a", "b", "c"}

        # At least one edge should have been dropped
        edge_result = await db_session.execute(select(LabelParentCache))
        edges = [(e.label_id, e.parent_id) for e in edge_result.scalars().all()]
        assert len(edges) == 2  # 3 edges - 1 dropped = 2

    async def test_rebuild_cache_returns_warnings(
        self, db_session: AsyncSession, tmp_content_dir: Path
    ) -> None:
        (tmp_content_dir / "labels.toml").write_text(
            '[labels]\n'
            '[labels.x]\nnames = ["X"]\nparent = "#y"\n'
            '[labels.y]\nnames = ["Y"]\nparent = "#x"\n'
        )
        await ensure_tables(db_session)
        cm = ContentManager(tmp_content_dir)
        warnings = await rebuild_cache(db_session, cm)
        assert len(warnings) == 1
        assert "#x" in warnings[0] or "#y" in warnings[0]

    async def test_rebuild_cache_no_warnings_when_no_cycles(
        self, db_session: AsyncSession, tmp_content_dir: Path
    ) -> None:
        (tmp_content_dir / "labels.toml").write_text(
            '[labels]\n'
            '[labels.cs]\nnames = ["CS"]\n'
            '[labels.swe]\nnames = ["SWE"]\nparent = "#cs"\n'
        )
        await ensure_tables(db_session)
        cm = ContentManager(tmp_content_dir)
        warnings = await rebuild_cache(db_session, cm)
        assert warnings == []
```

Note: these tests need `AsyncSession` import — add `from sqlalchemy.ext.asyncio import AsyncSession` at top.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_labels/test_label_dag.py::TestCacheCycleEnforcement -v`
Expected: FAIL — `rebuild_cache` returns `int`, not warnings list

**Step 3: Modify `rebuild_cache()` to use `break_cycles()` and return warnings**

In `backend/services/cache_service.py`:

1. Change return type from `int` to `tuple[int, list[str]]` (post count + warnings).
2. Import `break_cycles` from `backend.services.dag`.
3. Replace the direct edge insertion loop (lines 56-64) with:

```python
    # Collect all edges and run cycle detection
    all_edges: list[tuple[str, str]] = []
    for label_id, label_def in labels_config.items():
        for parent_id in label_def.parents:
            # Ensure parent exists
            if parent_id not in labels_config:
                parent_label = LabelCache(id=parent_id, names="[]", is_implicit=True)
                session.add(parent_label)
                await session.flush()
            all_edges.append((label_id, parent_id))

    accepted_edges, dropped_edges = break_cycles(all_edges)
    warnings: list[str] = []
    for child, parent in dropped_edges:
        msg = f"Cycle detected: dropped edge #{child} → #{parent}"
        logger.warning(msg)
        warnings.append(msg)

    for label_id, parent_id in accepted_edges:
        edge = LabelParentCache(label_id=label_id, parent_id=parent_id)
        session.add(edge)
```

4. Change the return statement to `return post_count, warnings`.

**Step 4: Fix all callers of `rebuild_cache()`**

- `backend/main.py` — lifespan handler calls `rebuild_cache()`. Change to `post_count, warnings = await rebuild_cache(...)`. Log warnings (already handled inside `rebuild_cache`).
- `backend/api/sync.py:171` — `sync_commit` calls `rebuild_cache()`. Capture warnings for the response.

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_labels/test_label_dag.py::TestCacheCycleEnforcement -v`
Expected: All PASS

**Step 6: Run full test suite to check nothing broke**

Run: `uv run pytest tests/ -v`
Expected: All existing tests pass (callers updated)

**Step 7: Commit**

```
feat: integrate break_cycles() into cache rebuild with warnings
```

---

### Task 3: Add warnings to sync commit response

**Files:**
- Modify: `backend/api/sync.py:67-72` (`SyncCommitResponse`)
- Modify: `backend/api/sync.py:154-176` (`sync_commit` endpoint)

**Step 1: Write failing test**

Add to `tests/test_api/test_api_integration.py` (inside `TestLabelCRUD` or a new class):

```python
class TestSyncCycleWarnings:
    @pytest.mark.asyncio
    async def test_sync_commit_returns_cycle_warnings(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload a labels.toml with cycles
        cyclic_toml = (
            '[labels]\n'
            '[labels.a]\nnames = ["A"]\nparent = "#b"\n'
            '[labels.b]\nnames = ["B"]\nparent = "#a"\n'
        )
        import io
        resp = await client.post(
            "/api/sync/upload",
            data={"file_path": "labels.toml"},
            files={"file": ("labels.toml", io.BytesIO(cyclic_toml.encode()), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        # Commit sync
        resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data
        assert len(data["warnings"]) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestSyncCycleWarnings -v`
Expected: FAIL — `warnings` not in response

**Step 3: Implement**

In `backend/api/sync.py`:

1. Add `warnings: list[str] = []` field to `SyncCommitResponse`.
2. In `sync_commit`, capture warnings from `rebuild_cache`:
   ```python
   _post_count, warnings = await rebuild_cache(session, content_manager)
   return SyncCommitResponse(status="ok", files_synced=len(current_files), warnings=warnings)
   ```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestSyncCycleWarnings -v`
Expected: PASS

**Step 5: Commit**

```
feat: return cycle warnings in sync commit response
```

---

### Task 4: `would_create_cycle()` — per-edge CTE validation

**Files:**
- Modify: `backend/services/label_service.py`
- Create: `tests/test_labels/test_label_service.py`

**Step 1: Write failing tests**

Create `tests/test_labels/test_label_service.py`:

```python
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

        # swe -> cs is fine (no existing edges)
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_labels/test_label_service.py -v`
Expected: FAIL — `would_create_cycle` not found

**Step 3: Implement `would_create_cycle()`**

Add to `backend/services/label_service.py`:

```python
async def would_create_cycle(
    session: AsyncSession, label_id: str, proposed_parent_id: str,
) -> bool:
    """Check if adding label_id -> proposed_parent_id would create a cycle.

    Returns True if proposed_parent_id is already a descendant of label_id
    (or is label_id itself), meaning the edge would close a cycle.
    """
    if label_id == proposed_parent_id:
        return True

    stmt = text("""
        WITH RECURSIVE ancestors(id) AS (
            SELECT :proposed_parent_id
            UNION ALL
            SELECT lp.parent_id
            FROM label_parents_cache lp
            JOIN ancestors a ON lp.label_id = a.id
        )
        SELECT 1 FROM ancestors WHERE id = :label_id LIMIT 1
    """)
    result = await session.execute(
        stmt, {"proposed_parent_id": proposed_parent_id, "label_id": label_id}
    )
    return result.first() is not None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_labels/test_label_service.py -v`
Expected: All PASS

**Step 5: Commit**

```
feat: add would_create_cycle() CTE for per-edge validation
```

---

### Task 5: Label update and delete API endpoints

**Files:**
- Modify: `backend/schemas/label.py` (add `LabelUpdate`, `LabelDeleteResponse`, extend `LabelCreate`)
- Modify: `backend/services/label_service.py` (add `update_label`, `delete_label`)
- Modify: `backend/api/labels.py` (add PUT, DELETE endpoints)

**Step 1: Write failing tests**

Add to `tests/test_api/test_api_integration.py` inside `TestLabelCRUD`:

```python
    async def test_update_label_parents(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create parent labels
        await client.post("/api/labels", json={"id": "math"}, headers=headers)
        await client.post("/api/labels", json={"id": "physics"}, headers=headers)

        # Create child with one parent
        await client.post(
            "/api/labels",
            json={"id": "quantum", "parents": ["math"]},
            headers=headers,
        )
        resp = await client.get("/api/labels/quantum")
        assert resp.json()["parents"] == ["math"]

        # Update to have two parents
        resp = await client.put(
            "/api/labels/quantum",
            json={"names": ["quantum mechanics"], "parents": ["math", "physics"]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["parents"]) == {"math", "physics"}
        assert data["names"] == ["quantum mechanics"]

    async def test_update_label_cycle_returns_409(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/labels", json={"id": "top"}, headers=headers)
        await client.post(
            "/api/labels", json={"id": "bottom", "parents": ["top"]}, headers=headers,
        )

        # Try to make top a child of bottom (cycle)
        resp = await client.put(
            "/api/labels/top",
            json={"names": ["top"], "parents": ["bottom"]},
            headers=headers,
        )
        assert resp.status_code == 409

    async def test_update_label_nonexistent_parent_returns_404(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/labels", json={"id": "orphan"}, headers=headers)
        resp = await client.put(
            "/api/labels/orphan",
            json={"names": ["orphan"], "parents": ["nonexistent"]},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_delete_label(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/labels", json={"id": "temp"}, headers=headers)
        resp = await client.delete("/api/labels/temp", headers=headers)
        assert resp.status_code == 200

        resp = await client.get("/api/labels/temp")
        assert resp.status_code == 404

    async def test_delete_label_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.delete("/api/labels/swe")
        assert resp.status_code == 401

    async def test_update_label_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/api/labels/swe",
            json={"names": ["swe"], "parents": []},
        )
        assert resp.status_code == 401

    async def test_create_label_with_parents(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/labels",
            json={"id": "new-child", "names": ["new child"], "parents": ["cs"]},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["parents"] == ["cs"]
        assert data["names"] == ["new child"]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestLabelCRUD -v`
Expected: Multiple failures (no PUT/DELETE endpoints, LabelCreate has no parents field)

**Step 3: Update schemas**

In `backend/schemas/label.py`, add:

```python
class LabelCreate(BaseModel):
    """Request to create a new label."""

    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    names: list[str] = Field(default_factory=list)
    parents: list[str] = Field(default_factory=list)


class LabelUpdate(BaseModel):
    """Request to update a label's names and parents."""

    names: list[str] = Field(default_factory=list)
    parents: list[str] = Field(default_factory=list)


class LabelDeleteResponse(BaseModel):
    """Response after deleting a label."""

    id: str
    deleted: bool = True
```

**Step 4: Add service functions**

In `backend/services/label_service.py`, add `update_label()` and `delete_label()`:

```python
async def update_label(
    session: AsyncSession, label_id: str, names: list[str], parents: list[str],
) -> LabelResponse | None:
    """Update a label's names and parent edges. Returns None if not found."""
    label = await session.get(LabelCache, label_id)
    if label is None:
        return None

    # Update names
    label.names = json.dumps(names)

    # Replace parent edges: delete old, insert new
    await session.execute(
        delete(LabelParentCache).where(LabelParentCache.label_id == label_id)
    )
    await session.flush()

    for parent_id in parents:
        edge = LabelParentCache(label_id=label_id, parent_id=parent_id)
        session.add(edge)
    await session.flush()

    return await get_label(session, label_id)


async def delete_label(session: AsyncSession, label_id: str) -> bool:
    """Delete a label and all its edges. Returns False if not found."""
    label = await session.get(LabelCache, label_id)
    if label is None:
        return False

    await session.delete(label)
    await session.flush()
    return True
```

Add `from sqlalchemy import delete` to imports.

**Step 5: Add API endpoints**

In `backend/api/labels.py`, add the PUT and DELETE endpoints, and update `create_label_endpoint` to handle `names` and `parents`:

```python
@router.put("/{label_id}", response_model=LabelResponse)
async def update_label_endpoint(
    label_id: str,
    body: LabelUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> LabelResponse:
    """Update a label's names and parents."""
    # Check label exists
    existing = await get_label(session, label_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Label not found")

    # Validate parents exist
    for parent_id in body.parents:
        parent = await get_label(session, parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail=f"Parent label '{parent_id}' not found")

    # Cycle detection per proposed parent
    for parent_id in body.parents:
        if await would_create_cycle_for_update(session, label_id, body.parents):
            raise HTTPException(status_code=409, detail="Adding parent would create a cycle")
            break

    result = await update_label(session, label_id, body.names, body.parents)

    # Persist to labels.toml
    labels = dict(content_manager.labels)
    if label_id in labels:
        labels[label_id] = LabelDef(
            id=label_id, names=body.names, parents=body.parents,
        )
    else:
        labels[label_id] = LabelDef(
            id=label_id, names=body.names, parents=body.parents,
        )
    write_labels_config(content_manager.content_dir, labels)
    content_manager.reload_config()

    await session.commit()
    return result
```

For the cycle check in update: since we're replacing all parents at once, temporarily remove the label's existing edges, then check each proposed parent:

```python
async def would_create_cycle_for_update(
    session: AsyncSession, label_id: str, proposed_parents: list[str],
) -> bool:
    """Check if replacing label's parents with proposed_parents would create a cycle.

    Temporarily removes existing edges for label_id before checking.
    """
    # Delete existing edges for this label (they'll be re-added or replaced)
    await session.execute(
        delete(LabelParentCache).where(LabelParentCache.label_id == label_id)
    )
    await session.flush()

    for parent_id in proposed_parents:
        if await would_create_cycle(session, label_id, parent_id):
            return True
    return False
```

Note: This function modifies the session state. If it returns True, the caller must rollback or not commit. The PUT endpoint should handle this.

Actually, a cleaner approach: delete edges, check, then either add new edges or rollback. The update endpoint should use a nested transaction or handle the flow correctly. Use the existing `update_label` service function which already deletes and re-adds edges — just do the cycle check after deleting old edges but before adding new ones.

Refactor: Move cycle validation into `update_label()` in the service layer. Have it delete old edges, check each new parent with `would_create_cycle()`, and either proceed or raise a `ValueError`. The API endpoint catches `ValueError` and returns 409.

**Step 6: Update create endpoint**

Update `create_label_endpoint` to pass `names` and `parents` from `LabelCreate` to the service, including cycle checks and parent validation.

**Step 7: Add DELETE endpoint**

```python
@router.delete("/{label_id}", response_model=LabelDeleteResponse)
async def delete_label_endpoint(
    label_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> LabelDeleteResponse:
    """Delete a label."""
    deleted = await delete_label(session, label_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Label not found")

    # Remove from labels.toml
    labels = dict(content_manager.labels)
    labels.pop(label_id, None)
    write_labels_config(content_manager.content_dir, labels)
    content_manager.reload_config()

    await session.commit()
    return LabelDeleteResponse(id=label_id)
```

**Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestLabelCRUD -v`
Expected: All PASS

**Step 9: Run full backend test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 10: Commit**

```
feat: add label update, delete, and create-with-parents API endpoints
```

---

### Task 6: Frontend API client additions

**Files:**
- Modify: `frontend/src/api/labels.ts`
- Modify: `frontend/src/api/client.ts` (add `LabelDeleteResponse`)

**Step 1: Add types and API functions**

In `frontend/src/api/client.ts`, add:

```typescript
export interface LabelDeleteResponse {
  id: string
  deleted: boolean
}
```

In `frontend/src/api/labels.ts`, update `createLabel` and add `updateLabel`, `deleteLabel`:

```typescript
export async function createLabel(
  id: string,
  names?: string[],
  parents?: string[],
): Promise<LabelResponse> {
  return api
    .post('labels', { json: { id, ...(names && { names }), ...(parents && { parents }) } })
    .json<LabelResponse>()
}

export async function updateLabel(
  labelId: string,
  data: { names: string[]; parents: string[] },
): Promise<LabelResponse> {
  return api.put(`labels/${labelId}`, { json: data }).json<LabelResponse>()
}

export async function deleteLabel(labelId: string): Promise<LabelDeleteResponse> {
  return api.delete(`labels/${labelId}`).json<LabelDeleteResponse>()
}
```

**Step 2: Commit**

```
feat: add updateLabel and deleteLabel API client functions
```

---

### Task 7: Label settings page

**Files:**
- Create: `frontend/src/pages/LabelSettingsPage.tsx`
- Modify: `frontend/src/App.tsx` (add route)
- Modify: `frontend/src/pages/LabelPostsPage.tsx` (add gear icon link)
- Modify: `frontend/src/pages/LabelListPage.tsx` (add edit icon, pluralize "Parents")

**Context:** Use the `frontend-design` skill to design this page. It needs:
- Editable list of display names (add/remove)
- Multi-select combobox for parents (all labels except self and descendants)
- Save button (calls `updateLabel`)
- Delete button with confirmation dialog (calls `deleteLabel`)
- Navigation back to label posts page
- Auth required — redirect to login if not authenticated
- Disable controls while async operations are in flight

**Step 1: Create `LabelSettingsPage.tsx`**

Use `frontend-design` skill for implementation. The page should:
- Fetch label detail and all labels on mount
- Filter out self and descendants from parent options (use BFS on the `children` field from `LabelResponse`)
- Show names as editable chips with an add input
- Show parents as a multi-select from filtered options
- Save and Delete buttons at bottom

**Step 2: Add route to `App.tsx`**

Add before the `/:labelId` route (more specific routes first):

```typescript
<Route path="/labels/:labelId/settings" element={<LabelSettingsPage />} />
```

**Step 3: Add settings link to `LabelPostsPage.tsx`**

For authenticated users, show a gear icon next to the label title linking to `/labels/${labelId}/settings`.

**Step 4: Update `LabelListPage.tsx`**

- Change `<span>Parent:</span>` to dynamically show "Parent:" vs "Parents:" based on `label.parents.length`.
- Add an edit icon on each card for authenticated users.

**Step 5: Write frontend tests**

Create `frontend/src/pages/__tests__/LabelSettingsPage.test.tsx`:
- Test that it renders label names and parent chips
- Test that save calls updateLabel with correct data
- Test that delete shows confirmation and calls deleteLabel

**Step 6: Commit**

```
feat: add label settings page with names and parents editing
```

---

### Task 8: Graph page edge editing with client-side cycle detection

**Files:**
- Modify: `frontend/src/pages/LabelGraphPage.tsx`

**Context:** Use the `frontend-design` skill for the UI updates. The graph page needs:

1. **`isValidConnection` callback** — given a connection attempt (source → target, meaning target becomes parent of source), run BFS from source following existing parent edges in the graph data. If target is found as a descendant of source, return false (would create cycle). Also block self-connections.

2. **`onConnect` callback** — when authenticated, call `updateLabel(sourceId, { names: currentNames, parents: [...currentParents, targetId] })`. Show dashed/animated edge while in flight. On 409 error, show error toast. On success, refetch graph.

3. **Edge deletion** — on edge click or right-click, show a delete option. Call `updateLabel(childId, { names: currentNames, parents: currentParents.filter(p => p !== parentId) })`. On success, refetch graph.

4. **Auth check** — only enable editing when authenticated (import `useAuthStore`).

**Step 1: Add cycle detection utility**

```typescript
function wouldCreateCycle(
  graphData: LabelGraphResponse,
  childId: string,
  proposedParentId: string,
): boolean {
  if (childId === proposedParentId) return true
  // BFS: check if proposedParentId is a descendant of childId
  const children = new Map<string, string[]>()
  for (const e of graphData.edges) {
    if (!children.has(e.target)) children.set(e.target, [])
    children.get(e.target)!.push(e.source)
  }
  const visited = new Set<string>()
  const queue = [childId]
  while (queue.length > 0) {
    const node = queue.shift()!
    if (node === proposedParentId) return true
    if (visited.has(node)) continue
    visited.add(node)
    for (const child of children.get(node) ?? []) {
      queue.push(child)
    }
  }
  return false
}
```

**Step 2: Wire up React Flow callbacks**

- `isValidConnection`: call `wouldCreateCycle()` with graph data
- `onConnect`: call `updateLabel()` API, show loading state, refetch
- Edge click handler: offer delete, call `updateLabel()` to remove parent

**Step 3: Write frontend test**

Create `frontend/src/pages/__tests__/LabelGraphPage.test.tsx`:
- Test `wouldCreateCycle` utility with cycle and non-cycle cases

**Step 4: Commit**

```
feat: add graph page edge editing with client-side cycle detection
```

---

### Task 9: Final integration testing and cleanup

**Files:**
- Modify: `docs/ARCHITECTURE.md` (update for multi-parent support)

**Step 1: Run full check suite**

Run: `just check`
Expected: All type checking, linting, formatting, and tests pass.

**Step 2: Manual browser testing**

Use playwright MCP to verify:
1. Create labels with multiple parents via settings page
2. Add/remove parent edges on graph page
3. Verify cycle prevention works in both settings and graph
4. Verify sync with cyclic labels.toml shows warnings

**Step 3: Update ARCHITECTURE.md**

Update the Label DAG section to reflect multi-parent support. Update the TOML example to show `parents = [...]` syntax. Update the API routes table to include PUT and DELETE label endpoints.

**Step 4: Commit**

```
docs: update architecture for multi-parent labels
```
