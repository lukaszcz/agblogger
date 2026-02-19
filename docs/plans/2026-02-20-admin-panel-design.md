# Admin Panel Design

## Overview

Add an admin panel at `/admin` that allows the site administrator to edit site settings, manage top-level navigation pages, and change the admin password. Accessible only to users with `is_admin=true`.

## Section 1: Site Settings

A form to edit fields stored in `content/index.toml` under `[site]`:

- **Blog title** (text input) — `site.title`
- **Description** (text input) — `site.description`
- **Default author** (text input) — `site.default_author`
- **Timezone** (text input) — `site.timezone`

Save writes directly to `index.toml` and invalidates the cached `site_config` on `ContentManager`.

## Section 2: Pages Management

Manages the `[[pages]]` array in `index.toml` and associated `.md` files.

**Capabilities:**

- List all pages in their current order
- Reorder pages with up/down arrow buttons
- Special pages (timeline, labels) are marked with a badge but fully controllable — can be reordered, renamed (display title), and hidden from navigation
- Add new page: inline form for ID + title, creates an `.md` file, then edit content via inline markdown editor with Pandoc preview
- Edit existing page: expand to edit title and markdown content inline
- Remove page: removes from navigation with option to delete the `.md` file

**Page types:**

- **timeline** — built-in, no `.md` file. Can be reordered, renamed, hidden.
- **labels** — built-in, no `.md` file. Can be reordered, renamed, hidden.
- **Custom pages** — have a `.md` file in `content/`. Can be reordered, renamed, hidden, deleted.

## Section 3: Change Password

Form with current password, new password, and confirm new password fields.

- Current password required to prevent session-hijack password changes
- Minimum 8-character password length
- Server-side validation of current password and confirmation match

## Backend API

New `admin` router at `/api/admin`, all endpoints require `is_admin=true`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/admin/site` | Get current site settings |
| PUT | `/api/admin/site` | Update site settings in index.toml |
| GET | `/api/admin/pages` | Get ordered page list with metadata |
| POST | `/api/admin/pages` | Create a new page (index.toml entry + .md file) |
| PUT | `/api/admin/pages/order` | Save page order and visibility to index.toml |
| PUT | `/api/admin/pages/{page_id}` | Update page title and/or markdown content |
| DELETE | `/api/admin/pages/{page_id}` | Remove page from nav, optionally delete .md file |
| PUT | `/api/admin/password` | Change admin password |

## Frontend

- New `AdminPage.tsx` at `/admin` route
- Single page with three collapsible/scrollable sections
- Gear icon in Header for admin users linking to `/admin`
- Follows existing patterns: Zustand auth store, `disabled={busy}` on async ops, error banners, Tailwind semantic tokens
- Inline markdown editor for page content uses same textarea + Pandoc preview as post editor

## Data Flow

### Updating Site Settings

```
PUT /api/admin/site { title, description, default_author, timezone }
  -> Validate with Pydantic
  -> Read current index.toml
  -> Update [site] section
  -> Write index.toml
  -> Invalidate ContentManager.site_config cache
  -> Git commit
  -> Return updated config
```

### Managing Pages

```
POST /api/admin/pages { id, title }
  -> Validate ID format (alphanumeric + hyphens)
  -> Check ID not already in use
  -> Create content/{id}.md with empty content
  -> Add [[pages]] entry to index.toml
  -> Git commit
  -> Return new page

PUT /api/admin/pages/{page_id} { title?, content? }
  -> Update title in index.toml if provided
  -> Write content to .md file if provided
  -> Git commit
  -> Return updated page

DELETE /api/admin/pages/{page_id} { delete_file?: bool }
  -> Remove [[pages]] entry from index.toml
  -> If delete_file and page has .md file, delete it
  -> Git commit

PUT /api/admin/pages/order { pages: [{ id, title, hidden }] }
  -> Replace [[pages]] array in index.toml
  -> Git commit
  -> Invalidate site_config cache
```

### Changing Password

```
PUT /api/admin/password { current_password, new_password, confirm_password }
  -> Verify current_password against stored hash
  -> Validate new_password == confirm_password
  -> Validate minimum length (8 chars)
  -> Hash new_password with bcrypt
  -> Update user record
  -> Return success
```
