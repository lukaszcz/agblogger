# Cross-Posting UI Design

## Overview

Web UI for cross-posting blog posts to Bluesky and Mastodon. The backend cross-posting infrastructure is complete (platform plugins, credential storage, history tracking). This design covers the frontend UI and a Mastodon OAuth flow to replace manual token pasting.

## Account Connection (Admin Page)

A new "Social Accounts" tab in the Admin page. Shows connected accounts as cards with platform icon, handle, connected date, and disconnect button.

Both platforms use the same OAuth redirect pattern:

**Bluesky** (existing backend): User enters handle -> `POST /api/crosspost/bluesky/authorize` -> redirect to Bluesky -> callback stores credentials -> redirect to `/admin`.

**Mastodon** (new backend): User enters instance URL -> `POST /api/crosspost/mastodon/authorize` -> backend dynamically registers app via `POST /api/v1/apps` on the instance, stores state (client_id, client_secret, PKCE verifier) -> redirect to instance's `/oauth/authorize` -> callback exchanges code for token -> stores encrypted credentials -> redirect to `/admin`.

Mastodon OAuth state uses the same in-memory `OAuthStateStore` with 10-min TTL. Instance URL validation reuses `_normalize_instance_url()` for SSRF protection.

Disconnect: trash icon on account card -> confirmation -> `DELETE /api/crosspost/accounts/{id}`.

## Cross-Post Dialog (Shared Component)

Reusable modal used from both Post Page and Editor:

- Single editable textarea with auto-generated text (title + excerpt + URL + hashtags)
- Character counters per selected platform below the textarea (300 for Bluesky, 500 for Mastodon), turning red when over limit
- Platform checkboxes with icon + handle to toggle which accounts to post to
- Post button disabled while posting or if any selected platform exceeds its character limit
- Results section after posting: per-platform success/failure with error messages

Content generation happens client-side from post data. The backend `CrossPostRequest` gets a new `custom_text: str | None` field; when provided, platforms use it instead of auto-generating.

## Post Page Integration

Admin-only section below post content:

- "Share" button opens the Cross-Post Dialog
- Cross-post history list: platform icon, handle, timestamp, status badge (success/failed), error message if failed
- History fetched via `GET /api/crosspost/history/{post_path}` only for admin users

## Editor Integration

Platform selection in the editor action bar, visible only when user has connected accounts:

- "Share after saving" section with platform checkboxes (icon + handle)
- On save with platforms selected: save completes first, then Cross-Post Dialog opens pre-populated with selected platforms
- Two-step flow: save, then review/edit text before posting. No silent auto-posting.

## Backend Changes

1. **Mastodon OAuth endpoints** (new):
   - `POST /api/crosspost/mastodon/authorize` - accepts instance_url, registers app, returns authorization_url
   - `GET /api/crosspost/mastodon/callback` - exchanges code, stores encrypted credentials, redirects to /admin
   - PKCE (S256) used for security

2. **CrossPostRequest update**: add `custom_text: str | None = None`

3. No changes to: Bluesky OAuth, social account CRUD, cross-post history, credential encryption.

## Frontend Components

New files:

| File | Purpose |
|------|---------|
| `api/crosspost.ts` | API functions for accounts, OAuth, cross-posting, history |
| `components/crosspost/SocialAccountsPanel.tsx` | Admin tab: list/connect/disconnect accounts |
| `components/crosspost/CrossPostDialog.tsx` | Shared modal: textarea, char counters, post + results |
| `components/crosspost/CrossPostHistory.tsx` | Post page: history list with status badges |
| `components/crosspost/PlatformIcon.tsx` | Renders platform icon by name |

Modified files:

| File | Change |
|------|--------|
| `AdminPage.tsx` | Add "Social Accounts" tab |
| `PostPage.tsx` | Add admin-only history + share button |
| `EditorPage.tsx` | Add platform checkboxes, open dialog after save |

No new routes or Zustand stores. Connected accounts fetched on-demand.
