# Pandoc Server Mode Design

## Problem

Each markdown render spawns a new `pandoc` subprocess. Pandoc is a Haskell binary with non-negligible startup cost (~50-100ms). Under load (cache rebuild of many posts, concurrent preview requests), this means N cold starts — wasted time and process churn.

## Solution

Run `pandoc` as a long-lived HTTP server (`pandoc-server`) and send render requests over localhost HTTP instead of spawning subprocesses.

## Architecture

### New module: `backend/pandoc/server.py`

A `PandocServer` class managing a `pandoc-server` child process:

- **Startup**: spawned via `asyncio.create_subprocess_exec` during FastAPI lifespan, before cache rebuild. Binds to `127.0.0.1` on a configurable port (default 3031). Health-checked with a retry loop before proceeding.
- **Shutdown**: `process.terminate()` + `process.wait()` in the lifespan teardown. Child process is also cleaned up if the parent is killed (process group inheritance).
- **Auto-restart**: if a render call gets a connection error, acquire an `asyncio.Lock`, check if the process is dead, restart it, and retry the request once.
- **Version check**: on startup, verify `+server` appears in `pandoc --version` output. Fail fast with a clear error if the installed pandoc lacks server support.

### Modified: `backend/pandoc/renderer.py`

`render_markdown()` changes from `asyncio.to_thread(subprocess.run(...))` to an async `httpx.AsyncClient.post()` to `http://127.0.0.1:{port}/`. Request body:

```json
{
  "text": "<markdown>",
  "from": "gfm+tex_math_dollars+footnotes+raw_html",
  "to": "html5",
  "html-math-method": {"method": "katex"},
  "highlight-style": "pygments",
  "wrap": "none"
}
```

Fully async — no `to_thread` needed. Per-request timeout of 10 seconds via httpx.

HTML sanitization (`_sanitize_html`) and heading anchors (`_add_heading_anchors`) remain unchanged, applied to the pandoc-server response.

### Modified: `backend/main.py`

Lifespan adds two steps:
- **Before cache rebuild**: start `PandocServer`, wait for health check.
- **After yield (shutdown)**: stop `PandocServer`.

The `PandocServer` instance is stored on `app.state.pandoc_server` for lifecycle management. The renderer accesses it via a module-level reference set during startup.

### Modified: `Dockerfile`

Replace `apt-get install pandoc` with a pinned download from GitHub releases to guarantee `+server` support. Target pandoc 3.6.x (latest stable with `+server`).

### No changes needed

- `docker-compose.yml` — pandoc-server is an internal child process, not a separate service.
- `Caddyfile` — pandoc-server binds to localhost only, invisible to the reverse proxy.
- All callers of `render_markdown()` — signature unchanged.

## Error Handling

| Scenario | Handling |
|----------|----------|
| Pandoc missing `+server` | Fail fast at startup with clear error message |
| Server not responding on startup | Retry with backoff (5 attempts, 0.5s intervals), then fail startup |
| Connection refused during render | Acquire restart lock, restart process, retry once |
| HTTP error from pandoc-server | Raise `RuntimeError` (same as current behavior) |
| 10s per-request timeout | `httpx.ReadTimeout` → `RuntimeError` |
| Process crash mid-operation | Same as connection refused — auto-restart + retry |

No subprocess fallback. If pandoc-server can't start, the application fails fast — same as today when `pandoc` is missing entirely.

## Testing

- Unit tests for `PandocServer` lifecycle (start, stop, restart on crash).
- Unit tests for the new HTTP-based `render_markdown` (mock httpx responses).
- Integration test: start server, render markdown, verify HTML output matches current behavior.
- Existing tests continue to work since `render_markdown` signature is unchanged.
