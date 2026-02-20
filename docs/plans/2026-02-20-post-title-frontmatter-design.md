# Design: Title as Front Matter Field

## Overview

Move the post title from being embedded as a `# Heading` in the markdown body to a dedicated `title` field in YAML front matter. The Web UI gets a separate compulsory Title input. The `# Heading` is stripped from the body. During sync, if `title` is absent from front matter, it's backfilled from the first `# Heading` (then stripped).

## Data Model

YAML front matter adds `title` to recognized fields:

```yaml
---
title: My Great Post
created_at: 2026-02-02T22:21:29+00:00
modified_at: 2026-02-02T22:21:35+00:00
author: Admin
labels: ["#swe"]
---

Content here (no # heading)...
```

`PostData` dataclass already has `title: str` -- no structural change needed.

`RECOGNIZED_FIELDS` adds `"title"`.

## Backend Changes

1. **`parse_post()`** -- Read `title` from front matter metadata. If absent, fall back to `extract_title()` from body (existing behavior for legacy/synced files).

2. **`serialize_post()`** -- Write `title` into YAML front matter. Strip any leading `# Heading` from the body before writing.

3. **Post API schemas** -- Add `title: str` to `PostCreate`, `PostUpdate`, and `PostEditResponse`.

4. **Post API endpoints** -- `create_post` and `update_post` use the title from the request body instead of extracting from content. `get_post_for_edit` returns the title.

5. **Sync normalization** -- In `normalize_post_frontmatter()`, if `title` is missing, extract from first `# Heading`, set it in front matter, and strip the heading from body.

6. **Cache rebuild** -- `parse_post()` change handles this automatically.

## Frontend Changes

1. **EditorPage** -- Add a Title text input above the markdown editor. Compulsory (save button disabled when empty). Remove the default `# New Post` from the initial body.

2. **New post file path** -- Auto-generate from title as `posts/YYYY-MM-DD-<slug>.md`. User can still edit.

3. **PostPage** -- Render title as `<h1>` from post metadata, above the Pandoc-rendered body HTML.

4. **Auto-save hook** -- Include `title` in the dirty-tracking state.

## Rendering

The frontend renders the title as an `<h1>` above the Pandoc-rendered body HTML on PostPage. The title comes from PostCache metadata, not from the rendered HTML body.

## Migration / Backward Compatibility

- Existing posts with `# Heading` and no `title` front matter continue to work -- `parse_post()` falls back to extraction.
- Sync normalization backfills `title` into front matter for uploaded posts missing it.
- No database migration needed -- `PostCache.title` column already exists.

## Decisions

| Decision | Choice |
|----------|--------|
| Body heading when title in front matter | Remove from body -- title lives only in front matter |
| File path for new posts | Auto-generate slug from title (`posts/YYYY-MM-DD-<slug>.md`) |
| Title rendering on post page | Frontend renders `<h1>` from metadata, not from Pandoc HTML |
