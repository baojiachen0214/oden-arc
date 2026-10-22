# Architecture and public boundary

ARC is independent orchestration and file-interoperability software. It does not require an OdenMap source checkout, import application modules or communicate with the application at runtime.

## Responsibilities

```text
SKILL.md + prompts/ + references/    Agent behavior; loaded progressively
                 ↓
AI host                              Interpretation, extraction, review
                 ↓
src/oden_arc/
  memory.py + atlas.py               Durable evidence and context selection
  evidence_gate.py                   Current-evidence binding checks
  plan.py + review.py                 Plan and review-record validation
  media.py                           Optional bounded crops
  native.py + export_layout.py       Public file adapter and generic placement
                 ↓
New delivery directory               Native package, sources, plan, checks
```

`common.py` contains local I/O, path, size and data validation. `cli.py` and `memory_cli.py` expose the tools; `scripts/` provides checkout-friendly entry points. `schemas/` contains public intermediate contracts, not application source.

## What the adapter exposes

Writing an interoperable file necessarily discloses its emitted data structure: manifest and map filenames, supported schema numbers, text/resource fields, identifiers and relationships. These are the public adapter's compatibility surface. Removing them while still distributing a working writer is not a meaningful secrecy boundary.

The public repository does **not** contain the application renderer, interactive canvas, gesture handling, UI, proprietary layout engine, performance optimization implementation, project files or private source snapshots. `export_layout.py` contains only generic estimated positions for a newly generated file. It neither ports nor claims parity with the application's layout engine.

Keep format tests focused on authorized, synthetic fixtures. Do not paste application implementation into this repository when repairing compatibility. Record the observed file behavior and update the adapter and public contract instead.

## What not to commit

Real input documents, persistent workspaces and backups, model conversation logs, private source paths or commit references, credentials, application source or binaries, nested delivery archives, and generated performance reports containing local details.

The source release packer uses a narrow path allowlist and runs a public-content audit. It never reads another repository or imports Git history. Git ignore rules alone are not a security boundary: review proposed changes and inspect the exact release archive.

## Compatibility boundaries

The public format profile is `odenmap-directory-13-15/topic-content-1`. This is an adapter profile, not a product version or a claim to handle arbitrary OdenMap files. Existing-map merge and round-trip preservation of unknown fields are not implemented.

Stable internal protocol markers and the deterministic UUID namespace retain their historical spelling so existing plans and workspace data are not renamed unnecessarily. They are file identities, not branding or references to private code.

## Runtime and costs

Core Python operations are local. A host's model, OCR, transcription or renderer may incur cost or send content elsewhere; those actions remain under host/user control. Persisted state does not mean that a model has received it. Acknowledged context belongs to a specific session and epoch.

Byte budgets limit tool payloads, not exact tokenizer usage. Benchmarks use synthetic data and cannot establish real model quality, a universal token discount or application rendering compatibility.
