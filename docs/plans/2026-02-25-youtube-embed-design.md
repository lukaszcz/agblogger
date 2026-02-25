# YouTube Embed Support — Design

Allow users to embed YouTube videos in markdown posts via raw `<iframe>` tags, with strict security controls.

## User Experience

Users write raw iframe tags in their markdown:

```markdown
# My Post

Check out this video:

<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>

More text...
```

The iframe renders as a responsive 16:9 embedded player, full content width. Users can play the video inline, go fullscreen, or click "Watch on YouTube." Width/height attributes are stripped — all embeds are responsive.

## Allowed URL Patterns

```
^https://www\.(?:youtube\.com/(?:embed|shorts)/|youtube-nocookie\.com/embed/)[a-zA-Z0-9_-]{11}(?:\?[a-zA-Z0-9_=&%-]*)?$
```

Matches:
- `https://www.youtube.com/embed/VIDEO_ID`
- `https://www.youtube-nocookie.com/embed/VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`
- Optional query parameters (start time, etc.)

Note: `www.` prefix is required to match the CSP `frame-src` domains. Bare domains (e.g., `youtube.com`) are rejected. `youtube-nocookie.com` only supports `/embed/`, not `/shorts/`, matching YouTube's own URL structure.

Non-matching URLs cause the `<iframe>` to be replaced with a user-visible notification.

## Sanitizer Changes (`backend/pandoc/renderer.py`)

The existing `_HtmlSanitizer` strips unknown tags. Rather than adding `iframe` to `_ALLOWED_TAGS` unconditionally, add conditional handling in `handle_starttag`:

1. Extract `src` attribute from iframe
2. Validate against YouTube URL regex
3. If valid: emit iframe with only `src` plus forced security attributes
4. If invalid: replace with a user-visible notification message

**Forced security attributes** (injected by sanitizer, not user-controllable):
- `sandbox="allow-scripts allow-same-origin allow-popups"` — minimal permissions for YouTube player
- `allowfullscreen` — enables fullscreen video
- `referrerpolicy="no-referrer"` — privacy
- `loading="lazy"` — performance

**Sandbox justification:**
- `allow-scripts` — YouTube player is a JS app, won't work without it
- `allow-same-origin` — needed for YouTube's own cookies/storage; safe because YouTube is cross-origin
- `allow-popups` — needed for "Watch on YouTube" link
- Key capabilities blocked: top-navigation, forms, modals, pointer-lock, downloads

**Stripped attributes:** width, height, onload, style, and everything else — only `src` passes through from user input.

## CSP Update (`backend/config.py`)

Add `frame-src` directive to Content Security Policy:

```
frame-src https://www.youtube.com https://www.youtube-nocookie.com;
```

This is a second layer of defense: even if the sanitizer had a bug, the browser would block non-YouTube iframes. `frame-ancestors 'none'` stays unchanged (controls who frames us, not what we frame).

## Frontend CSS (`frontend/src/index.css`)

Responsive iframe styling within `.prose`:

```css
.prose iframe {
  width: 100%;
  aspect-ratio: 16 / 9;
  border: none;
  border-radius: 8px;
  margin: 1.5rem 0;
}
```

## Pandoc Configuration

No changes needed. Pandoc's `markdown` format includes `raw_html` by default, so `<iframe>` tags pass through to the HTML output where the sanitizer handles them.

## Security Properties

**Defense in depth:**
1. Sanitizer allowlists only YouTube URLs; all others stripped
2. CSP `frame-src` enforces YouTube-only at browser level
3. Sandbox attribute restricts iframe capabilities
4. `referrerpolicy="no-referrer"` prevents referrer leakage

## Testing

**Sanitizer tests** (`tests/test_rendering/test_sanitizer.py`):
- Valid YouTube embed → rendered with forced security attributes
- Valid YouTube-nocookie → allowed
- Valid YouTube Shorts → allowed
- Non-YouTube iframe → stripped
- YouTube iframe with extra attributes → stripped, only `src` preserved
- Malformed URLs (javascript:, data:, path traversal) → stripped
- Query parameters → preserved
- Unmatched end tags → handled gracefully

**CSP test:** Verify header includes `frame-src` for YouTube.

**E2E test (Playwright):** Create post with YouTube iframe, verify embedded player renders.
