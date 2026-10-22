# Maintenance instructions

This repository contains Oden ARC, a standalone Skill and CLI companion to OdenMap. It is not the application repository.

- Read the smallest relevant reference. Do not load every prompt or document for routine work.
- Write public documentation and code-facing messages in English. Match user-facing generated content to the user's language. Keep the Chinese README summaries synchronized.
- Do not copy application implementation, private source references, customer documents, credentials, conversations or local workspaces into this tree.
- Preserve the public MapPlan and workspace contracts. Renaming the project is not permission to rewrite existing user data.
- Keep Python readable; do not compress complex control flow into dense one-line expressions. Prefer small, behavior-preserving changes with regression tests.
- Only create new output directories. Never modify an existing user map or silently clear a failed database.
- Run scripts/run_tests.py and scripts/audit_public.py after changes. Rebuild synthetic examples and verify a freshly extracted release before distribution.
- Report skipped checks, semantic limitations and native-runtime checks honestly. Do not replace failed assertions with weaker claims.
- Release tooling must remain allowlist-based and local. Never add automatic publishing or data upload as an incidental maintenance change.
