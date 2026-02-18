# Project Development History

1. [Initial prompt](initial_prompt.md). Used with Claude Code (Opus 4.6 High Effort) to create the [initial plan](initial_plan.md).
2. Claude Code created project scaffolding (no code yet).
3. Claude implemented the initial plan, all phases. Used the frontend-design skill and Playwright MCP for testing.
4. Used the `review-pr` skill from the `pr-review-toolkit` to review. I didn't save the review, but it found quite a few issues and fixed them.
5. Created infra: justfile, README.md, AGENTS.md, docs/ARCHITECTURE.md
6. Used `review-pr` to review the entire codebase in its current state (not just recent changes): [review_2.md](review_2.md). Claude Code fixed all the issues in 15min.
