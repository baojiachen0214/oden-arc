# OdenMap output profile

This document describes ARC's supported interoperability surface. It contains no application implementation or private source references. The profile identifier is `odenmap-directory-13-15/topic-content-1`; it is not an OdenMap application version or a claim to support every native document.

## Directory package

```text
map.odenmap/
  manifest.json
  map.json
  Assets/<resource-id>
```

Manifest schema is 1 without aliases and 2 with aliases. Aliases point directly to real payloads in this package; they cannot loop, point to another alias or escape the directory. Resource paths are `Assets/<id>`, not original filenames.

The emitted map schema is 13, or 15 when canvas links are present. These are the adapter's output levels, not the application's maximum version. TopicContent version 1 contains blocks, inlines and marks; block/inline identities are deterministic, and equations retain LaTeX for editing.

Tree relations use `relationships` with hierarchy kind. Cross-branch relations use `canvasLinks`, with separate floating label nodes and `canvasAttachments` describing label attachment. Label nodes do not count as semantic roots.

## Rendering is separate

ARC does not run the native renderer or fabricate a QuickLook preview. Finder previews, font measurement, exact layout and interactive behavior require the application. `export_layout.py` implements a small independent estimate of initial node sizes and positions. It is neither the product's layout engine nor a promise of equivalent geometry.

## Deterministic and portable delivery

Logical document/object IDs generate stable UUIDv5 identifiers. Identical plans and resources produce deterministic map structures. Compilation rechecks payload digests, copies original sources where available and writes a full plan and manifest beside the native package. It does not rely on the application preserving arbitrary unknown fields.

Relative source text in a note is a traceability cue, not a guarantee of clickable navigation in every host. Do not invent an undocumented deep-link scheme.

## Limits

Only new directories are created. Existing maps, unknown fields and manually arranged layouts are not merged or overwritten. Ordinary errors clean up the output owned by the current transaction; a forced termination can leave an `.incomplete` marker, which validation rejects. No guarantee of hostile-filesystem isolation or cross-platform crash-atomic publication is made.

Resource type/signature/size checks are not malware scanning. Active HTML/SVG and directory-style iWork serialization are outside this profile. Attaching bytes does not mean their contents were interpreted.

## Native acceptance

Open a synthetic output in OdenMap; inspect root, links, resources, visible qualifiers and formulas; edit text and an equation; save a new copy; close and reopen; inspect again. Record the actual public application version/platform and observed results. Static checks do not replace this process.
