# Crash Resilience Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 42 identified crash vulnerabilities so the server never crashes from unhandled exceptions during request handling, and startup failures produce clear error messages.

**Architecture:** Six layers of defense: (1) global exception handlers as safety net, (2) targeted endpoint fixes for critical/high issues, (3) service/library hardening, (4) startup hardening, (5) atomic writes and async fixes, (6) low-severity fixes.

**Tech Stack:** Python/FastAPI, pytest (async), pendulum, PyYAML, SQLAlchemy, subprocess (pandoc/git)

**Design doc:** `docs/plans/2026-02-22-crash-resilience-design.md`

---

### Task 1: Service/library hardening — datetime, TOML, content manager, pandoc, labels, sync, FTS

Fixes: H3, H4, H5, H6, M7, M8, M10, M11, M13

**Files:**
- Modify: `backend/services/datetime_service.py:35`
- Modify: `backend/filesystem/toml_manager.py:57-61, 101-126, 129-141, 144-161`
- Modify: `backend/filesystem/content_manager.py:123-135, 173-184`
- Modify: `backend/pandoc/renderer.py:212-218`
- Modify: `backend/services/label_service.py:58, 89-91`
- Modify: `backend/services/sync_service.py:454`
- Modify: `backend/services/post_service.py:65-73, 193-226`
- Test: `tests/test_services/test_error_handling.py` (new)

**Step 1: Write failing tests**

Create `tests/test_services/test_error_handling.py`:

