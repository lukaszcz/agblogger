# Cross-Posting UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a web UI for cross-posting blog posts to Bluesky and Mastodon, including Mastodon OAuth support, social account management in the Admin panel, a shared cross-post dialog, and integration into the post page and editor.

**Architecture:** The backend already has complete cross-posting infrastructure (platform plugins, credential encryption, history tracking). This plan adds: (1) Mastodon OAuth backend endpoints mirroring the existing Bluesky OAuth pattern, (2) a `custom_text` field on `CrossPostRequest` so users can edit text before posting, (3) frontend API layer, components, and page integrations. All new frontend components live in `frontend/src/components/crosspost/` and follow existing codebase patterns.

**Tech Stack:** Python/FastAPI (backend), React 19 + TypeScript + Tailwind (frontend), httpx (Mastodon OAuth), ky (frontend HTTP client), Vitest + testing-library (frontend tests), pytest (backend tests).

**Design doc:** `docs/plans/2026-02-21-cross-posting-ui-design.md`

---

### Task 1: Mastodon OAuth Backend — Schema and State

**Files:**
- Modify: `backend/schemas/crosspost.py`
- Modify: `backend/main.py:137-144` (add mastodon state store)

**Step 1: Add Mastodon OAuth schemas to `backend/schemas/crosspost.py`**

Add after `BlueskyAuthorizeResponse`:

```python
class MastodonAuthorizeRequest(BaseModel):
    """Request to start Mastodon OAuth flow."""

    instance_url: str = Field(min_length=1, description="Mastodon instance URL, e.g. 'https://mastodon.social'")


class MastodonAuthorizeResponse(BaseModel):
    """Response with authorization URL for Mastodon OAuth."""

    authorization_url: str
```

**Step 2: Add `custom_text` to `CrossPostRequest`**

In `CrossPostRequest`, add:

```python
custom_text: str | None = Field(default=None, description="Optional custom text to post instead of auto-generated content")
```

**Step 3: Initialize Mastodon OAuth state store in `backend/main.py`**

After line 144 (`app.state.bluesky_oauth_state = OAuthStateStore(...)`), add:

```python
app.state.mastodon_oauth_state = OAuthStateStore(ttl_seconds=600)
```

**Step 4: Run backend static checks**

Run: `just check-backend-static`
Expected: PASS

**Step 5: Commit**

```
feat: add mastodon oauth schemas and state store
```

---

### Task 2: Mastodon OAuth Backend — Authorize and Callback Endpoints

**Files:**
- Modify: `backend/api/crosspost.py` (add mastodon authorize + callback routes)
- Modify: `backend/crosspost/mastodon.py` (add `_normalize_instance_url` export or reuse)

**Step 1: Write failing tests for Mastodon OAuth endpoints**

Create tests in `tests/test_api/test_crosspost_api.py` (or add to existing test file):

```python
"""Tests for cross-posting API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
class TestMastodonOAuth:
    async def test_mastodon_authorize_requires_auth(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/crosspost/mastodon/authorize",
                json={"instance_url": "https://mastodon.social"},
            )
            assert resp.status_code == 401

    async def test_mastodon_authorize_rejects_invalid_instance(self, app, admin_auth_header):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/crosspost/mastodon/authorize",
                json={"instance_url": "http://localhost"},
                headers=admin_auth_header,
            )
            assert resp.status_code == 400

    async def test_mastodon_callback_rejects_invalid_state(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/crosspost/mastodon/callback",
                params={"code": "test_code", "state": "invalid_state"},
            )
            assert resp.status_code == 400
```

Adapt fixtures to match existing test patterns in `tests/conftest.py`. Check what `app` and auth fixtures exist.

**Step 2: Run tests to verify they fail**

Run: `just test-backend` (or the specific test file)
Expected: FAIL — endpoints don't exist yet

**Step 3: Implement Mastodon OAuth endpoints in `backend/api/crosspost.py`**

Add two new endpoints after the Bluesky callback endpoint:

`POST /api/crosspost/mastodon/authorize`:
1. Validate instance URL using `_normalize_instance_url()` from mastodon.py
2. Generate PKCE code_verifier + code_challenge (S256)
3. Generate random state parameter
4. Call `POST {instance_url}/api/v1/apps` via httpx to dynamically register app:
   - `client_name`: "AgBlogger"
   - `redirect_uris`: `{base_url}/api/crosspost/mastodon/callback`
   - `scopes`: "read:accounts write:statuses"
   - `website`: base_url
