# Post Sharing Design

## Problem

Cross-posting is admin-only and server-mediated (OAuth tokens stored server-side, backend posts on behalf of the user). Unauthenticated visitors have no way to share posts to their own social media accounts. We need a client-side sharing feature that works for everyone without storing credentials on the server.

## Approach

Pure client-side share component using the Web Share API with fallback platform-specific share URLs. Zero backend changes.

### Share Mechanism

- **Web Share API** (`navigator.share`): Primary mechanism on supported browsers (mobile Safari, Chrome Android, recent desktop Chrome). Triggers the OS-native share sheet.
- **Fallback platform buttons**: When Web Share API is unavailable, show explicit buttons for each platform that open pre-filled compose URLs in new tabs.
- **Copy link**: Always available as a universal fallback.

### Platforms (in order)

| Platform | Share URL Pattern |
|----------|-------------------|
| Bluesky | `https://bsky.app/intent/compose?text={encoded_text}` |
| Mastodon | `https://{instance}/share?text={encoded_text}` (instance prompted) |
| X | `https://x.com/intent/tweet?text={encoded_text}` |
| Facebook | `https://www.facebook.com/sharer/sharer.php?u={url}&quote={title}` |
| LinkedIn | `https://www.linkedin.com/sharing/share-offsite/?url={url}` |
| Reddit | `https://www.reddit.com/submit?url={url}&title={title}` |
| Email | `mailto:?subject={title}&body={text}` |

### Share Text Format

```
"{title}" by {author} {url}
```

The quoted title signals shared content (not the user's own). Author attribution provides context. The URL enables platform preview cards via existing Open Graph meta tags.

### Mastodon Instance Prompt

Mastodon has no centralized share URL. When clicking the Mastodon button:
- If `localStorage` key `agblogger:mastodon-instance` exists, share immediately using the stored instance.
- Otherwise, show a small inline popover with a text input (placeholder: `mastodon.social`) and a Share button. Save the entered instance to `localStorage`.

## Components

### Placement on PostPage

Two share touchpoints:

1. **Header** (`ShareButton`): Compact icon button in the post metadata row, alongside date/author/labels. On click: native share (if available) or dropdown with platform icons.
2. **Bottom of post** (`ShareBar`): Horizontal row of platform icon buttons between post content and the admin-only cross-posting section. Visible to all users.

### File Structure

```
frontend/src/components/share/
  ShareButton.tsx          Compact header icon + optional dropdown
  ShareBar.tsx             Full bottom-of-post platform row
  MastodonSharePrompt.tsx  Instance URL popover
  shareUtils.ts            Share URL generation, native share, clipboard
```

### ShareButton (header)

- Renders a `Share2` lucide icon button in the metadata row.
- On click: if `navigator.share` is available, triggers native share dialog immediately with `{ title, text, url }`.
- On click: if native share unavailable, toggles a dropdown popover below the button showing platform icon buttons (same as ShareBar but in a compact vertical/grid layout).
- Click-outside or Escape closes the dropdown.

### ShareBar (bottom of post)

- Horizontal row separated by `border-t border-border` above it.
- Contains platform icon buttons in order: Bluesky, Mastodon, X, Facebook, LinkedIn, Reddit, Email, Copy Link.
- On Web Share API-capable browsers: an additional "Share..." button at the start triggers the native dialog.
- Each platform button opens the respective share URL in `_blank`.
- Copy Link button copies the post URL to clipboard and shows brief "Copied!" feedback.

### MastodonSharePrompt

- Small popover anchored to the Mastodon button.
- Text input for instance URL (placeholder: `mastodon.social`).
- Share button that constructs `https://{instance}/share?text={text}` and opens in `_blank`.
- Saves instance to `localStorage` on share.
- If instance already in `localStorage`, skips the prompt and shares immediately.

### shareUtils.ts

Shared logic module:
- `getShareText(title, author, url)`: Returns formatted share text.
- `getShareUrl(platform, text, url, title)`: Returns platform-specific compose URL.
- `canNativeShare()`: Checks `navigator.share` availability.
- `nativeShare(title, text, url)`: Calls `navigator.share()`.
- `copyToClipboard(text)`: Copies to clipboard, returns success boolean.
- `getMastodonInstance()` / `setMastodonInstance(instance)`: localStorage helpers.

### Visual Style

Consistent with existing PostPage patterns:
- Platform buttons: `text-muted hover:text-ink transition-colors` (matching existing icon links).
- Bottom bar: `border-t border-border` separator.
- Copy feedback: Brief "Copied!" tooltip/text that fades out after 2 seconds.
- Light and editorial, no heavy backgrounds or badges.

### Platform Icons

- Bluesky, Mastodon: Reuse existing `PlatformIcon` component.
- X, Facebook, LinkedIn, Reddit: New SVG icons added to a shared icon component or inline.
- Email: `Mail` icon from lucide-react.
- Copy Link: `Link` or `Copy` icon from lucide-react.

## Interaction with Cross-Posting

Share (client-side, public) and cross-post (server-side, admin) remain separate features:
- All users see the share UI.
- Only admins see the cross-posting section below the share bar.
- No functional overlap: sharing opens external compose UIs; cross-posting posts directly from the server.

## Testing

### Unit Tests (Vitest + testing-library)

- `shareUtils.ts`: All share URL generation, text formatting, edge cases (special characters, long URLs).
- `ShareButton`: Renders, triggers native share when available, shows dropdown when not.
- `ShareBar`: Renders all platform buttons, click handlers open correct URLs.
- `MastodonSharePrompt`: Renders input, saves to localStorage, auto-shares when instance saved.
- Copy-to-clipboard: Mock `navigator.clipboard.writeText`, verify feedback.

### Integration (PostPage)

- Share UI renders for unauthenticated users.
- Admin users see both share UI and cross-posting section.
- Share text format includes post title and author.

## Scope Exclusions

- No backend changes.
- No share counts or social proof.
- No analytics or tracking.
- No admin toggle for enabling/disabling sharing.
- No changes to existing cross-posting feature.
