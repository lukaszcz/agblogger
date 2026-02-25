# YouTube Embed Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to embed YouTube videos in markdown posts via raw `<iframe>` tags, with strict security (YouTube-only URL validation, sandboxing, CSP).

**Architecture:** Extend the existing `_HtmlSanitizer` in `backend/pandoc/renderer.py` to conditionally allow `<iframe>` tags when `src` matches YouTube URL patterns. The sanitizer forces security attributes (sandbox, referrerpolicy) and strips everything else. CSP gains a `frame-src` directive for YouTube domains. Frontend CSS handles responsive 16:9 layout.

**Tech Stack:** Python (HTMLParser-based sanitizer), CSS (aspect-ratio), pytest (sanitizer tests), Playwright (E2E)

**Design doc:** `docs/plans/2026-02-25-youtube-embed-design.md`

---

### Task 1: Add YouTube iframe sanitizer tests

**Files:**
- Modify: `tests/test_rendering/test_sanitizer.py`

**Step 1: Write failing tests for YouTube iframe sanitization**

Add a new test class at the end of `tests/test_rendering/test_sanitizer.py`:

```python
class TestYouTubeIframe:
    """Tests for YouTube iframe embed support."""

    def test_youtube_embed_allowed(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" in result
        assert 'src="https://www.youtube.com/embed/dQw4w9WgXcQ"' in result
        assert "</iframe>" in result

    def test_youtube_nocookie_allowed(self) -> None:
        html = '<iframe src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" in result
        assert 'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"' in result

    def test_youtube_shorts_allowed(self) -> None:
        html = '<iframe src="https://www.youtube.com/shorts/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" in result
        assert 'src="https://www.youtube.com/shorts/dQw4w9WgXcQ"' in result

    def test_youtube_without_www_allowed(self) -> None:
        html = '<iframe src="https://youtube.com/embed/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" in result

    def test_youtube_with_query_params_allowed(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ?start=30&autoplay=1"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" in result
        assert "start=30" in result

    def test_non_youtube_iframe_stripped(self) -> None:
        html = '<iframe src="https://evil.com/page"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" not in result
        assert "</iframe>" not in result

    def test_iframe_without_src_stripped(self) -> None:
        html = "<iframe></iframe>"
        result = _sanitize_html(html)
        assert "<iframe" not in result

    def test_iframe_javascript_src_stripped(self) -> None:
        html = '<iframe src="javascript:alert(1)"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" not in result

    def test_iframe_data_src_stripped(self) -> None:
        html = '<iframe src="data:text/html,<script>alert(1)</script>"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" not in result

    def test_youtube_http_stripped(self) -> None:
        """Only HTTPS allowed, not HTTP."""
        html = '<iframe src="http://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" not in result

    def test_sandbox_attribute_forced(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert 'sandbox="allow-scripts allow-same-origin allow-popups"' in result

    def test_allowfullscreen_forced(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert "allowfullscreen" in result

    def test_referrerpolicy_forced(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert 'referrerpolicy="no-referrer"' in result

    def test_loading_lazy_forced(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert 'loading="lazy"' in result

    def test_width_height_stripped(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" width="560" height="315"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" in result
        assert "width" not in result
        assert "height" not in result

    def test_onload_stripped(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" onload="alert(1)"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" in result
        assert "onload" not in result

    def test_youtube_path_traversal_stripped(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/../evil"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" not in result

    def test_youtube_extra_path_stripped(self) -> None:
        html = '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ/evil"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" not in result

    def test_youtube_subdomain_attack_stripped(self) -> None:
        html = '<iframe src="https://evil.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe" not in result

    def test_existing_iframe_test_still_passes(self) -> None:
        """Non-YouTube iframes are still stripped (regression for existing test)."""
        result = _sanitize_html("<iframe src='evil.com'></iframe>")
        assert "<iframe" not in result
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rendering/test_sanitizer.py::TestYouTubeIframe -v`
Expected: All tests FAIL (iframes are currently stripped unconditionally)

**Step 3: Commit failing tests**

```bash
git add tests/test_rendering/test_sanitizer.py
git commit -m "test: add failing tests for youtube iframe sanitization"
```