5. Store in `mastodon_oauth_state`: state, instance_url, client_id, client_secret, pkce_verifier, user_id
6. Build authorization URL: `{instance_url}/oauth/authorize?client_id=...&redirect_uri=...&response_type=code&scope=read:accounts write:statuses&state=...&code_challenge=...&code_challenge_method=S256`
7. Return `MastodonAuthorizeResponse(authorization_url=...)`

`GET /api/crosspost/mastodon/callback`:
1. Pop state from `mastodon_oauth_state`
2. Exchange code for token via `POST {instance_url}/oauth/token`:
   - `grant_type`: "authorization_code"
   - `code`: from query param
   - `client_id`, `client_secret`: from stored state
   - `redirect_uri`: same as authorize
   - `code_verifier`: from stored state
3. Verify credentials work via `GET {instance_url}/api/v1/accounts/verify_credentials`
4. Store encrypted credentials as `SocialAccount` with platform="mastodon", account_name=`@{acct}@{hostname}`
5. Handle `DuplicateAccountError` by replacing existing account (same as Bluesky callback)
6. Redirect to `/admin` with 303

Use `settings.bluesky_client_url` (or add a general `APP_URL` setting) for constructing the callback URL. Since `BLUESKY_CLIENT_URL` already serves as the public base URL, reuse it.

**Step 4: Run tests to verify they pass**

Run: `just test-backend`
Expected: PASS

**Step 5: Run full backend checks**

Run: `just check-backend`
Expected: PASS

**Step 6: Commit**

```
feat: add mastodon oauth authorize and callback endpoints
```

---

### Task 3: Backend — Support custom_text in crosspost service

**Files:**
- Modify: `backend/services/crosspost_service.py:97-246`
- Modify: `backend/api/crosspost.py:98-144` (pass custom_text)
- Modify: `backend/crosspost/bluesky.py` (accept optional custom text)
- Modify: `backend/crosspost/mastodon.py` (accept optional custom text)

**Step 1: Write failing test for custom_text**

Add to test file:

```python
async def test_crosspost_uses_custom_text(self, ...):
    # Test that when custom_text is provided, it's used instead of auto-generated text
    ...
```

**Step 2: Update `CrossPostContent` in `backend/crosspost/base.py`**

Add field: `custom_text: str | None = None`

**Step 3: Pass custom_text through the service**

In `crosspost_service.py`, the `crosspost()` function signature gets a new param:
```python
async def crosspost(
    session, content_manager, post_path, platforms, actor, site_url,
    secret_key="", custom_text=None,
) -> list[CrossPostResult]:
```

Set `content.custom_text = custom_text` when building `CrossPostContent`.

**Step 4: Use custom_text in platform posters**

In `bluesky.py` `_build_post_text()` and `mastodon.py` `_build_status_text()`: if `content.custom_text` is not None, return it directly (bypass auto-generation). The frontend handles character limiting.

**Step 5: Pass custom_text in API endpoint**

In `crosspost_endpoint()`, pass `body.custom_text` to the service call:
```python
results = await crosspost(..., custom_text=body.custom_text)
```

**Step 6: Run tests**

Run: `just check-backend`
Expected: PASS

**Step 7: Commit**

```
feat: support custom text in cross-posting
```

---

### Task 4: Frontend — API Layer (`frontend/src/api/crosspost.ts`)

**Files:**
- Create: `frontend/src/api/crosspost.ts`

**Step 1: Create the crosspost API module**

Follow patterns from `frontend/src/api/posts.ts` and `frontend/src/api/admin.ts`.

```typescript
import api from '@/api/client'

export interface SocialAccount {
  id: number
  platform: string
  account_name: string | null
  created_at: string
}

export interface CrossPostResult {
  id: number
  post_path: string
  platform: string
  platform_id: string | null
  status: string
  posted_at: string | null
  error: string | null
}

export interface CrossPostHistory {
  items: CrossPostResult[]
}

export async function fetchSocialAccounts(): Promise<SocialAccount[]> {
  return api.get('crosspost/accounts').json<SocialAccount[]>()
}

export async function deleteSocialAccount(accountId: number): Promise<void> {
  await api.delete(`crosspost/accounts/${accountId}`)
}

export async function authorizeBluesky(handle: string): Promise<{ authorization_url: string }> {
  return api.post('crosspost/bluesky/authorize', { json: { handle } }).json<{ authorization_url: string }>()
}

export async function authorizeMastodon(instanceUrl: string): Promise<{ authorization_url: string }> {
  return api.post('crosspost/mastodon/authorize', { json: { instance_url: instanceUrl } }).json<{ authorization_url: string }>()
}

export async function crossPost(
  postPath: string,
  platforms: string[],
  customText?: string,
): Promise<CrossPostResult[]> {
  return api
    .post('crosspost/post', {
      json: { post_path: postPath, platforms, custom_text: customText ?? null },
    })
    .json<CrossPostResult[]>()
}

export async function fetchCrossPostHistory(postPath: string): Promise<CrossPostHistory> {
  return api.get(`crosspost/history/${postPath}`).json<CrossPostHistory>()
}
```

