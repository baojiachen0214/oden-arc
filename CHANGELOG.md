# Changelog

## Public source packaging

- Standardize the OdenMap product name, official icon and website links across the English and Chinese introductions.
- Clarify that the OdenMap application stays closed source and its icon is excluded from ARC’s MIT license.
- Canonicalize macOS system temporary directories for disposable test/example fixtures while retaining strict user-path checks.
- Preserve stable skill, CLI and file-format identifiers.

Implementation versions track changes to this toolkit; they are not OdenMap application versions.

## 0.5.0

### Public project structure
- Introduced the Oden ARC name and English-first documentation with Simplified and Traditional Chinese entry points.
- Separated user guides, agent references, prompts, synthetic examples and release tooling.
- Renamed the Python package and CLI entry points while retaining existing wire and workspace identifiers.
- Added contribution and security policies, dependency licensing notes, CI configuration and public-source auditing.
- Replaced internal compatibility references with a documented file-output profile.
- Added a new dependency-free English quick-start example and transparent vector branding.
- Excluded historical delivery archives, local workspaces, built maps, internal reports and source-checkout references from public packaging.

### Compatibility
The native data profile and durable workspace behavior remain unchanged. Existing plans retain deterministic object IDs. CLI wrapper filenames changed; see `docs/getting-started.md`. Native application display/edit/save/reopen validation remains a separate check.
