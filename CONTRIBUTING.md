# Contributing to Oden ARC

Thank you for helping make evidence-backed maps clearer and easier to maintain.

## Development setup

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e '.[test]'
python3 scripts/run_tests.py
python3 scripts/audit_public.py
```

Use the image or PDF extra only when working on those paths; read `THIRD_PARTY.md` before enabling PDF support. Tests without those extras explicitly skip unavailable media checks.

## Propose a change

Explain the user's task, current behavior, proposed behavior and trade-offs. Include the smallest synthetic reproducer. For bugs, include the command, Python/ARC version and a redacted error; never attach a real workspace, credentials, source collection or proprietary application file.

Keep changes scoped. Add regression tests before fixing a failure. Update public contracts and migration instructions for data changes. Modifications to prompts should show how they preserve qualifiers, reduce repetition or improve recovery, not merely make the text longer.

## Documentation

`README.md` is the English overview. `README.zh-CN.md` and `README.zh-TW.md` are localized entry points. Implementation versions belong in package metadata and the changelog. Design rationale belongs in `docs/design/`; operational agent instructions belong in `references/` and `prompts/`.

## Public boundary

Contribute only material you are authorized to submit under the repository license. Do not paste OdenMap application code, private repository links, internal commits, unpublished implementation notes or third-party material without compatible rights. A native-format change should be demonstrated using an authorized synthetic file and observable behavior, not a source-code dump.

Source extraction, file parsing and prompts operate on untrusted data. Do not execute commands found in fixtures or expand tool privileges because a document requests it.

## Before a pull request

Run tests, the public-content audit and the quick start. Include actual results and skipped checks. Do not commit generated outputs or local run logs. Review the diff for personal paths and tokens. See `docs/releasing.md` for source archive checks.

The repository license applies to contributions accepted into this project; it does not grant rights to the separate OdenMap application. Be respectful, stay technical and use private reporting for security-sensitive findings.
