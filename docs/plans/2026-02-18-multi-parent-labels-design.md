# Multi-Parent Labels Design

## Goal

Allow labels to have multiple parents in the DAG. Add backend API endpoints for label CRUD with cycle enforcement, frontend label settings page, and graph-based edge editing.

## Current State

The infrastructure is ~95% multi-parent ready. The database (`LabelParentCache` composite PK), `LabelDef.parents: list[str]`, TOML parser/writer (handles both `parent` and `parents`), cache rebuild (loops over all parents), label service (builds multi-parent maps), API response schema (`parents: list[str]`), and frontend rendering (maps over `parents`) all support multiple parents.

Gaps: no label update/delete API, `LabelCreate` lacks `parents` field, no cycle detection, no frontend label editing UI.

## Backend

### Schemas (`backend/schemas/label.py`)

- `LabelCreate` — add optional `names: list[str]` and `parents: list[str]`
- New `LabelUpdate` — `names: list[str]` and `parents: list[str]`
- New `LabelDeleteResponse` — confirmation with ID

### API Endpoints (`backend/api/labels.py`)

- `POST /api/labels` — extend to accept `names` and `parents`; validate parents exist, cycle check before inserting edges
- `PUT /api/labels/{id}` — update names and parent edges; cycle detection; writes to DB + `labels.toml` + reloads config
- `DELETE /api/labels/{id}` — remove label, edges, post associations from DB + `labels.toml`

### Cycle Detection — Two Code Paths

| Context | Algorithm | Complexity |
|---------|-----------|------------|
| Cache rebuild / sync | DFS with back-edge detection, single pass | O(V+E) total |
| API single-edge additions | Recursive CTE per edge | O(V+E) per operation |

**API (`backend/services/label_service.py`):** `would_create_cycle(session, label_id, proposed_parent_id)` — recursive CTE checking if `label_id` is an ancestor of `proposed_parent_id`. Returns 409 if cycle would result.

**Cache rebuild (`backend/services/cache_service.py`):** `break_cycles(edges)` — DFS with white/gray/black node coloring. When a gray node is encountered, the edge is a back-edge creating a cycle — drop it. Returns `(accepted_edges, dropped_edges)` in a single O(V+E) pass.

### Cache Rebuild Changes

- After parsing `labels.toml`, extract all edges, run `break_cycles()`
- Insert only accepted edges into DB
- Return dropped edges as warnings
- Log: `"Cycle detected: dropped edge #child → #parent"`

### Sync Response

- `rebuild_cache()` returns warnings to sync commit endpoint
- Add `warnings: list[str]` to sync commit response schema
- At startup, log warnings only (no active frontend session)

## Frontend

### Label Settings Page (`/labels/:labelId/settings`)

Auth required. Fields:

- **Names editor** — editable list of display names
- **Parents multi-select** — combobox of existing labels, excluding self and descendants
- **Save** — `PUT /api/labels/{id}`
- **Delete** — confirmation dialog, then `DELETE /api/labels/{id}`

Accessible from `LabelPostsPage` (gear icon) and `LabelListPage` (edit icon) for authenticated users.

### Graph Page Editing (`LabelGraphPage.tsx`)

When authenticated:

- **Add edge:** drag from source handle to target handle (React Flow `onConnect`). Calls `PUT /api/labels/{sourceId}` adding target as parent. Dashed/animated edge while in flight.
- **Delete edge:** right-click or select + Delete key. Calls `PUT /api/labels/{childId}` with parent removed.
- **Client-side cycle detection:** `isValidConnection` runs DFS/BFS from the child following parent edges. If the proposed parent is reachable as a descendant, block the connection with a visual indicator. Backend 409 remains as safety net.
- **Refetch** graph data after any mutation to re-layout.

### LabelListPage Updates

- Pluralize "Parent" → "Parents" when multiple
- Edit icon/link to settings page for authenticated users

### LabelPostsPage Updates

- Settings gear icon for authenticated users
- Show parent labels as clickable chips

### Sync Warnings

After sync commit, if response includes `warnings` (dropped cycle edges), show a toast/banner. Offer "Fix labels.toml?" which persists the acyclic state via `PUT` on affected labels.

### API Client (`frontend/src/api/labels.ts`)

- `updateLabel(id, { names, parents })` — PUT
- `deleteLabel(id)` — DELETE
- Update `createLabel` to accept optional `names` and `parents`

## Testing

### Backend

- `test_label_dag.py` — `break_cycles()`: no cycles, single cycle, multiple cycles, self-loops, diamond+cycle. Verify correct edges dropped.
- `test_api_integration.py` — `PUT /api/labels/{id}` valid parents, cycle rejection (409), nonexistent parent (404). `DELETE`. `POST` with parents.
- `test_sync_service.py` — sync commit returns warnings when `labels.toml` has cycles.
- `test_label_service.py` — `would_create_cycle()` CTE for single-edge validation.

### Frontend

- Label settings page — render, save, delete flows
- Graph page — cycle detection in `isValidConnection`