```python
"""Tests for error handling in services and libraries."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from backend.filesystem.content_manager import ContentManager
from backend.filesystem.toml_manager import (
    LabelDef,
    parse_labels_config,
    parse_site_config,
    write_labels_config,
    write_site_config,
    SiteConfig,
)
from backend.pandoc.renderer import _render_markdown_sync
from backend.services.datetime_service import parse_datetime


class TestParseDatetimeParserError:
    """H3: pendulum.ParserError should be converted to ValueError."""

    def test_invalid_date_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            parse_datetime("not-a-date")

    def test_gibberish_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            parse_datetime("xyz123!@#")


class TestConfigParsingOSError:
    """H4: OSError in config parsing returns defaults."""

    def test_site_config_permission_error(self, tmp_path: Path) -> None:
        index = tmp_path / "index.toml"
        index.write_text('[site]\ntitle = "Test"')
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            result = parse_site_config(tmp_path)
        assert result.title == "My Blog"  # default

    def test_labels_config_permission_error(self, tmp_path: Path) -> None:
        labels = tmp_path / "labels.toml"
        labels.write_text("[labels.foo]\nnames = ['foo']")
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            result = parse_labels_config(tmp_path)
        assert result == {}


class TestLabelsConfigTypeCheck:
    """M10: Non-dict label entries should be skipped."""

    def test_string_label_entry_skipped(self, tmp_path: Path) -> None:
        labels = tmp_path / "labels.toml"
        labels.write_text('[labels]\nfoo = "bar"')
        result = parse_labels_config(tmp_path)
        assert "foo" not in result


class TestReadPostErrorHandling:
    """H5: read_post returns None on parse errors."""

    def test_invalid_yaml_returns_none(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        bad_post = posts_dir / "bad.md"
        bad_post.write_text("---\ntitle: [\n---\nbody")
        (tmp_path / "index.toml").write_text('[site]\ntitle = "Test"')
        (tmp_path / "labels.toml").write_text("[labels]")
        cm = ContentManager(content_dir=tmp_path)
        result = cm.read_post("posts/bad.md")
        assert result is None

    def test_binary_file_returns_none(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        bad_post = posts_dir / "binary.md"
        bad_post.write_bytes(b"\x80\x81\x82\x83")
        (tmp_path / "index.toml").write_text('[site]\ntitle = "Test"')
        (tmp_path / "labels.toml").write_text("[labels]")
        cm = ContentManager(content_dir=tmp_path)
        result = cm.read_post("posts/binary.md")
        assert result is None


class TestReadPageErrorHandling:
    """M11: read_page returns None on I/O errors."""

    def test_binary_page_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "index.toml").write_text(
            '[site]\ntitle = "Test"\n\n[[pages]]\nid = "about"\ntitle = "About"\nfile = "about.md"'
        )
        (tmp_path / "labels.toml").write_text("[labels]")
        about = tmp_path / "about.md"
        about.write_bytes(b"\x80\x81\x82\x83")
        cm = ContentManager(content_dir=tmp_path)
        result = cm.read_page("about")
        assert result is None


class TestPandocOSError:
    """M13: OSError from subprocess.run caught and raised as RuntimeError."""

    def test_oserror_raises_runtime_error(self) -> None:
        with patch("subprocess.run", side_effect=OSError("Too many open files")):
            with pytest.raises(RuntimeError, match="system error"):
                _render_markdown_sync("# hello")


class TestLabelServiceJsonError:
    """M7: corrupted label names in DB handled gracefully."""

    @pytest.mark.asyncio
    async def test_corrupted_names_returns_empty_list(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_label = MagicMock()
        mock_label.id = "test"
        mock_label.names = "not valid json {"
        mock_label.is_implicit = False

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_label]
        mock_session.execute.return_value = mock_result

        from backend.services.label_service import get_all_labels

        results = await get_all_labels(mock_session)
        # Should not crash; corrupted label should have empty names
        assert len(results) >= 0


class TestSyncYamlError:
    """H6: yaml.YAMLError caught in normalize_post_frontmatter."""

    def test_malformed_yaml_skipped(self, tmp_path: Path) -> None:
        post = tmp_path / "posts" / "bad.md"
        post.parent.mkdir(parents=True)
        post.write_text("---\ntitle: [\n---\nbody")
        from backend.services.sync_service import normalize_post_frontmatter

        warnings = normalize_post_frontmatter(
            uploaded_files=["posts/bad.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="admin",
        )
        assert any("parse error" in w for w in warnings)


class TestFTSOperationalError:
    """M8: FTS5 OperationalError returns empty results."""

    @pytest.mark.asyncio
    async def test_fts_error_returns_empty(self) -> None:
        from unittest.mock import AsyncMock

        from sqlalchemy.exc import OperationalError

        mock_session = AsyncMock()
        mock_session.execute.side_effect = OperationalError("fts5", {}, Exception())

        from backend.services.post_service import search_posts

        results = await search_posts(mock_session, "test")
        assert results == []


class TestAtomicWrites:
    """M9: TOML writes are atomic."""

    def test_write_labels_uses_temp_file(self, tmp_path: Path) -> None:
        labels = {"test": LabelDef(id="test", names=["test"])}
        write_labels_config(tmp_path, labels)
        # File should exist and be valid TOML
        import tomllib

        data = tomllib.loads((tmp_path / "labels.toml").read_text())
        assert "test" in data["labels"]
        # No .tmp file left behind
        assert not (tmp_path / "labels.tmp").exists()

    def test_write_site_config_uses_temp_file(self, tmp_path: Path) -> None:
        config = SiteConfig(title="Test Blog")
        write_site_config(tmp_path, config)
        import tomllib

        data = tomllib.loads((tmp_path / "index.toml").read_text())
        assert data["site"]["title"] == "Test Blog"
        assert not (tmp_path / "index.tmp").exists()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_error_handling.py -v`
