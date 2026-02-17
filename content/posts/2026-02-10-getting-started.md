---
created_at: 2026-02-10 10:00:00.000000+00
modified_at: 2026-02-10 10:00:00.000000+00
author: Admin
labels: ["#swe"]
---
# Getting Started with AgBlogger

AgBlogger makes it easy to publish your thoughts.

## Writing Posts

Posts are written in standard Markdown with YAML front matter. Simply create a `.md` file in the `content/posts/` directory.

## Front Matter

Every post starts with YAML front matter between `---` delimiters:

```yaml
---
created_at: 2026-02-10
author: Your Name
labels: ["#tech", "#tutorial"]
---
```

## Labels

Labels organize your posts into categories. They form a directed acyclic graph (DAG), so you can create hierarchical taxonomies.

## Syncing

Use the CLI tool to sync your local content directory with the server:

```bash
agblogger-sync sync
```

That's it! Your posts are now live.
