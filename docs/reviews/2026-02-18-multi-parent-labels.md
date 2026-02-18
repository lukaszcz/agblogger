# Review: Multi-Parent Labels with Cycle Detection

**Date:** 2026-02-18
**Scope:** 8 commits (`a4278a6..2f15306`), 18 files, ~1300 lines added
**Reviewers:** code-reviewer, test-analyzer, silent-failure-hunter, comment-analyzer, type-design-analyzer

## Summary

Implements multi-parent label DAG with cycle detection (batch DFS + recursive CTE), label CRUD API, label settings page, and graph edge editing. All linting, type checking, and tests pass (164 backend + 1 frontend). The two-level cycle detection approach is correct and well-tested.

## Critical Issues (3)

### 1. `delete_label` leaves stale parent references in `labels.toml`

`backend/api/labels.py:155` — When deleting a label, it's removed from `labels.toml` but references to it in other labels' `parents` lists remain. On next cache rebuild, the deleted label reappears as an implicit ghost label.

### 2. `LabelUpdate.names` accepts empty list — no server-side validation

`backend/schemas/label.py:52` — `names: list[str] = Field(default_factory=list)` has no `min_length=1`. A direct API call with `{"names": [], "parents": []}` persists a label with no display names to DB and TOML. Frontend prevents this, but backend does not.

### 3. `update_label` names fallback inconsistency between create and update

`backend/api/labels.py:80` uses `body.names if body.names else [body.id]` for the `LabelDef`, but line 126 uses `body.names` directly without fallback. Empty names on update writes `names = []` to TOML.

## Important Issues (6)

### 4. `useCallback` should be `useMemo` for `excludedIds`

`frontend/src/pages/LabelSettingsPage.tsx:76-84` — `excludedIds` is a `useCallback` returning a function, called inline as `excludedIds()` on every render. The BFS recomputes every render. Should be `useMemo`.

### 5. Edge click deletes without confirmation

`frontend/src/pages/LabelGraphPage.tsx:280-304` — Single-clicking an edge immediately deletes the parent relationship with no confirmation dialog. The label settings page has two-step confirmation for delete; graph edge deletion should too.

### 6. `assert` in production code

`backend/api/labels.py:122` — `assert result is not None` would be stripped with `-O` flag and gives a 500 `AssertionError` on a TOCTOU race. Replace with explicit check.

### 7. No validation on parent ID format

`backend/schemas/label.py:46,53` — `parents` fields accept arbitrary strings. `LabelCreate.id` has `pattern=r"^[a-z0-9][a-z0-9-]*$"` but parent IDs have no such constraint.

### 8. Frontend error catch blocks discard error details

`LabelGraphPage.tsx:202`, `LabelListPage.tsx:18`, `LabelPostsPage.tsx:27`, `LabelSettingsPage.tsx:68` — All use `.catch(() => setError('...'))`, discarding the actual error type. `LabelSettingsPage.handleSave` already does this correctly and should be the template.

### 9. Missing test: delete label with edges (cascade verification)

No test deletes a label that has parent and child edges to verify cascade cleanup works correctly.

## Suggestions (7)

### 10. `would_create_cycle` docstring mixes perspectives

Rewrite to match the CTE's ancestor-walking direction. (`label_service.py:192-195`)

### 11. `break_cycles` DFS uses Python recursion

Could hit `RecursionError` on 1000+ label chains. Convert to iterative DFS. (`dag.py:34-44`)

### 12. Extract `LabelNodeData` interface in frontend

The inline `as` cast in `LabelGraphPage.tsx` should reference a named type shared between `layoutGraph` and `LabelNode`.

### 13. Extract TypeScript request types

`LabelCreateRequest` and `LabelUpdateRequest` interfaces should be defined in `client.ts`.

### 14. `LabelGraphEdge` naming confusion

`source`/`target` semantics are inverted between DAG domain and React Flow. Consider `child_id`/`parent_id` in the API schema.

### 15. Missing test: create-label-with-cycle at API level

No `test_create_label_cycle_returns_409` exists, though the code path exists.

### 16. Missing test: multi-parent ancestor cycle detection

No test for `would_create_cycle` where the cycle exists through one branch of a multi-parent graph.

## Strengths

- Sound two-level cycle detection architecture (batch DFS + real-time CTE)
- `break_cycles` docstring is exemplary
- Excellent `handleSave` error differentiation in `LabelSettingsPage.tsx`
- UI controls properly disabled during async operations
- Well-structured three-tier testing: unit (DAG), service (CTE), integration (API)
- `_is_dag` test helper using independent Kahn's algorithm verification
- Filesystem write failures properly caught with session rollback and logging
- Architecture docs kept in sync