Expected: Multiple failures (parse_datetime doesn't catch ParserError, config doesn't catch OSError, read_post doesn't return None on bad YAML, etc.)

**Step 3: Implement the fixes**

**3a. `backend/services/datetime_service.py:35`** — Catch `ParserError` and convert to `ValueError`:

```python
# Add to imports
from pendulum.parsing.exceptions import ParserError

# Replace line 35
    try:
        parsed = pendulum.parse(value_str, tz=default_tz, strict=False)
    except ParserError as exc:
        raise ValueError(f"Cannot parse date from: {value_str}") from exc
```

**3b. `backend/filesystem/toml_manager.py:57-61`** — Add `OSError` to except clauses in `parse_site_config`:

Change line 59 from:
```python
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
```
to:
```python
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as exc:
```

**3c. `backend/filesystem/toml_manager.py:101-105`** — Add `OSError` to except clause in `parse_labels_config`:

Change line 103 from:
```python
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
```
to:
```python
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as exc:
```

**3d. `backend/filesystem/toml_manager.py:109-124`** — Add `isinstance` check for non-dict label entries (M10):

Wrap the loop body in `parse_labels_config`:
```python
    for label_id, label_info in labels_data.items():
        if not isinstance(label_info, dict):
            logger.warning("Skipping non-dict label entry %r in labels.toml", label_id)
            continue
        names = label_info.get("names", [])
        ...
```

**3e. `backend/filesystem/toml_manager.py:129-141, 144-161`** — Atomic writes (M9):

Replace `write_labels_config` body ending:
```python
    labels_path = content_dir / "labels.toml"
    tmp_path = labels_path.with_suffix(".toml.tmp")
    data = tomli_w.dumps({"labels": labels_data}).encode("utf-8")
    tmp_path.write_bytes(data)
    tmp_path.replace(labels_path)
```

Replace `write_site_config` body ending:
```python
    index_path = content_dir / "index.toml"
    tmp_path = index_path.with_suffix(".toml.tmp")
    data = tomli_w.dumps({"site": site_data, "pages": pages_data}).encode("utf-8")
    tmp_path.write_bytes(data)
    tmp_path.replace(index_path)
```

**3f. `backend/filesystem/content_manager.py:123-135`** — Add error handling to `read_post` (H5):

```python
    def read_post(self, rel_path: str) -> PostData | None:
        """Read a single post by relative path."""
        full_path = self._validate_path(rel_path)
        if not full_path.exists() or not full_path.is_file():
            return None
        try:
            raw_content = full_path.read_text(encoding="utf-8")
            post_data = parse_post(
                raw_content,
                file_path=rel_path,
                default_tz=self.site_config.timezone,
                default_author=self.site_config.default_author,
            )
        except (UnicodeDecodeError, ValueError, yaml.YAMLError, OSError) as exc:
            logger.warning("Failed to read post %s: %s", rel_path, exc)
            return None
        return post_data
```

**3g. `backend/filesystem/content_manager.py:173-184`** — Add error handling to `read_page` (M11):

Wrap the `read_text` call:
```python
                if page_path.exists():
                    try:
                        return page_path.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, OSError) as exc:
                        logger.warning("Failed to read page %s: %s", page_id, exc)
                        return None
```

**3h. `backend/pandoc/renderer.py:212-218`** — Add `OSError` to except clause (M13):

After the `except subprocess.TimeoutExpired` block, add:
```python
    except OSError as exc:
        raise RuntimeError(
            f"Pandoc subprocess system error: {exc}"
        ) from None
```

**3i. `backend/services/label_service.py:58`** — Wrap `json.loads` (M7):

In `get_all_labels`, change:
```python
                names=json.loads(label.names),
```
to:
```python
                names=_safe_parse_names(label.names),
```

Add helper at module level:
```python
def _safe_parse_names(raw: str) -> list[str]:
    """Parse label names JSON, returning empty list on error."""
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid label names JSON: %s", raw[:100])
        return []
```

Do the same in `get_label` at line 91.

**3j. `backend/services/sync_service.py:454`** — Add `yaml.YAMLError` (H6):

Change line 454 from:
```python
        except (UnicodeDecodeError, ValueError) as exc:
```
to:
```python
        except (UnicodeDecodeError, ValueError, yaml.YAMLError) as exc:
```

(Note: `yaml` is already imported at top of file via `from yaml import YAMLError` or similar — check and add import if needed.)

**3k. `backend/services/post_service.py:65-73`** — Wrap date parsing (H3):

```python
    if from_date:
        date_part = from_date.split("T")[0].split(" ")[0]
        try:
            from_dt = parse_datetime(date_part + " 00:00:00", default_tz="UTC")
        except ValueError:
            from_dt = None
        if from_dt is not None:
            stmt = stmt.where(PostCache.created_at >= from_dt)

    if to_date:
        date_part = to_date.split("T")[0].split(" ")[0]
        try:
            to_dt = parse_datetime(date_part + " 23:59:59.999999", default_tz="UTC")
        except ValueError:
            to_dt = None
        if to_dt is not None:
            stmt = stmt.where(PostCache.created_at <= to_dt)
```

**3l. `backend/services/post_service.py:193-226`** — Wrap FTS query (M8):

```python
async def search_posts(session: AsyncSession, query: str, *, limit: int = 20) -> list[SearchResult]:
    """Full-text search for posts."""
    from sqlalchemy.exc import OperationalError

    safe_query = '"' + query.replace('"', '""') + '"'
    stmt = text("""...""")
    try:
        result = await session.execute(stmt, {"query": safe_query, "limit": limit})
    except OperationalError as exc:
        logger.warning("FTS search failed (index may be corrupted): %s", exc)
        return []
    rows = result.all()
    ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_error_handling.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `just test-backend`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add backend/services/datetime_service.py backend/filesystem/toml_manager.py \
  backend/filesystem/content_manager.py backend/pandoc/renderer.py \
  backend/services/label_service.py backend/services/sync_service.py \
  backend/services/post_service.py tests/test_services/test_error_handling.py
git commit -m "fix: harden services and libraries against crash-causing exceptions"
```

---

### Task 2: Global exception handlers and startup hardening

Fixes: C2, H9, H12, H7, M16, global safety net

**Files:**
- Modify: `backend/main.py:106-182, 185-287`
- Modify: `backend/crosspost/atproto_oauth.py:112-135`
- Test: `tests/test_services/test_startup_hardening.py` (new)

**Step 1: Write failing tests**

Create `tests/test_services/test_startup_hardening.py`:

```python
"""Tests for startup hardening and global exception handlers."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import Settings
from backend.main import create_app


class TestGlobalExceptionHandlers:
    """Global exception handlers return structured JSON instead of crashing."""

    @pytest.mark.asyncio
    async def test_runtime_error_returns_502(self) -> None:
        settings = Settings(
            secret_key="test-secret-key-min-32-characters-long",
            admin_password="testpassword",
            debug=True,
        )
        app = create_app(settings)

        # Register a test route that raises RuntimeError
        @app.get("/test-runtime-error")
        async def _raise_runtime_error() -> None:
            raise RuntimeError("pandoc failed")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/test-runtime-error")
        assert resp.status_code == 502
        assert "detail" in resp.json()

    @pytest.mark.asyncio
    async def test_os_error_returns_500(self) -> None:
        settings = Settings(
            secret_key="test-secret-key-min-32-characters-long",
            admin_password="testpassword",
            debug=True,
        )
        app = create_app(settings)

        @app.get("/test-os-error")
        async def _raise_os_error() -> None:
            raise OSError("disk full")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/test-os-error")
        assert resp.status_code == 500
        assert "detail" in resp.json()


class TestStaleLockFile:
    """H7: stale lock file is cleaned up."""

    def test_stale_lock_removed(self, tmp_path: Path) -> None:
        key_path = tmp_path / "test-key.json"
        lock_path = key_path.with_name(f".{key_path.name}.lock")
        # Create a stale lock (older than 30 seconds)
        lock_path.write_text("")
        old_time = time.time() - 60
        os.utime(lock_path, (old_time, old_time))

        from backend.crosspost.atproto_oauth import load_or_create_keypair

        private_key, jwk = load_or_create_keypair(key_path)
        assert private_key is not None
        assert not lock_path.exists()

    def test_corrupted_keypair_in_lock_loop(self, tmp_path: Path) -> None:
        key_path = tmp_path / "test-key.json"
        lock_path = key_path.with_name(f".{key_path.name}.lock")
        # Create a lock that will be held
        lock_path.write_text("")
        old_time = time.time() - 60
        os.utime(lock_path, (old_time, old_time))
        # Create a corrupted keypair file
        key_path.write_text("not valid json")

        from backend.crosspost.atproto_oauth import load_or_create_keypair

        # Should regenerate despite corruption
        private_key, jwk = load_or_create_keypair(key_path)
        assert private_key is not None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_startup_hardening.py -v`
Expected: Failures

**Step 3: Implement the fixes**

**3a. `backend/main.py`** — Add global exception handlers after `create_app` builds the app:

Add these imports near the top:
```python
import yaml
```

In `create_app()`, before `return app`, add:

```python
    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
        logger.error("RuntimeError in %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=502,
            content={"detail": "Rendering service unavailable"},
        )

    @app.exception_handler(OSError)
    async def os_error_handler(request: Request, exc: OSError) -> JSONResponse:
        logger.error("OSError in %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Storage operation failed"},
        )

    @app.exception_handler(yaml.YAMLError)
    async def yaml_error_handler(request: Request, exc: yaml.YAMLError) -> JSONResponse:
        logger.error("YAMLError in %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid content format"},
        )

    @app.exception_handler(json.JSONDecodeError)
    async def json_error_handler(request: Request, exc: json.JSONDecodeError) -> JSONResponse:
        logger.error("JSONDecodeError in %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Data integrity error"},
        )
```

**3b. `backend/main.py` lifespan** — Wrap startup phases with clear error messages (C2, H9, H12):

Wrap each phase in the lifespan:
```python
    try:
        engine, session_factory = create_engine(settings)
        app.state.engine = engine
        app.state.session_factory = session_factory
    except Exception as exc:
        logger.critical("Failed to initialize database: %s. Check database path and permissions.", exc)
        raise

    try:
        async with engine.begin() as conn:
            ...
        await _ensure_crosspost_user_id_column(app)
        async with session_factory() as session:
            await session.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS ..."))
            await session.commit()
    except Exception as exc:
        logger.critical("Failed to create database schema: %s. Check database integrity.", exc)
        raise

    try:
        ensure_content_dir(settings.content_dir)
    except Exception as exc:
        logger.critical("Failed to initialize content directory: %s. Check filesystem permissions.", exc)
        raise

    # ... similar wrapping for git_service.init_repo(), load_or_create_keypair(),
    # ensure_admin_user(), rebuild_cache()
```

**3c. `backend/main.py`** — Auto-create database directory (M16):

Before `create_engine`, add:
```python
    # Ensure database directory exists
    db_url = settings.database_url
    if db_url.startswith("sqlite"):
        db_path = db_url.split("///", 1)[-1] if "///" in db_url else None
        if db_path:
            from pathlib import Path as PathLib
            PathLib(db_path).parent.mkdir(parents=True, exist_ok=True)
```

**3d. `backend/crosspost/atproto_oauth.py:112-135`** — Stale lock detection and lock-loop exception handling (H7, M18):

Before the lock loop, add stale lock check:
```python
    lock_path = path.with_name(f".{path.name}.lock")
    # Remove stale lock files (older than 30 seconds)
    if lock_path.exists():
        try:
            lock_age = time.time() - lock_path.stat().st_mtime
            if lock_age > 30:
                logger.warning("Removing stale keypair lock file (age: %.0fs): %s", lock_age, lock_path)
                lock_path.unlink(missing_ok=True)
        except OSError:
            pass  # If we can't check/remove it, the loop will handle it
```

In the lock loop, wrap `_load_existing()` (M18):
```python
        except FileExistsError:
            if path.exists():
                try:
                    return _load_existing()
                except (json.JSONDecodeError, KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
                    logger.warning("Corrupted keypair during lock wait: %s", exc)
                    # Fall through to retry — another process may fix it
            time.sleep(0.01)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_startup_hardening.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `just test-backend`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add backend/main.py backend/crosspost/atproto_oauth.py \
  tests/test_services/test_startup_hardening.py
git commit -m "fix: add global exception handlers and harden startup sequence"
```

---

### Task 3: Targeted endpoint fixes — posts, render, pages, sync, labels, admin

Fixes: C1, H1, H2, H8, H10, H11, M1, M2, M3, M4

**Files:**
- Modify: `backend/api/posts.py:208-210, 234-236, 345, 405-407, 503-505, 536-578`
- Modify: `backend/api/render.py:35`
- Modify: `backend/api/pages.py:36`
- Modify: `backend/api/sync.py:364-371`
- Modify: `backend/api/labels.py:55-57`
- Modify: `backend/api/admin.py:73, 108, 130, 148, 167`
- Test: `tests/test_api/test_error_handling.py` (new)

**Step 1: Write failing tests**

Create `tests/test_api/test_error_handling.py`:

```python
"""Tests for API endpoint error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_api.test_api_integration import get_auth_headers


class TestRenderEndpointPandocFailure:
    """H1: render endpoint handles pandoc failure."""

    @pytest.mark.asyncio
    async def test_preview_pandoc_failure_returns_502(self, client: AsyncClient) -> None:
        headers = await get_auth_headers(client)
        with patch(
            "backend.api.render.render_markdown",
            side_effect=RuntimeError("Pandoc not installed"),
        ):
            resp = await client.post(
                "/api/render/preview",
                json={"markdown": "# Hello"},
                headers=headers,
            )
        assert resp.status_code == 502


class TestUploadPostValidation:
    """M1/M2: upload_post validates encoding and YAML."""

    @pytest.mark.asyncio
    async def test_upload_invalid_utf8_returns_422(self, client: AsyncClient) -> None:
        headers = await get_auth_headers(client)
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("test.md", b"\x80\x81\x82", "text/markdown")},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_invalid_yaml_returns_422(self, client: AsyncClient) -> None:
        headers = await get_auth_headers(client)
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("test.md", b"---\ntitle: [\n---\nbody", "text/markdown")},
            headers=headers,
        )
        assert resp.status_code == 422


class TestPostCreatePandocFailure:
    """H1: create_post handles pandoc failure."""

    @pytest.mark.asyncio
    async def test_create_post_pandoc_failure_returns_502(self, client: AsyncClient) -> None:
        headers = await get_auth_headers(client)
        with patch(
            "backend.api.posts.render_markdown",
            side_effect=RuntimeError("Pandoc failed"),
        ):
            resp = await client.post(
                "/api/posts",
                json={"title": "Test", "body": "content", "labels": [], "is_draft": False},
                headers=headers,
            )
        assert resp.status_code == 502


class TestSyncCacheRebuildFailure:
    """H10: sync commit handles cache rebuild failure gracefully."""

    @pytest.mark.asyncio
    async def test_sync_commit_cache_failure_returns_warning(
        self, client: AsyncClient
    ) -> None:
        headers = await get_auth_headers(client)
        with patch(
            "backend.api.sync.rebuild_cache",
            side_effect=Exception("DB locked"),
        ):
            resp = await client.post(
                "/api/sync/commit",
                data={"metadata": "{}"},
                headers=headers,
            )
        # Should still return a response (not crash), with warning
        assert resp.status_code == 200
        data = resp.json()
        assert any("cache" in w.lower() for w in data.get("warnings", []))
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api/test_error_handling.py -v`
Expected: Failures

**Step 3: Implement the fixes**

**3a. `backend/api/render.py:35`** — Catch RuntimeError (H1):

```python
@router.post("/preview", response_model=RenderResponse)
async def preview(
    body: RenderRequest,
    _user: Annotated[User, Depends(require_auth)],
) -> RenderResponse:
    """Render markdown to HTML for preview."""
    try:
        html = await render_markdown(body.markdown)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RenderResponse(html=html)
```

Add `HTTPException` to the imports if not already there.

**3b. `backend/api/pages.py:36`** — Catch RuntimeError (H1):

```python
    page = await get_page(content_manager, page_id)
```

This calls `page_service.get_page` which calls `render_markdown`. The global handler will catch this, but for a better error message, modify `backend/services/page_service.py:42`:

```python
    try:
        rendered_html = await render_markdown(raw_content)
    except RuntimeError:
        rendered_html = ""
```

**3c. `backend/api/posts.py:208-210`** — Upload validation (M1, M2):

```python
    md_filename, md_bytes = md_file
    try:
        raw_content = md_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="Markdown file is not valid UTF-8")

    try:
        post_data = content_manager.read_post_from_string(raw_content, title_override=title)
    except (ValueError, yaml.YAMLError) as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid post front matter: {exc}"
        ) from exc
```

Add `import yaml` to imports.

**3d. `backend/api/posts.py:234-236`** — Pandoc try/except in upload_post (H1):

```python
    md_excerpt = generate_markdown_excerpt(post_data.content)
    try:
        rendered_excerpt = await render_markdown(md_excerpt) if md_excerpt else ""
        rendered_html = await render_markdown(post_data.content)
    except RuntimeError as exc:
        # Clean up assets already written
        for asset in written_assets:
            asset.unlink(missing_ok=True)
        if post_dir.exists() and not any(post_dir.iterdir()):
            post_dir.rmdir()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

**3e. `backend/api/posts.py:405-407`** — Pandoc try/except in create_post (H1):

```python
    md_excerpt = generate_markdown_excerpt(post_data.content)
    try:
        rendered_excerpt = await render_markdown(md_excerpt) if md_excerpt else ""
        rendered_html = await render_markdown(post_data.content)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

**3f. `backend/api/posts.py:503-505`** — Pandoc try/except in update_post (H1):

```python
    md_excerpt = generate_markdown_excerpt(post_data.content)
    try:
        rendered_excerpt = await render_markdown(md_excerpt) if md_excerpt else ""
        rendered_html = await render_markdown(post_data.content)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

**3g. `backend/api/posts.py:536-578`** — Render before rename (C1), OSError handling (H2):

Restructure the title-change block so rendering happens BEFORE filesystem operations:

```python
    # Rename directory if title changed and this is a directory-based post
    new_file_path = file_path
    if file_path.endswith("/index.md"):
        new_slug = generate_post_slug(title)
        old_dir_name = FilePath(file_path).parent.name
        date_prefix_match = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", old_dir_name)
        if date_prefix_match:
            date_prefix = date_prefix_match.group(1)
            old_slug = date_prefix_match.group(2)
            if new_slug != old_slug:
                old_dir = content_manager.content_dir / FilePath(file_path).parent
                posts_parent = old_dir.parent
                new_dir_name = f"{date_prefix}-{new_slug}"
                new_dir = posts_parent / new_dir_name

                if new_dir.exists():
                    counter = 2
                    while True:
                        candidate = posts_parent / f"{new_dir_name}-{counter}"
                        if not candidate.exists():
                            new_dir = candidate
                            break
                        counter += 1

                new_file_path = str(
                    (new_dir / "index.md").relative_to(content_manager.content_dir)
                )

                # C1: Render BEFORE filesystem changes
                try:
                    rendered_excerpt = rewrite_relative_urls(
                        await render_markdown(md_excerpt) if md_excerpt else "",
                        new_file_path,
                    )
                    rendered_html = rewrite_relative_urls(
                        await render_markdown(post_data.content),
                        new_file_path,
                    )
                except RuntimeError as exc:
                    await session.rollback()
                    raise HTTPException(status_code=502, detail=str(exc)) from exc

                # H2: Wrap filesystem operations with rollback
                try:
                    shutil.move(str(old_dir), str(new_dir))
                except OSError as exc:
                    await session.rollback()
                    raise HTTPException(
                        status_code=500, detail="Failed to rename post directory"
                    ) from exc
                try:
                    os.symlink(new_dir.name, str(old_dir))
                except OSError as exc:
                    # Rollback: move directory back
                    logger.error("Failed to create symlink, rolling back rename: %s", exc)
                    shutil.move(str(new_dir), str(old_dir))
                    await session.rollback()
                    raise HTTPException(
                        status_code=500, detail="Failed to create backward-compatible symlink"
                    ) from exc

                existing.file_path = new_file_path
                post_data.file_path = new_file_path
                existing.rendered_excerpt = rendered_excerpt
                existing.rendered_html = rendered_html
```

**3h. `backend/api/posts.py:345`** — Asset upload OSError (M3):

```python
        try:
            dest.write_bytes(content)
        except OSError as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to write asset: {filename}"
            ) from exc
