# Testing

## Backend (pytest)

```
tests/
├── conftest.py                             Fixtures: tmp content dir, settings, DB engine/session
├── test_api/
│   ├── test_api_integration.py             Full API tests via httpx AsyncClient + ASGITransport
│   ├── test_api_security.py                Security-related API tests
│   ├── test_auth_hardening.py              Auth abuse protections and rate limiting
│   ├── test_bluesky_oauth_endpoints.py     Bluesky OAuth endpoint tests
│   ├── test_content_api.py                 Content serving API tests
│   ├── test_crosspost_api.py               Cross-post API tests
│   ├── test_draft_visibility.py            Draft access control tests
│   ├── test_path_safety_hypothesis.py      Property-based path safety checks
│   ├── test_post_assets_upload.py          Post asset upload tests
│   ├── test_post_directory.py              Post-per-directory tests
│   ├── test_post_rename.py                 Post rename/symlink tests
│   ├── test_post_upload.py                 Post file/folder upload tests
│   └── test_security_regressions.py        Security regression tests
├── test_cli/
│   ├── test_deploy_production.py           Deployment script tests
│   ├── test_safe_path.py                   CLI path safety tests
│   └── test_sync_client.py                 CLI sync client tests
├── test_labels/
│   ├── test_label_dag.py                   Label DAG operations
│   ├── test_label_dag_hypothesis.py        Property-based DAG cycle-breaking
│   └── test_label_service.py              Label service tests
├── test_rendering/
│   ├── test_frontmatter.py                 Frontmatter parsing tests
│   ├── test_renderer_no_dead_code.py       Renderer dead-code checks
│   └── test_url_rewriting.py              Relative URL rewriting tests
├── test_services/
│   ├── test_admin_service.py               Admin service operations
│   ├── test_atproto_oauth.py               AT Protocol OAuth tests
│   ├── test_auth_edge_cases.py             Auth edge case tests
│   ├── test_auth_service.py                Auth service operations
│   ├── test_bluesky_oauth_state.py         OAuth state store tests
│   ├── test_config.py                      Settings loading
│   ├── test_content_manager.py             ContentManager operations
│   ├── test_crosspost_decrypt_fallback.py  Credential decryption fallback
│   ├── test_crosspost_formatting.py        Cross-post text formatting
│   ├── test_crosspost.py                   Cross-posting platforms
│   ├── test_crypto_service.py              AES-256-GCM encryption
│   ├── test_database.py                    DB engine creation
│   ├── test_datetime_service.py            Date/time parsing
│   ├── test_ensure_content_dir.py          Content directory scaffolding
│   ├── test_frontmatter_hypothesis.py      Property-based frontmatter tests
│   ├── test_frontmatter_merge.py           Semantic front matter merge
│   ├── test_git_merge_file.py              git merge-file wrapper tests
│   ├── test_git_service.py                 Git service operations
│   ├── test_hybrid_merge.py                Hybrid merge (front matter + body)
│   ├── test_invite_code.py                 Invite code tests
│   ├── test_label_schema_validation.py     Label schema validation
│   ├── test_pat_last_used.py               PAT last-used tracking
│   ├── test_rate_limiter.py                Rate limiter tests
│   ├── test_scan_posts_exception.py        Post scanning error handling
│   ├── test_slug_service.py                Slug generation tests
│   ├── test_ssrf.py                        SSRF protection tests
│   ├── test_sync_merge_integration.py      Full sync merge API flow
│   ├── test_sync_normalization.py          Sync frontmatter normalization
│   ├── test_sync_service_hypothesis.py     Property-based sync invariants
│   ├── test_sync_service.py                Sync plan computation
│   ├── test_toml_manager.py                TOML config parsing
│   └── test_toml_validation.py             TOML input validation
└── test_sync/
    ├── test_normalize_frontmatter.py       Frontmatter normalization in sync
    └── test_sync_client.py                 Sync client integration tests
```

Configuration in `pyproject.toml`: `asyncio_mode = "auto"`, coverage via `pytest-cov`, `fail_under = 80` with branch coverage enabled.

Property-based testing is implemented with Hypothesis for high-invariant backend logic:
- sync plan classification and symmetry invariants
- front matter merge and normalization invariants
- label DAG cycle-breaking invariants
- URL/path safety invariants across rendering, sync, content serving, and CLI path resolution

## Frontend (Vitest)

Vitest with jsdom environment, `@testing-library/react`, and `@testing-library/user-event`. Test setup (`src/test/setup.ts`) fails tests on unexpected `console.error`/`console.warn` output.

```
src/
├── App.test.tsx
├── components/
│   ├── crosspost/__tests__/
│   │   ├── CrossPostDialog.test.tsx
│   │   ├── CrossPostHistory.test.tsx
│   │   ├── PlatformIcon.test.tsx
│   │   ├── SocialAccountsPanel.test.tsx
│   │   └── crosspostText.property.test.ts    Property-based (fast-check)
│   ├── editor/__tests__/
│   │   ├── LabelInput.test.tsx
│   │   ├── MarkdownToolbar.test.tsx
│   │   └── wrapSelection.property.test.ts    Property-based (fast-check)
│   ├── filters/__tests__/
│   │   └── FilterPanel.test.tsx
│   ├── labels/__tests__/
│   │   ├── LabelChip.test.tsx
│   │   └── graphUtils.property.test.ts       Property-based (fast-check)
│   ├── layout/__tests__/
│   │   └── Header.test.tsx
│   ├── posts/__tests__/
│   │   ├── PostCard.test.tsx
│   │   └── TableOfContents.test.tsx
│   └── share/__tests__/
│       ├── MastodonSharePrompt.test.tsx
│       ├── ShareBar.test.tsx
│       ├── ShareButton.test.tsx
│       └── shareUtils.property.test.ts       Property-based (fast-check)
├── pages/__tests__/
│   ├── AdminPage.test.tsx
│   ├── EditorPage.test.tsx
│   ├── LabelGraphPage.test.tsx
│   ├── LabelPostsPage.test.tsx
│   ├── LabelSettingsPage.test.tsx
│   ├── LabelsPage.test.tsx
│   ├── LoginPage.test.tsx
│   ├── PageViewPage.test.tsx
│   ├── PostPage.test.tsx
│   ├── SearchPage.test.tsx
│   └── TimelinePage.test.tsx
└── stores/__tests__/
    └── authStore.test.ts
```

Coverage thresholds: statements 80%, branches 70%, functions 80%, lines 80%.

Property-based testing is implemented with `fast-check` for deterministic frontend logic:
- share utility invariants (`shareUtils`): URL/query encoding, hostname validation, and platform fallbacks
- editor transformation invariants (`wrapSelection`): splice correctness, cursor bounds, and block newline semantics
- label graph invariants (`graphUtils`): cycle detection, depth computation, and descendant traversal
- cross-post text/url invariants (`crosspostText`): post-path normalization and hashtag truncation/content assembly
