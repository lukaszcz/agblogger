Review the backend for any code that may potentially result in crashing the server. It is CRITICAL that the server never crashes. We are aiming for a production-grade high-reliability server with 100% uptime. All exceptions need to be handled. No exceptions may be silently ignored or crash the server.

Investigate all potential causes of race conditions, including unsynchronized access to mutable state, missing or incorrect locking, non-atomic compound operations, check-then-act patterns, improper initialization, read-modify-write races.

Pay attention to external sources of failure, particularly to potential errors from interacting with: database, network, filesystem, pandoc, git. Failures of external services should ALWAYS be handled gracefully.

Check if invalid content (e.g. invalid markdown, toml, yaml) is handled gracefully.