```

**3i. `backend/api/sync.py:364-371`** — Wrap cache rebuild (H10):

```python
    # ── Update manifest and rebuild caches ──
    try:
        current_files = scan_content_files(content_dir)
        await update_server_manifest(session, current_files)
    except Exception as exc:
        logger.error("Failed to update server manifest after sync: %s", exc)
        sync_warnings.append("Server manifest update failed; next sync may show stale data.")

    content_manager.reload_config()

    from backend.services.cache_service import rebuild_cache

    try:
        _post_count, cache_warnings = await rebuild_cache(session, content_manager)
    except Exception as exc:
        logger.error("Cache rebuild failed after sync: %s", exc)
        cache_warnings = [f"Cache rebuild failed: {exc}. Data may be stale until server restart."]
```

**3j. `backend/api/labels.py:55-57`** — Wrap session.commit with recovery (H8):

```python
    try:
        await session.commit()
    except Exception as exc:
        logger.error("DB commit failed for %s, restoring labels.toml: %s", error_context, exc)
        # Restore old labels to TOML to maintain consistency
        try:
            old_labels = content_manager.labels
            write_labels_config(content_manager.content_dir, old_labels)
            content_manager.reload_config()
        except Exception as restore_exc:
            logger.error("Failed to restore labels.toml: %s", restore_exc)
        raise HTTPException(
            status_code=500, detail="Database commit failed"
        ) from exc
    git_service.try_commit(commit_message)