---

### Task 2: Implement YouTube iframe support in the sanitizer

**Files:**
- Modify: `backend/pandoc/renderer.py:28-31` (add regex constant)
- Modify: `backend/pandoc/renderer.py:110-137` (modify `_HtmlSanitizer` methods)

**Step 1: Add the YouTube URL regex constant**

After line 31 (`_VOID_TAGS` definition), add:

```python
_YOUTUBE_SRC_RE = re.compile(
    r"^https://(?:www\.)?(?:youtube\.com/(?:embed|shorts)/|youtube-nocookie\.com/embed/)"
    r"[a-zA-Z0-9_-]{11}(?:\?[a-zA-Z0-9_=&%-]*)?$"
)
```

**Step 2: Modify `handle_starttag` to conditionally allow YouTube iframes**

Replace the current `handle_starttag` (lines 118-129) with logic that:
1. Checks if `tag_name == "iframe"` before the generic `_ALLOWED_TAGS` check
2. For iframes: extracts `src`, validates against `_YOUTUBE_SRC_RE`, and if valid emits the iframe with forced security attributes; if invalid, strips it
3. For all other tags: keeps existing behavior unchanged

```python
def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    tag_name = tag.lower()
    if tag_name == "iframe":
        self._handle_iframe(attrs)
        return
    if tag_name not in _ALLOWED_TAGS:
        self._open_tags.append(None)
        return

    rendered_attrs = self._sanitize_attrs(tag_name, attrs)
    attrs_text = "".join(
        f' {name}="{html.escape(value, quote=True)}"' for name, value in rendered_attrs
    )
    self._parts.append(f"<{tag_name}{attrs_text}>")
    self._open_tags.append(tag_name)
```

**Step 3: Add the `_handle_iframe` method to `_HtmlSanitizer`**

Add this method to the class:

```python
def _handle_iframe(self, attrs: list[tuple[str, str | None]]) -> None:
    """Allow YouTube iframes with forced security attributes; strip all others."""
    src = None
    for raw_name, raw_value in attrs:
        if raw_name.lower() == "src" and raw_value is not None:
            src = raw_value.strip()
            break

    if src is None or not _YOUTUBE_SRC_RE.fullmatch(src):
        self._open_tags.append(None)
        return

    escaped_src = html.escape(src, quote=True)
    self._parts.append(
        f'<iframe src="{escaped_src}"'
        f' sandbox="allow-scripts allow-same-origin allow-popups"'
        f' allowfullscreen="allowfullscreen"'
        f' referrerpolicy="no-referrer"'
        f' loading="lazy"'
        f">"
    )
    self._open_tags.append("iframe")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rendering/test_sanitizer.py -v`
Expected: ALL tests pass including existing ones and new YouTube iframe tests.

**Step 5: Commit**

```bash
git add backend/pandoc/renderer.py
git commit -m "feat: allow youtube iframes with forced security attributes"
```

---

### Task 3: Update CSP to allow YouTube frames

**Files:**
- Modify: `backend/config.py:72-82` (CSP string)

**Step 1: Write a test for CSP frame-src**