**Step 2: Run frontend static checks**

Run: `just check-frontend-static`
Expected: PASS

**Step 3: Commit**

```
feat: add cross-posting api layer
```

---

### Task 5: Frontend — PlatformIcon Component

**Files:**
- Create: `frontend/src/components/crosspost/PlatformIcon.tsx`

**Step 1: Create the PlatformIcon component**

A small component that renders an SVG icon for each platform. Use simple inline SVGs for Bluesky (butterfly) and Mastodon (elephant) logos, or use text-based fallbacks. Keep it minimal.

```typescript
interface PlatformIconProps {
  platform: string
  size?: number
  className?: string
}

export default function PlatformIcon({ platform, size = 16, className = '' }: PlatformIconProps) {
  // Render appropriate icon per platform
  // Bluesky: butterfly SVG
  // Mastodon: elephant SVG
  // Fallback: first letter capitalized in a circle
}
```

**Step 2: Run frontend static checks**

Run: `just check-frontend-static`
Expected: PASS

**Step 3: Commit**

```
feat: add platform icon component
```

---

### Task 6: Frontend — SocialAccountsPanel Component (Admin Tab)

**Files:**
- Create: `frontend/src/components/crosspost/SocialAccountsPanel.tsx`
- Create: `frontend/src/components/crosspost/__tests__/SocialAccountsPanel.test.tsx`

**Step 1: Write failing tests**