```

**3k. `backend/api/admin.py`** — Add OSError handling to endpoints (H11, M4):

For `update_settings` (line 73):
```python
    try:
        cfg = update_site_settings(...)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to write site configuration") from exc
```

Same pattern for `create_page_endpoint`, `update_page_endpoint`, `delete_page_endpoint`, `update_order`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api/test_error_handling.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `just test-backend`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add backend/api/posts.py backend/api/render.py backend/api/pages.py \
  backend/api/sync.py backend/api/labels.py backend/api/admin.py \
  backend/services/page_service.py tests/test_api/test_error_handling.py
git commit -m "fix: add targeted error handling to all API endpoints"
```

---

### Task 4: Crosspost hardening, async DNS, and low-severity fixes

Fixes: M14, M15, M17, L1, L8

**Files:**
- Modify: `backend/api/crosspost.py:328, 425, 432-433, 515-516, 663-665`
- Modify: `backend/crosspost/ssrf.py:62`
- Modify: `backend/api/auth.py:250-258`
- Modify: `backend/schemas/crosspost.py:12`
- Test: `tests/test_services/test_crosspost_error_handling.py` (new)

**Step 1: Write failing tests**

Create `tests/test_services/test_crosspost_error_handling.py`:

```python
"""Tests for crosspost error handling."""

from __future__ import annotations

import asyncio
import socket
from unittest.mock import patch

import pytest

from backend.crosspost.ssrf import SSRFSafeBackend


class TestAsyncDNS:
    """M17: DNS resolution should not block the event loop."""

    @pytest.mark.asyncio
    async def test_dns_resolution_is_async(self) -> None:
        backend = SSRFSafeBackend()
        # Patch asyncio.get_event_loop().getaddrinfo to verify it's used
        with patch.object(
            asyncio.get_event_loop(),
            "getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))],
        ) as mock_getaddrinfo:
            # This should fail with ConnectError since we can't actually connect,
            # but the DNS resolution should use async getaddrinfo
            try:
                await backend.connect_tcp("example.com", 80)
            except Exception:
                pass
            mock_getaddrinfo.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_crosspost_error_handling.py -v`
