# Getting started

## Choose your path

Use the **source repository** for the complete Agent Skill, examples and prompts. Installing a Python wheel supplies command-line modules; it is not a substitute for the complete skill directory.

Use Python 3.10+ and run from the repository root. No package index publication is assumed: install from this local checkout, not a guessed public package name.

### No-install core

```sh
python3 scripts/arc.py capabilities
python3 scripts/arc.py preflight examples/quickstart/plan.json
python3 scripts/arc.py compile examples/quickstart/plan.json --out ./first-map --strict-review
python3 scripts/arc.py validate-delivery ./first-map
```

The output is a new directory containing `map.odenmap/`, `plan.json`, `delivery.json`, `review.json` and any copied `Sources/`. A `.odenmap` is a directory package, not a renamed ZIP. Preserve the entire delivery for provenance.

### Editable CLI installation

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
oden-arc capabilities
oden-arc-memory --help
oden-arc-assets --help
```

On Windows, activate `.venv\Scripts\activate` using the appropriate shell. The tools are portable Python; the OdenMap application is a separate runtime.

### Optional dependencies

```sh
# Image crops only (Pillow)
python3 -m pip install -e '.[images]'

# PDF text extraction and PDF crops: review THIRD_PARTY.md first
python3 -m pip install -e '.[pdf]'

# JSON Schema checks; media tests remain optional
python3 -m pip install -e '.[test]'
```

The `pdf` extra includes Pillow and PyMuPDF. PyMuPDF uses AGPL/commercial terms; an MIT license on ARC does not replace those terms. Keep this tool separate from the OdenMap application and review the actual deployment before combining components. Do not install the unrelated package named `fitz`.

## Bring your materials

An AI assistant should read `SKILL.md`, infer your goal, inspect the relevant sources and write a MapPlan. Begin with `assets/templates/minimal-plan.json` or `examples/quickstart/plan.json`. File paths must resolve within the plan directory; stage authorized source copies there when necessary.

The compiler does not summarize documents on its own. It rejects structurally inconsistent plans and altered source files, but the assistant or a human must verify the meaning.

## Large tasks

Keep the workspace **outside the repository**, on storage that survives your AI host's sessions:

```sh
python3 scripts/arc_memory.py --workspace ../arc-work init --goal assets/templates/goal.json
python3 scripts/arc_memory.py --workspace ../arc-work ingest examples/quickstart/source.md
python3 scripts/arc_memory.py --workspace ../arc-work recover
python3 scripts/arc_memory.py --workspace ../arc-work next --worker reader --limit 4 --budget-bytes 24000
```

`next` returns a lease and source units. The AI reads them, writes a result matching `schemas/memory-result.schema.json`, then submits it with `commit`. Do not submit the blank template as actual evidence. Follow [the complete protocol](../references/memory-protocol.md) for leases, partial work, recovery and backups.

## Read-only previews and native verification

ARC does not launch OdenMap. Open the generated map yourself, inspect resources and formula editing, save a new copy, close it, and reopen it. Record what actually ran. A successful static check is not a claim that the application was tested.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Output already exists | Use a new output directory; do not delete user files automatically. |
| Source or asset hash mismatch | Inspect the changed material and update the plan only after review. |
| PDF backend unavailable | Review licensing, install the `pdf` extra, or provide host-extracted units. |
| Skill appears to have no tools | Supply the full repository, not only `SKILL.md`. |
| Queue is empty but work is incomplete | Check leased, partial, blocked and excluded units with `status`. |
| Retrieval misses a paraphrase | Add verified aliases or inspect the room/source index; retrieval is lexical, not embedding-based. |
| Context was compacted or the model changed | Reset the session epoch; do not reuse acknowledgements from the old context. |
