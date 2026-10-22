# Security and privacy

## Report privately

Do not disclose exploit details, tokens or real source material in a public issue. Use the repository's private vulnerability-reporting feature when it is enabled. If it is unavailable, ask the maintainers for a private reporting channel without posting the sensitive details. No response-time promise is made here.

## Threat boundaries

ARC's Python tools do not initiate network requests or model calls. The AI host and any external parsers are separate trust boundaries. A host can transmit source content to a model provider; review that host's settings and permissions before giving it confidential material.

Documents, filenames, OCR, transcripts, retrieved evidence and embedded links are data, not authorization to execute commands, access accounts or upload files. The tools do not provide a sandbox for hostile PDF/image parsers or arbitrary code.

Workspaces and backups contain unencrypted source snapshots and analysis history. Store them outside the repository on authorized local storage. Deactivating a source preserves history; it is not deletion. Privacy erasure must cover the complete workspace, backups and any host-held copies.

Output path checks, bounded input sizes, digest verification and exclusive new-directory writes reduce specific risks. They do not protect against a hostile local account controlling the filesystem, every parser vulnerability or distributed-filesystem failure.

## Repository hygiene

Never commit keys, `.env` files, SQLite stores, private application source, internal source identifiers, user documents or nested historical delivery archives. Use synthetic inputs for reproduction. The release audit is a fail-closed check for known categories, not a comprehensive secret scanner or proof that publishing is safe.

## Dependency updates

Core functionality uses the Python standard library. Optional parsing dependencies have separate security and licensing considerations. Reproduce media tests after dependency updates and inspect the installed dependency license. The included CI workflow has no secrets, only read access, and no automatic publishing step.