Add a test in a relevant test file (e.g., `tests/test_api/test_security_headers.py` or wherever CSP tests exist — if no dedicated file, add to `tests/test_rendering/test_sanitizer.py` since it's related):

Search for existing CSP/security-header tests first. If none exist, create a simple one that verifies the CSP string contains `frame-src`:

```python
from backend.config import Settings

class TestContentSecurityPolicy:
    def test_csp_includes_frame_src_for_youtube(self) -> None:
        settings = Settings()
        assert "frame-src" in settings.content_security_policy
        assert "https://www.youtube.com" in settings.content_security_policy
        assert "https://www.youtube-nocookie.com" in settings.content_security_policy
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rendering/test_sanitizer.py::TestContentSecurityPolicy -v` (or wherever you placed it)
Expected: FAIL — current CSP has no `frame-src`.

**Step 3: Update the CSP string**

In `backend/config.py`, modify the `content_security_policy` field (lines 72-82) to add `frame-src`:

```python
content_security_policy: str = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' https: data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)
```

**Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_rendering/test_sanitizer.py -v`
Expected: ALL pass.

**Step 5: Commit**

```bash
git add backend/config.py tests/test_rendering/test_sanitizer.py
git commit -m "feat: add frame-src csp directive for youtube embeds"
```

---

### Task 4: Add responsive iframe CSS

**Files:**
- Modify: `frontend/src/index.css` (add after `.prose img` block, line 172)

**Step 1: Add `.prose iframe` styles**

After the `.prose img` block (line 172), add:

```css
.prose iframe {
  width: 100%;
  aspect-ratio: 16 / 9;
  border: none;
  border-radius: 8px;
  margin: 1.5rem 0;
}
```

**Step 2: Run frontend checks**

Run: `just check-frontend-static`
Expected: PASS.

**Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: add responsive iframe styling for youtube embeds"
```

---

### Task 5: Update security documentation

**Files:**
- Modify: `docs/guidelines/security.md:108`
- Modify: `docs/arch/security.md:87-103` (CSP section)
- Modify: `docs/arch/security.md:126-135` (HTML Sanitization section)

**Step 1: Update security guidelines**

In `docs/guidelines/security.md`, change line 108 from:
```
- Never add `script`, `iframe`, `object`, `embed`, `style`, `form`, `input`, or `button` to the allowed tags
```
to:
```
- Never add `script`, `object`, `embed`, `style`, `form`, `input`, or `button` to the allowed tags
- `iframe` is conditionally allowed only for YouTube embed/shorts URLs (`_YOUTUBE_SRC_RE`). The sanitizer forces sandbox, referrerpolicy, and loading attributes. Never extend iframe support to other domains without updating CSP `frame-src`.
```

**Step 2: Update security architecture — CSP section**

In `docs/arch/security.md`, update the CSP code block (lines 91-101) to include `frame-src`:

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' https: data:;
font-src 'self' data:;
connect-src 'self';
frame-src https://www.youtube.com https://www.youtube-nocookie.com;
base-uri 'self';
form-action 'self';
frame-ancestors 'none'
```

Update the description paragraph (line 103) to mention `frame-src`:

```
Applied via the `security_headers` middleware in `backend/main.py`. All fonts, scripts, and stylesheets must be self-hosted. External images are allowed over HTTPS. Inline styles are permitted for Tailwind and KaTeX. `frame-src` allows only YouTube embeds. `frame-ancestors 'none'` prevents framing (clickjacking).
```

**Step 3: Update HTML Sanitization section**

In `docs/arch/security.md`, update line 131 from:
```
- Strips all tags not in the allowlist (script, iframe, object, embed, style, form, input, etc.)
```
to:
```
- Strips all tags not in the allowlist (script, object, embed, style, form, etc.)
- Conditionally allows `<iframe>` only when `src` matches YouTube embed/shorts URLs; forces `sandbox="allow-scripts allow-same-origin allow-popups"`, `allowfullscreen`, `referrerpolicy="no-referrer"`, and `loading="lazy"` on all iframes
```

**Step 4: Commit**

```bash
git add docs/guidelines/security.md docs/arch/security.md
git commit -m "docs: update security docs for youtube iframe support"
```

---

### Task 6: E2E browser test with Playwright

**Step 1: Start the dev server**

Run: `just start`

**Step 2: Create a test post with a YouTube iframe**

Log in, create a new post, and add markdown with an iframe:

```markdown
---
title: YouTube Test
---

<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>
```

**Step 3: Verify the iframe renders in the browser**

- Navigate to the post
- Verify the iframe is visible and has the correct security attributes
- Verify it renders at 16:9 aspect ratio, full content width
- Verify fullscreen button works

**Step 4: Stop the dev server**

Run: `just stop`

**Step 5: Clean up any screenshots**

Remove any `*.png` files created during testing.

---

### Task 7: Run full quality gate

**Step 1: Run `just check`**

Run: `just check`
Expected: ALL static checks and tests pass.

**Step 2: Fix any issues**

If any check fails, fix the issue and re-run.

**Step 3: Final commit if needed**

Only if fixes were required.