```typescript
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import SocialAccountsPanel from '../SocialAccountsPanel'

// Mock the API module
vi.mock('@/api/crosspost', () => ({
  fetchSocialAccounts: vi.fn(),
  deleteSocialAccount: vi.fn(),
  authorizeBluesky: vi.fn(),
  authorizeMastodon: vi.fn(),
}))

describe('SocialAccountsPanel', () => {
  it('renders connect buttons for both platforms', async () => {
    // Mock fetchSocialAccounts to return empty
    // Render component
    // Assert "Connect Bluesky" and "Connect Mastodon" buttons visible
  })

  it('shows connected accounts', async () => {
    // Mock fetchSocialAccounts to return accounts
    // Assert account names and disconnect buttons visible
  })

  it('disables controls while busy', async () => {
    // Mock fetchSocialAccounts, trigger connect flow
    // Assert controls disabled during operation
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `just test-frontend`
Expected: FAIL

**Step 3: Implement SocialAccountsPanel**

The component:
1. On mount, fetches connected accounts via `fetchSocialAccounts()`
2. Shows loading spinner while fetching
3. Lists existing accounts as cards: PlatformIcon + account_name + created_at + delete button
4. Two "Connect" sections:

**Bluesky connect flow:**
- "Connect Bluesky" button reveals input for handle
- Submit calls `authorizeBluesky(handle)` → returns `authorization_url`
- `window.location.href = authorization_url` to redirect

**Mastodon connect flow:**
- "Connect Mastodon" button reveals input for instance URL
- Submit calls `authorizeMastodon(instanceUrl)` → returns `authorization_url`
- `window.location.href = authorization_url` to redirect

**Disconnect:**
- Trash icon on account card → confirmation → `deleteSocialAccount(id)` → refresh list

Props: `busy: boolean` from parent AdminPage, `onBusyChange: (busy: boolean) => void`

Follow AdminPage patterns for error/success messages, button styles, disabled states.

**Step 4: Run tests to verify they pass**

Run: `just test-frontend`
Expected: PASS

**Step 5: Commit**

```
feat: add social accounts panel component
```

---

### Task 7: Frontend — Integrate SocialAccountsPanel into AdminPage

**Files:**
- Modify: `frontend/src/pages/AdminPage.tsx`

**Step 1: Add social accounts section to AdminPage**

After the Password section (line 972), add a new section:

```tsx
{/* === Section 4: Social Accounts === */}
<SocialAccountsPanel busy={busy} onBusyChange={setSocialBusy} />
```

Add state variable: `const [socialBusy, setSocialBusy] = useState(false)`

Include `socialBusy` in the `busy` computed state.

Add import for `SocialAccountsPanel`.

**Step 2: Run frontend checks**

Run: `just check-frontend`
Expected: PASS

**Step 3: Commit**

```
feat: add social accounts section to admin page
```

---

### Task 8: Frontend — CrossPostDialog Component

**Files:**
- Create: `frontend/src/components/crosspost/CrossPostDialog.tsx`
- Create: `frontend/src/components/crosspost/__tests__/CrossPostDialog.test.tsx`

**Step 1: Write failing tests**

```typescript
describe('CrossPostDialog', () => {
  it('renders platform checkboxes for connected accounts', () => {
    // Pass accounts as prop, assert checkboxes render
  })

  it('shows character count per platform', () => {
    // Assert character counters for selected platforms
  })

  it('disables post button when over character limit', () => {
    // Enter text over 300 chars, check Bluesky selected, assert button disabled
  })

  it('calls onPost with selected platforms and custom text', async () => {
    // Select platforms, edit text, click post, assert callback
  })

  it('shows results after posting', () => {
    // Pass results prop, assert success/failure badges
  })
})
```

**Step 2: Run tests to verify they fail**

**Step 3: Implement CrossPostDialog**

Props:
```typescript
interface CrossPostDialogProps {
  open: boolean
  onClose: () => void
  accounts: SocialAccount[]
  postPath: string
  postTitle: string
  postExcerpt: string
  postLabels: string[]
}
```

The dialog:
1. On open, generates default text client-side from postTitle + postExcerpt + URL + hashtags
2. Single textarea for editing the text
3. Character counters per selected platform below textarea (Bluesky: 300, Mastodon: 500)
4. Platform checkboxes with PlatformIcon + account_name
5. "Post" button → calls `crossPost(postPath, selectedPlatforms, customText)`
6. Shows results: per-platform success (green) / failure (red with error message)
7. "Close" button after results

Character limits: `{ bluesky: 300, mastodon: 500 }` — counter turns red when exceeded. Post button disabled if any selected platform exceeds its limit.

Use the modal pattern from PostPage delete dialog (fixed overlay, centered card, backdrop blur).

**Step 4: Run tests to verify they pass**

**Step 5: Run frontend static checks**

Run: `just check-frontend`
Expected: PASS

**Step 6: Commit**

```
feat: add cross-post dialog component
```

---

### Task 9: Frontend — CrossPostHistory Component

**Files:**
- Create: `frontend/src/components/crosspost/CrossPostHistory.tsx`
- Create: `frontend/src/components/crosspost/__tests__/CrossPostHistory.test.tsx`

**Step 1: Write failing tests**

```typescript
describe('CrossPostHistory', () => {
  it('renders history items with platform and status', () => {
    // Pass items, assert platform icons and status badges
  })

  it('shows error message for failed posts', () => {
    // Pass item with error, assert error text visible
  })

  it('shows empty state when no history', () => {
    // Pass empty items, assert "Not shared yet" message
  })
})
```

**Step 2: Implement CrossPostHistory**

Props:
```typescript
interface CrossPostHistoryProps {
  items: CrossPostResult[]
  loading: boolean
}
```

Renders a list of history entries:
- PlatformIcon + platform name
- Status badge: "Posted" (green) / "Failed" (red)
- Timestamp (formatted)
- Error message if failed (small red text)

If empty and not loading: "Not shared yet."

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: add cross-post history component
```

---

### Task 10: Frontend — PostPage Integration

**Files:**
- Modify: `frontend/src/pages/PostPage.tsx`

**Step 1: Write failing test**

Add test that verifies: when user is admin, cross-post section renders. When not admin, it doesn't.

**Step 2: Integrate into PostPage**

After the post content `<div>` (line 172) and before the `<footer>` (line 174), add an admin-only section:

```tsx
{user?.is_admin && post && (
  <CrossPostSection filePath={filePath!} post={post} />
)}
```

