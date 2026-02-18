# Project Development History

1. [Initial prompt](initial_prompt.md). Used with Claude Code (Opus 4.6 High Effort) to create the [initial plan](initial_plan.md).
2. Claude Code created project scaffolding (no code yet).
3. Claude implemented the initial plan, all phases. Used the frontend-design skill and Playwright MCP for testing.
4. Used the `review-pr` skill from the `pr-review-toolkit` to review. I didn't save the review, but it found quite a few issues and fixed them.
5. Created infra: justfile, README.md, AGENTS.md, docs/ARCHITECTURE.md
6. Used `review-pr` to review the entire codebase in its current state (not just recent changes): [review_2.md](reviews/review_2.md). Claude Code fixed all the issues in 15min.
7. Used the playwright mcp to test the application end-to-end.
  - Fix KaTeX math rendering.
  - Fix code block highlighting.
8. Fixed YAML front matter editing. Used skills: frontend-design, superpowers:brainstorming
  - Prompt:
    ```markdown
    In the web editor, YAML front matter should not be directly editable or visible in the editor text field. There should be UI controls above the text field to edit the front matter:
      - labels: select existing or immediately create new one, (separate field, like hashtags on twitter or other social media platforms),
      - date created/modified: not editable from the UI, filled in / updated automatically,
      - author: not editable, filled in automatically from the logged-in user data
    In the text field, the user directly edits only the blog post content (without YAML front matter).
    ```
  - Questions: label UI, API endpoint for raw content, draft toggle UI.
9. Reviewed changes with `review-pr`, then fixed the issues.
10. Allow multiple parents for labels.