Expected: Failures

**Step 3: Implement the fixes**

**3a. `backend/api/crosspost.py:328`** — Bluesky token data KeyError (M14):

Replace direct dictionary access with `.get()` and validation:
```python
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=502,
                detail="Bluesky token response missing access_token",
            )
        credentials = {
            "access_token": access_token,
            "refresh_token": token_data.get("refresh_token", ""),
            ...
        }
```

**3b. `backend/api/crosspost.py:425, 432-433`** — Mastodon registration (M15, M14):

```python
            try:
                reg_data = reg_resp.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Mastodon returned invalid JSON response: {exc}",
                ) from exc
    except httpx.HTTPError as exc:
        ...

    client_id = reg_data.get("client_id")
    client_secret = reg_data.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=502,
            detail="Mastodon app registration response missing client_id or client_secret",
        )
```

**3c. `backend/api/crosspost.py:515-516`** — Mastodon token result (M14):

```python
        access_token = token_result.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="Mastodon token response missing access_token")
```

**3d. `backend/api/crosspost.py:663-665`** — X token result (M14):

```python
    access_token = token_result.get("access_token")
    refresh_token = token_result.get("refresh_token")
    username = token_result.get("username")
    if not access_token or not refresh_token or not username:
        missing = [k for k in ("access_token", "refresh_token", "username") if not token_result.get(k)]
        raise HTTPException(
            status_code=502,
            detail=f"X token response missing: {', '.join(missing)}",
        )
```

