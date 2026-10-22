<p align="center">
  <img src="assets/brand/logo.png" width="104" height="104" alt="OdenMap app icon">
</p>
<h1 align="center">Oden ARC</h1>
<p align="center"><strong>From scattered sources to clear, traceable maps.</strong></p>
<p align="center">An open-source AI skill and local toolkit for OdenMap</p>
<p align="center">English · <a href="README.zh-CN.md">简体中文</a> · <a href="README.zh-TW.md">繁體中文</a></p>

Oden ARC helps an AI assistant turn documents, images, tables and other source material into useful **OdenMap** mind maps—with editable formulas, resource cards, notes and traceable evidence.

It combines an **Agent Skill**, a **local command-line toolkit**, and **resumable evidence memory**. Your AI host interprets the material; ARC organizes state, validates references and creates new `.odenmap` files. It does not run a model or require an API account of its own.

**[OdenMap website & Mac beta](https://baojiachen0214.github.io/oden-website/)** · [Source repository](https://github.com/baojiachen0214/oden-arc)

**OdenMap is a separate, closed-source native Swift app.** This repository opens only the companion skill, Python tools, documentation and synthetic examples.

## Why ARC?

- **Meaning before hierarchy.** Organize around what the reader needs to understand, decide or do—not a mirror of the input folders.
- **More than text.** Keep figures, cropped evidence, tables, documents and editable LaTeX alongside concise conclusions.
- **Evidence stays attached.** Preserve sources, qualifiers, contradictory findings and unresolved questions.
- **Resume without starting over.** Persist batches, leases, source fingerprints and checkpoints in a local workspace.
- **Spend context deliberately.** Retrieve relevant evidence groups. Reuse acknowledged context only while the host still retains it.
- **Create, never overwrite.** Compile a new delivery directory and validate it before opening it in OdenMap.

```text
Sources → Evidence & context → MapPlan → OdenMap + traceable sources
             AI + local tools             deterministic compiler
```

## Quick start

Requires **Python 3.10 or later**. The core compiler and memory engine use only the standard library. From the downloaded or cloned repository:

```sh
python3 scripts/arc.py capabilities
python3 scripts/arc.py preflight examples/quickstart/plan.json
python3 scripts/arc.py compile examples/quickstart/plan.json \
  --out ./my-first-map --strict-review
python3 scripts/arc.py validate-delivery ./my-first-map
```

Open `my-first-map/map.odenmap` in OdenMap. Keep the surrounding delivery folder: it contains the plan, source copies and verification metadata. Choose a **new** output directory for each run.

The quick-start input is synthetic and needs no network, model or optional dependency. See [Getting started](docs/getting-started.md) for editable installation, media extras and larger jobs.

## Use it with an AI assistant

Give your assistant the complete repository directory and ask it to read [`SKILL.md`](SKILL.md):

> Use Oden ARC to organize these materials around my goal. Read SKILL.md first and load references only as needed. Preserve decisive conditions and source links. For a large task, use a persistent workspace and commit each batch. Deliver a new OdenMap file with its sources and validation results.

For hosts that support Agent Skills, select the **whole `oden-arc/` directory**, not just the Markdown file. Discovery and installation depend on the host. This repository does not install itself into global skill folders.

For smaller inputs, the direct MapPlan path is enough. For long-running tasks, start with [durable memory](references/memory-protocol.md) and [Context Atlas](references/context-atlas.md).

## What is included?

| Included | Supplied by the host or another tool |
| --- | --- |
| A goal-first prompt workflow and review rules | Model inference and multimodal understanding |
| Native file compilation and static validation | OdenMap display, editing and runtime verification |
| Local batch memory, recovery and evidence retrieval | OCR, speech transcription and Office parsing |
| Optional image/PDF crops with provenance | Mermaid rendering and active-content sandboxing |

**ARC is a Skill and CLI toolkit, not a running MCP server.** An MCP wrapper is a possible integration, not an included feature.

## Project boundaries and privacy

This is a **standalone companion to OdenMap**, not the application source code. The public adapter contains the data structures needed to write its supported file profile. It does not include the application's renderer, interactive canvas, proprietary layout engine or optimization code. Its export-position estimates are a separate, generic fallback. See [Architecture](docs/architecture.md) and [Format profile](references/native-format.md).

The Python tools make no outbound network calls or model requests. **Your AI host may send the material you provide to its provider.** Workspaces and backups contain unencrypted source snapshots; keep them outside this repository and do not attach them to public issues. See [Security](SECURITY.md).

Static validation does not establish factual correctness or guarantee native application rendering. Check the generated map in OdenMap before relying on it. This repository does not claim universal model-host compatibility or benchmark-leading quality.

## Explore and contribute

[Documentation](docs/README.md) · [Examples](examples/README.md) · [Contributing](CONTRIBUTING.md) · [Testing](docs/testing.md) · [Changelog](CHANGELOG.md)

```sh
python3 scripts/run_tests.py
python3 scripts/audit_public.py
```

Optional media tests report skips when their dependencies are absent. The public audit is a bounded release check, not a guarantee that arbitrary future contributions are safe to publish.

## License

ARC's original code, prompts, documentation and synthetic examples are under the [MIT License](LICENSE). This license does **not** license the OdenMap application or third-party dependencies.

The optional PDF backend, **PyMuPDF**, has AGPL/commercial licensing terms. Read [Third-party dependencies](THIRD_PARTY.md) before using, redistributing or integrating that backend. The dependency-free core and image-only installation do not require it.

The OdenMap app icon in `assets/brand/` is product branding and is excluded from ARC’s MIT license; see [Brand assets](assets/brand/README.md).
