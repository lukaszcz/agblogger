# Frontend Architecture

## Routing

Uses `createBrowserRouter` (data router) with `RouterProvider` for full react-router v7 feature support including `useBlocker`.

| Route | Page | Description |
|-------|------|-------------|
| `/` | TimelinePage | Paginated post list with filter panel, post upload (file/folder) |
| `/post/*` | PostPage | Single post view (rendered HTML) |
| `/page/:pageId` | PageViewPage | Top-level page (About, etc.) |
| `/search` | SearchPage | Full-text search results |
| `/login` | LoginPage | Login form |
| `/labels` | LabelsPage | Label list/graph with segmented control toggle (auth: graph edge create/delete) |
| `/labels/:labelId` | LabelPostsPage | Posts filtered by label |
| `/labels/:labelId/settings` | LabelSettingsPage | Label names, parents, delete (auth required) |
| `/editor/*` | EditorPage | Structured metadata bar + split-pane markdown editor |
| `/admin` | AdminPage | Admin panel: site settings, pages, password (admin required) |

## Editor Auto-Save

The `useEditorAutoSave` hook (`hooks/useEditorAutoSave.ts`) provides crash recovery and unsaved-changes protection:

- **Dirty tracking**: Compares current form state (body, labels, isDraft, newPath) to the loaded/initial state
- **Debounced auto-save**: Writes draft to `localStorage` (key: `agblogger:draft:<filePath>`) 3 seconds after the last edit
- **Navigation blocking**: `useBlocker` shows a native `window.confirm` dialog for in-app SPA navigation; `beforeunload` covers tab close and page refresh
- **Draft recovery**: On editor mount, detects stale drafts and shows a banner with Restore/Discard options
- **Enabled gating**: The hook accepts an `enabled` parameter; for existing posts it activates only after loading completes, preventing false dirty state during data fetch

## State Management

Two Zustand stores:

- **`authStore`** — User state, login/logout, token persistence in localStorage.
- **`siteStore`** — Site configuration fetched on app load.

The `ky` HTTP client injects `Authorization: Bearer <token>` from localStorage and clears tokens on 401 responses.

## SEO

`SEOMiddleware` intercepts HTML responses for `/post/*` routes and injects Open Graph and Twitter Card meta tags by looking up post metadata from the database cache.
