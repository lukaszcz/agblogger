# Labels as Configurable Navigation Page

## Problem

The "Labels" and "Graph" tabs are hard-coded in the Header component. Users cannot control whether Labels appears in navigation via `index.toml`, and the graph view feels disconnected as a separate top-level tab.

## Design

### Backend: Special page ID

Add `"labels"` as a recognized special page ID alongside `"timeline"`. When `index.toml` contains a `[[pages]]` entry with `id = "labels"`, the Header renders a Labels nav tab. No `file` field is needed since it is a built-in page.

```toml
[[pages]]
id = "labels"
title = "Labels"
```

No backend code changes are required since `parse_site_config` already accepts arbitrary page IDs. The frontend Header is the only consumer that needs to understand the special ID.

### Frontend: Header

Remove the hard-coded Labels and Graph links. The Header renders only pages from the site config. When a page has `id = "labels"`, its link target is `/labels` (mirroring how `id = "timeline"` maps to `/`). The active state highlights on `/labels` and `/labels/*` paths (except settings pages already navigate away).

### Frontend: Unified Labels Page

Merge `LabelListPage` and `LabelGraphPage` into a single `LabelsPage` component at `/labels`. A segmented control pill toggle (List | Graph) in the page header switches between the two views. View state is local component state, not reflected in the URL. The existing `/labels/graph` route is removed from the router.

```
+----------------------------------------------+
|  Labels                  [ List | Graph ]    |
|                                              |
|  (list view or graph view rendered here)     |
+----------------------------------------------+
```

### What stays the same

- All label CRUD, graph editing, label settings pages and routes
- Backend API endpoints
- `parse_site_config` and `SiteConfig` dataclass
- `LabelPostsPage` and `LabelSettingsPage` routes

### What changes

1. `Header.tsx`: remove hard-coded Labels/Graph links; add `labels` to the special-ID-to-path mapping
2. New unified `LabelsPage` component with segmented control toggling between list and graph views
3. Remove `LabelGraphPage` as a separate route; remove or redirect `/labels/graph`
4. Update `content/index.toml` to include `id = "labels"` page entry
