# Labels Navigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the "labels" page configurable via `index.toml` and merge the list/graph views into a single page with a segmented control toggle.

**Architecture:** The Header already renders navigation from `config.pages`. We add `"labels"` as a special page ID (like `"timeline"`) that maps to `/labels`. The separate `LabelListPage` and `LabelGraphPage` merge into one `LabelsPage` with a local state toggle. The `/labels/graph` route is removed.

**Tech Stack:** React, react-router-dom, Zustand, Tailwind CSS, Vitest, @testing-library/react

---

### Task 1: Update Header to support `labels` as a config-driven page

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`
- Modify: `frontend/src/components/layout/__tests__/Header.test.tsx`

**Step 1: Update Header test fixture and write failing tests**

In `frontend/src/components/layout/__tests__/Header.test.tsx`:

1. Update `siteConfig` fixture to include the labels page:

```typescript
const siteConfig: SiteConfigResponse = {
  title: 'My Blog',
  description: 'A test blog',
  pages: [
    { id: 'timeline', title: 'Posts', file: null },
    { id: 'labels', title: 'Labels', file: null },
  ],
}
```

2. Remove the tests `'Labels NOT active at /labels/graph'` and `'Graph active at /labels/graph'` — these routes no longer exist.

3. Update the `'Labels active at /labels'` test to find the link via the config-rendered tabs (it should still pass with the same assertion, since Labels is now in the pages array).

4. Keep the `'Labels active at /labels/swe'` test — the Header should highlight Labels when on any `/labels/*` sub-path.

**Step 2: Run tests to verify they fail**

Run: `cd /Users/lukasz/dev/agblogger && npx vitest run frontend/src/components/layout/__tests__/Header.test.tsx`
Expected: Tests fail because Header still renders hard-coded Labels/Graph links and the siteConfig fixture changed.

**Step 3: Update Header component**

In `frontend/src/components/layout/Header.tsx`:

1. Remove the two hard-coded `<Link>` elements for Labels and Graph (lines 127-146).

2. Update the page-rendering `map` to handle the `"labels"` special ID. The path mapping logic becomes:

```typescript
const path =
  page.id === 'timeline' ? '/' :
  page.id === 'labels' ? '/labels' :
  `/page/${page.id}`
```

3. Update the `isActive` logic to handle labels:

```typescript
const isActive =
  page.id === 'timeline'
    ? location.pathname === '/'
    : page.id === 'labels'
      ? location.pathname === '/labels' || location.pathname.startsWith('/labels/')
      : location.pathname === path
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/lukasz/dev/agblogger && npx vitest run frontend/src/components/layout/__tests__/Header.test.tsx`
Expected: All tests pass.

**Step 5: Commit**

```
feat: make labels a config-driven nav page in Header
```

---

### Task 2: Create unified LabelsPage with segmented control

**Files:**
- Create: `frontend/src/pages/LabelsPage.tsx`

**Step 1: Write the LabelsPage component**

Create `frontend/src/pages/LabelsPage.tsx` that:

1. Has a `view` state: `'list' | 'graph'`, defaulting to `'list'`.
2. Renders a header row with the label icon + "Labels" title on the left, and a segmented control on the right.
3. The segmented control is two buttons ("List" and "Graph") inside a rounded pill container. The active button has a filled background (`bg-accent text-white`), the inactive one is transparent.
4. Below the header, conditionally renders the list view content (from current `LabelListPage`) or the graph view content (from current `LabelGraphPage`).

The segmented control markup:

```tsx
<div className="flex items-center bg-paper-warm rounded-lg p-0.5 border border-border">
  <button
    onClick={() => setView('list')}
    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
      view === 'list'
        ? 'bg-accent text-white shadow-sm'
        : 'text-muted hover:text-ink'
    }`}
  >
    List
  </button>
  <button
    onClick={() => setView('graph')}
    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
      view === 'graph'
        ? 'bg-accent text-white shadow-sm'
        : 'text-muted hover:text-ink'
    }`}
  >
    Graph
  </button>
</div>
```

For the **list view**: Extract the body of `LabelListPage` (the loading/error/grid logic) into this component. The data fetching (`fetchLabels`) stays the same.

For the **graph view**: Import `LabelGraphPage` directly and render it inline. Since `LabelGraphPage` is a self-contained component with its own data fetching, it can be rendered as-is. However, remove the duplicate page title/header from `LabelGraphPage` — its header bar already says "Label Graph" with a search field. Keep that header bar as the graph's internal chrome, it works well within the unified page.

**Step 2: Run linter/type check**

Run: `cd /Users/lukasz/dev/agblogger && npx tsc --noEmit`
Expected: No type errors.

**Step 3: Commit**

```
feat: add unified LabelsPage with list/graph segmented control
```

---

### Task 3: Update routes and remove old pages

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Update App.tsx routes**

1. Replace imports: remove `LabelListPage` and `LabelGraphPage`, add `LabelsPage`.
2. Replace the two route entries:
   ```tsx
   // Remove these:
   <Route path="/labels" element={<LabelListPage />} />
   <Route path="/labels/graph" element={<LabelGraphPage />} />

   // Add this:
   <Route path="/labels" element={<LabelsPage />} />
   ```
3. Keep `/labels/:labelId/settings` and `/labels/:labelId` routes as-is.

**Step 2: Delete old LabelListPage**

Delete `frontend/src/pages/LabelListPage.tsx` — its content is now in `LabelsPage`.

Keep `frontend/src/pages/LabelGraphPage.tsx` — it's still imported by `LabelsPage` as the graph view component.

**Step 3: Run type check**

Run: `cd /Users/lukasz/dev/agblogger && npx tsc --noEmit`
Expected: No type errors.

**Step 4: Commit**

```
refactor: route /labels to unified LabelsPage, remove LabelListPage
```

---

### Task 4: Update `content/index.toml`

**Files:**
- Modify: `content/index.toml`

**Step 1: Add labels page entry**

Add a `[[pages]]` entry after the existing ones:

```toml
[[pages]]
id = "labels"
title = "Labels"
```

**Step 2: Commit**

```
feat: add labels to site navigation in index.toml
```

---

### Task 5: Run full check and browser test

**Step 1: Run `just check`**

Run: `cd /Users/lukasz/dev/agblogger && just check`
Expected: All type checks, linting, format checks, and tests pass.

**Step 2: Fix any issues**

If any tests fail (especially Header tests that reference the old Graph link), fix them.

**Step 3: Start dev server and browser test**

Run: `cd /Users/lukasz/dev/agblogger && just start`

Verify in browser:
1. The nav bar shows "Posts", "About", "Labels" tabs (no separate "Graph" tab).
2. Click "Labels" — see the label tiles with a segmented control (List | Graph).
3. Click "Graph" in the segmented control — see the graph view.
4. Click "List" — see the tile grid again.
5. Navigate to a label (e.g., click a tile) — the Labels tab stays highlighted.
6. Navigate back to `/labels` — returns to list view.

Run: `cd /Users/lukasz/dev/agblogger && just stop`

**Step 4: Update ARCHITECTURE.md**

Update the routing table in `docs/ARCHITECTURE.md` to reflect:
- `/labels` now shows `LabelsPage` with list/graph toggle (remove the separate `/labels/graph` row).

**Step 5: Final commit**

```
docs: update ARCHITECTURE.md for unified labels page
```
