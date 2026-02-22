# Testing

## Backend (pytest)

```
tests/
├── conftest.py                  Fixtures: tmp content dir, settings, DB engine/session
├── test_api/
│   └── test_api_integration.py  Full API tests via httpx AsyncClient + ASGITransport
├── test_services/
│   ├── test_config.py           Settings loading
│   ├── test_content_manager.py  ContentManager operations
│   ├── test_crosspost.py        Cross-posting platforms
│   ├── test_database.py         DB engine creation
│   ├── test_datetime_service.py Date/time parsing
│   ├── test_git_service.py      Git service operations
│   ├── test_git_merge_file.py   git merge-file wrapper tests
│   ├── test_frontmatter_merge.py  Semantic front matter merge tests
│   ├── test_frontmatter_hypothesis.py  Property-based front matter merge/normalization tests
│   ├── test_hybrid_merge.py     Hybrid merge (front matter + body) tests
│   ├── test_sync_service.py     Sync plan computation
│   ├── test_sync_service_hypothesis.py  Property-based sync state-machine invariants
│   └── test_sync_merge_integration.py  Full sync merge API flow
├── test_sync/                   CLI sync client tests
├── test_labels/                 Label service tests (+ property-based DAG checks)
├── test_api/                    Endpoint integration/security tests (+ property-based path safety checks)
└── test_rendering/              Pandoc rendering tests
```

Configuration in `pyproject.toml`: `asyncio_mode = "auto"`, coverage via `pytest-cov`.

Property-based testing is implemented with Hypothesis for high-invariant backend logic:
- sync plan classification and symmetry invariants
- front matter merge and normalization invariants
- label DAG cycle-breaking invariants
- URL/path safety invariants across rendering, sync, content serving, and CLI path resolution

## Frontend (Vitest)

Vitest with jsdom environment, `@testing-library/react`, and `@testing-library/user-event`.

Property-based testing is implemented with `fast-check` for deterministic frontend logic:
- share utility invariants (`shareUtils`): URL/query encoding, hostname validation, and platform fallbacks
- editor transformation invariants (`wrapSelection`): splice correctness, cursor bounds, and block newline semantics
- label graph invariants (`graphUtils`): cycle detection, depth computation, and descendant traversal
- cross-post text/url invariants (`crosspostText`): post-path normalization and hashtag truncation/content assembly
