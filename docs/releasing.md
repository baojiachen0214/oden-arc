# Preparing a public source release

The public source tree is the release input. Keep internal notes and real workspaces elsewhere. A source ZIP is not automatically published, and this repository includes no publish/deploy credentials or workflow.

1. Review `LICENSE`, `THIRD_PARTY.md`, public API changes and synthetic fixture provenance.
2. Run `python3 scripts/run_tests.py` and `python3 scripts/audit_public.py`.
3. Confirm English and Chinese README scope, commands and privacy statements agree.
4. Set the implementation version in `src/oden_arc/__init__.py` and record changes in `CHANGELOG.md`; the README remains a product introduction.
5. Build outside the checkout: `python3 scripts/repack.py --out ../oden-arc-source.zip`.
6. Extract into a new directory, run `python3 scripts/verify_bundle.py --strict`, rerun tests, and execute the quick start there.
7. Review the exact ZIP inventory and any independent secret-scan findings before manually uploading it to the chosen public repository.

The packer excludes Git history, old delivery reports, generated maps, databases, cache directories, credentials and unrelated files. It validates required source and documentation paths; its inventory has SHA-256 digests. Digests detect changes relative to the manifest, not authorship or an independent signature.

The release audit checks defined patterns and formats; it is not a proof of intellectual-property ownership, trademark clearance, absence of every possible secret, or safety of every binary. Future contributors must supply authorized sources and reviewers must inspect changes. Do not add private identifiers to a public denylist merely to prove that they have been removed.

## Host compatibility record

When native testing is available, record the publicly identifiable application version, platform, observed behavior and synthetic input. Do not include private application source paths or internal commits. Never claim runtime compatibility solely from compiler round-trip tests.

Example sources use `-text` Git attributes because digests cover original bytes, including line endings. Do not normalize or edit a fixture without reviewing the change and updating its dependent records.
