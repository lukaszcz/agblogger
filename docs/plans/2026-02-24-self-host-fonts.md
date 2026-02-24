# Self-Host Google Fonts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Google Fonts CDN `@import` with locally bundled fontsource packages, eliminating the third-party dependency and CSP violation.

**Architecture:** Install `@fontsource/instrument-serif`, `@fontsource-variable/dm-sans`, and `@fontsource-variable/jetbrains-mono` as npm dependencies. Replace the single Google Fonts `@import` in `index.css` with local imports. Update CSS custom property font-family names to match fontsource naming (`'DM Sans Variable'`, `'JetBrains Mono Variable'`). Add CSP policy documentation to `CLAUDE.md`.

**Tech Stack:** fontsource npm packages, CSS, Vite (bundles font assets automatically)

---

### Task 1: Install fontsource packages

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install the three fontsource packages**

Run:
```bash
cd frontend && npm install @fontsource/instrument-serif @fontsource-variable/dm-sans @fontsource-variable/jetbrains-mono
```

**Step 2: Verify installation**

Run: `cd frontend && npm ls @fontsource/instrument-serif @fontsource-variable/dm-sans @fontsource-variable/jetbrains-mono`
Expected: All three packages listed without errors.

---

### Task 2: Replace Google Fonts import with fontsource imports

**Files:**
- Modify: `frontend/src/index.css`

**Step 1: Remove the Google Fonts `@import` line**

In `frontend/src/index.css`, delete line 2:
```css
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap');
```

Replace with fontsource CSS imports (order: tailwind first, then fonts):
```css
@import "tailwindcss";
@import "@fontsource/instrument-serif/400.css";
@import "@fontsource/instrument-serif/400-italic.css";
@import "@fontsource-variable/dm-sans/wght.css";
@import "@fontsource-variable/dm-sans/wght-italic.css";
@import "@fontsource-variable/jetbrains-mono/wght.css";
```

**Step 2: Update font-family CSS custom properties**

Variable fontsource packages use a `Variable` suffix in the font-family name. Update the `@theme` block:

```css
  --font-display: 'Instrument Serif', Georgia, serif;
  --font-body: 'DM Sans Variable', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono Variable', 'Fira Code', monospace;
```

Note: `Instrument Serif` keeps the same name (it's not a variable font).

**Step 3: Run frontend static checks**

Run: `just check-frontend-static`
Expected: All checks pass.

**Step 4: Run frontend tests**

Run: `just test-frontend`
Expected: All tests pass.

**Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/index.css
git commit -m "fix: self-host google fonts via fontsource packages"
```

---

### Task 3: Add CSP policy documentation to CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add CSP section to Security Guidelines**

Add the following after the existing security guidelines in `CLAUDE.md`:

```markdown
### Content Security Policy (CSP)

The backend enforces a strict CSP that only allows same-origin resources (`default-src 'self'`). This means:

- **All fonts, scripts, and stylesheets must be self-hosted.** Do not add CDN `@import` or `<link>` tags pointing to third-party domains (e.g., Google Fonts, cdnjs, unpkg). These will be silently blocked in production.
- **Images** are an exception: `img-src 'self' https: data:` allows external HTTPS images.
- **Inline styles** are allowed (`'unsafe-inline'`) for Tailwind and KaTeX.
- If a new third-party resource is genuinely needed, self-host it (e.g., use fontsource for fonts, npm packages for libraries) rather than relaxing the CSP.
- The CSP is configured in `backend/config.py` via the `content_security_policy` setting.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CSP policy guidelines to CLAUDE.md"
```

---

### Task 4: Visual verification

**Step 1: Start dev server**

Run: `just start`

**Step 2: Open browser and verify fonts render correctly**

Use Playwright MCP to navigate to the app and verify:
- Headings use Instrument Serif (serif font)
- Body text uses DM Sans (sans-serif)
- Code blocks use JetBrains Mono (monospace)

**Step 3: Stop dev server**

Run: `just stop`

---

### Task 5: Full gate check

**Step 1: Run full check**

Run: `just check`
Expected: All static checks and tests pass.