Create a small `CrossPostSection` inline component (or separate file) that:
1. Fetches cross-post history via `fetchCrossPostHistory(filePath)`
2. Fetches connected accounts via `fetchSocialAccounts()`
3. Renders "Share" button (only if accounts exist) + CrossPostHistory
4. "Share" button opens CrossPostDialog
5. After dialog closes with results, refreshes history

State: loading, history items, accounts, dialog open state.

**Step 3: Run tests, verify pass**

**Step 4: Run frontend checks**

Run: `just check-frontend`
Expected: PASS

**Step 5: Commit**

```
feat: add cross-posting section to post page
```

---

### Task 11: Frontend — EditorPage Integration

**Files:**
- Modify: `frontend/src/pages/EditorPage.tsx`

**Step 1: Write failing test**

Test that platform checkboxes appear when accounts are connected, and that the dialog opens after save when platforms are selected.

**Step 2: Integrate into EditorPage**

Add state:
```typescript
const [accounts, setAccounts] = useState<SocialAccount[]>([])
const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([])
const [showCrossPostDialog, setShowCrossPostDialog] = useState(false)
const [savedFilePath, setSavedFilePath] = useState<string | null>(null)
```

On mount, fetch accounts (only if user is authenticated):
```typescript
useEffect(() => {
  if (user) {
    fetchSocialAccounts().then(setAccounts).catch(() => {})
  }
}, [user])
```

In the metadata bar (after the Draft checkbox area, around line 348), add platform checkboxes:
```tsx
{accounts.length > 0 && (
  <div className="flex items-center gap-3">
    <span className="text-xs text-muted">Share after saving:</span>
    {accounts.map((acct) => (
      <label key={acct.id} className="flex items-center gap-1.5 cursor-pointer">
        <input
          type="checkbox"
          checked={selectedPlatforms.includes(acct.platform)}
          onChange={...}
          disabled={saving}
        />
        <PlatformIcon platform={acct.platform} size={14} />
        <span className="text-sm text-ink">{acct.account_name}</span>
      </label>
    ))}
  </div>
)}
```

Modify `handleSave`: after successful save, if `selectedPlatforms.length > 0`, set `savedFilePath` and `showCrossPostDialog = true` instead of navigating immediately. Navigate after the dialog closes.

Render `CrossPostDialog` at the end of the component.

**Step 3: Run tests, verify pass**

**Step 4: Run frontend checks**

Run: `just check-frontend`
Expected: PASS

**Step 5: Commit**

```
feat: add cross-posting integration to editor
```

---

### Task 12: End-to-End Testing in Browser

**Files:** None (uses playwright MCP for browser testing)

**Step 1: Start dev server**

Run: `just start`

**Step 2: Test account connection flow**

1. Navigate to `/login`, log in as admin
2. Navigate to `/admin`
3. Verify Social Accounts section is visible
4. Click "Connect Bluesky" → verify handle input appears
5. Click "Connect Mastodon" → verify instance URL input appears
6. (Cannot complete OAuth redirect in test, but verify UI renders)

**Step 3: Test cross-post dialog from post page**

1. Navigate to an existing post
2. Verify cross-post section appears for admin
3. Verify "Share" button works (opens dialog)
4. Verify dialog shows textarea, character counters, platform checkboxes
5. Verify dialog close works

**Step 4: Test editor integration**

1. Navigate to editor for existing post
2. Verify platform checkboxes appear (if accounts connected)
3. Verify save flow works normally when no platforms selected

**Step 5: Stop dev server**

Run: `just stop`

**Step 6: Clean up screenshots**

Remove any `*.png` files created during testing.

---

### Task 13: Update Architecture Documentation

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Update Cross-Posting section**

Add Mastodon OAuth details:
- Dynamic app registration via `POST /api/v1/apps`
- PKCE support
- OAuth state stored in same `OAuthStateStore` pattern

Add `custom_text` support description.

**Step 2: Update Frontend Architecture section**

Add cross-posting components description:
- `SocialAccountsPanel` in Admin page
- `CrossPostDialog` shared modal
- `CrossPostHistory` on post page

**Step 3: Update API Routes table**

Ensure crosspost router description mentions Mastodon OAuth endpoints.

**Step 4: Commit**

```
docs: update architecture for cross-posting ui
```

---

### Task 14: Final Verification

**Step 1: Run full check gate**

Run: `just check`
Expected: ALL PASS (static checks + tests for both backend and frontend)

**Step 2: Review git log**

Verify all commits are clean and focused.

**Step 3: Commit any remaining changes**

If any fixes were needed during verification.
