# Project Development History

1. [Initial prompt](initial_prompt.md). Used with Claude Code (Opus 4.6 High Effort) to create the [initial plan](initial_plan.md).
2. Claude Code created project scaffolding (no code yet).
3. Claude implemented the initial plan, all phases. Used the frontend-design skill and Playwright MCP for testing.
4. Used the `review-pr` skill from the `pr-review-toolkit` to review. I didn't save the review, but it found quite a few issues and fixed them.
5. Created infra: justfile, README.md, AGENTS.md, docs/ARCHITECTURE.md
6. Used `review-pr` to review the entire codebase in its current state (not just recent changes): [review_2.md](review_2.md). Claude Code fixed all the issues in 15min.
7. Used the playwright mcp to test the application end-to-end.
  - Fix KaTeX math rendering.
  - Fix code block highlighting.
  - Allow multiple parents for labels.
  - In the web editor, front matter should not be directly editable or visible in the editor text field. There should be UI controls above the text field to edit the front matter:
    - labels: select existing or immediately create new one, (separate field, like hashtags on twitter or other social media platforms),
    - date created/modified: not editable from the UI, filled in / updated automatically
    The user directly edits only the blog post content (except front matter).