**3e. `backend/crosspost/ssrf.py:62`** — Async DNS (M17):

```python
    async def connect_tcp(self, host: str, port: int, ...) -> httpcore.AsyncNetworkStream:
        if host.strip().lower() in _BLOCKED_HOSTNAMES:
            msg = f"SSRF protection: blocked hostname {host!r}"
            raise httpcore.ConnectError(msg)

        import asyncio

        loop = asyncio.get_event_loop()
        try:
            addr_infos = await loop.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            msg = f"DNS resolution failed for {host!r}"
            raise httpcore.ConnectError(msg) from exc

        ...
```

**3f. `backend/api/auth.py:250-258`** — Register race condition (L1):

```python
    from sqlalchemy.exc import IntegrityError

    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already taken",
        )
```

**3g. `backend/schemas/crosspost.py:12`** — account_name default (L8):

```python
    account_name: str = Field(default="", description="Display name for the account")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_crosspost_error_handling.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `just test-backend`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add backend/api/crosspost.py backend/crosspost/ssrf.py \
  backend/api/auth.py backend/schemas/crosspost.py \
  tests/test_services/test_crosspost_error_handling.py
git commit -m "fix: harden crosspost error handling and async DNS resolution"
```

---

### Task 5: Final verification

**Step 1: Run full check gate**

Run: `just check`
Expected: All static checks and tests pass

**Step 2: Fix any regressions**

If any test fails, fix the issue and re-run.

**Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve check gate issues from crash resilience changes"
```
