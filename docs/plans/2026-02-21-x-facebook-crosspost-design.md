# X (Twitter) + Facebook Cross-Posting Design

## Summary

Add cross-posting support for X (Twitter) and Facebook Pages, following the existing plugin architecture used by Bluesky and Mastodon. Both platforms use OAuth 2.0 flows and text-based posting (excerpt + hashtags + URL).

LinkedIn was excluded (requires partner program approval, unsuitable for hobby projects). Instagram was excluded (image-only posting, poor fit for text-based blog cross-posting).

## X (Twitter) Integration

### OAuth Flow

OAuth 2.0 Authorization Code with PKCE (same pattern as Mastodon):

1. User clicks "Connect X" in admin panel (no input needed)
2. `POST /api/crosspost/x/authorize` builds authorization URL with PKCE challenge
3. Frontend redirects to `https://x.com/i/oauth2/authorize`
4. User authorizes, X redirects to `GET /api/crosspost/x/callback`
5. Backend exchanges code for tokens, fetches username via `GET /2/users/me`, stores encrypted credentials

Scopes: `tweet.read`, `tweet.write`, `users.read`, `offline.access`

### Token Lifecycle

- Access token: 2-hour expiry
- Refresh token: 6-month expiry
- Auto-refresh on 401 during posting (same pattern as Bluesky)

### Posting

- Endpoint: `POST https://api.x.com/2/tweets` with `{"text": "..."}`
- Character limit: 280
- Text generation: same pattern as Bluesky/Mastodon (excerpt + hashtags + URL)

### Configuration

- `X_CLIENT_ID` and `X_CLIENT_SECRET` env vars (optional)
- Platform hidden in UI if not configured

### Stored Credentials

```json
{"access_token": "...", "refresh_token": "...", "username": "..."}
```

## Facebook Page Integration

### OAuth Flow

Standard OAuth 2.0 with a page-selection step:

1. User clicks "Connect Facebook" in admin panel
2. `POST /api/crosspost/facebook/authorize` builds Facebook Login URL
3. Frontend redirects to `https://www.facebook.com/v22.0/dialog/oauth`
4. User authorizes, Facebook redirects to `GET /api/crosspost/facebook/callback`
5. Backend exchanges code for User Access Token, then:
   - Exchanges for long-lived User Access Token (60-day expiry)
   - Fetches managed Pages via `GET /me/accounts`
   - Single page: auto-selects, gets Page Access Token, stores credentials, redirects to admin
   - Multiple pages: redirects to admin with page list → frontend shows picker → `POST /api/crosspost/facebook/select-page` finalizes

Scopes: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`

### Token Lifecycle

- Page Access Tokens derived from long-lived user tokens do not expire
- No refresh logic needed
- Handle token invalidation (user revokes app) gracefully during posting

### Posting

- Endpoint: `POST https://graph.facebook.com/v22.0/{page-id}/feed` with `message` + `link`
- No practical character limit (uses same text-generation logic for consistency)

### Configuration

- `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` env vars (optional)
- Platform hidden in UI if not configured

### Stored Credentials

```json
{"page_access_token": "...", "page_id": "...", "page_name": "..."}
```

## Backend Architecture

### New Files

| File | Purpose |
|------|---------|
| `backend/crosspost/x.py` | `XCrossPoster` implementation |
| `backend/crosspost/facebook.py` | `FacebookCrossPoster` implementation |

### Modified Files

| File | Change |
|------|--------|
| `backend/crosspost/registry.py` | Add X and Facebook to `PLATFORMS` dict |
| `backend/api/crosspost.py` | Add OAuth endpoints: `x/authorize`, `x/callback`, `facebook/authorize`, `facebook/callback`, `facebook/select-page` |
| `backend/config.py` | Add optional `X_CLIENT_ID`, `X_CLIENT_SECRET`, `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` |
| `backend/schemas/crosspost.py` | Add request/response schemas for new flows |
| `backend/main.py` | Initialize OAuth state stores for X and Facebook on `app.state` |

### Character Limits

Shared constant across backend and frontend:

```
bluesky: 300, mastodon: 500, x: 280, facebook: no limit
```

## Frontend Changes

| Component | Change |
|-----------|--------|
| `SocialAccountsPanel.tsx` | Add X connect button (one-click) and Facebook connect button; Facebook page picker for multi-page accounts |
| `CrossPostDialog.tsx` | Add `x: 280` to character limits; no limit display for Facebook |
| `PlatformIcon.tsx` | Add X and Facebook SVG icons |
| `crosspost.ts` | Add `authorizeX()` and `authorizeFacebook()` API functions |

## Testing

### Backend

- Unit tests for `XCrossPoster` and `FacebookCrossPoster` (mocked httpx)
- Integration tests for new OAuth endpoints
- Token refresh tests for X
- Page selection flow tests for Facebook

### Frontend

- `SocialAccountsPanel` tests for new connect buttons
- `CrossPostDialog` tests for new character limits and platform support
