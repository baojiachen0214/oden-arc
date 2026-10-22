# MapPlan 1.0

MapPlan is ARC's intermediate format, not the native OdenMap format. The agent chooses content; the compiler encodes it deterministically.

Start with `assets/templates/minimal-plan.json` or `examples/quickstart/plan.json`. The full structure is in `schemas/map-plan.schema.json`. Python validation also checks the tree, paths, references, digests and actual files; JSON Schema alone is insufficient.

## Root

`plan_version: "1.0"`, stable `document_id`, `title`, `goal`, `sources`, `assets`, `nodes`; optional `cross_links`, `settings`, `audit`, `extensions`.

`goal.purpose` is `learn`, `decide`, `act`, `reference` or `explain`. `question` is the central question. `must_answer` lists concrete required questions, not the entire conversation history.

## Sources

```json
{"id":"s1","title":"Lesson","kind":"text","status":"read","coverage":"Sections 1–3","uri":"materials/lesson.md","sha256":"actual-lowercase-sha256"}
```

Status is `read`, `partial`, `unread` or `unavailable`. A local `uri` must be an actual path inside the plan directory. Explicit HTTP(S) references are allowed but are never downloaded by the compiler. When the original is unavailable, omit the path and describe the gap. Coverage, identifiers and page numbers must not be invented.

## Nodes

```json
{"id":"mechanism","parent_id":"root","label":"The parameter controls response speed","role":"mechanism","support":"fact","source_refs":[{"source_id":"s1","locator":"Section 2"}],"body":[{"kind":"equation","latex":"y_t=\\alpha x_t+(1-\\alpha)y_{t-1}"}],"note":"Define the variables and assumptions here."}
```

Exactly one semantic root has `parent_id: null`. Support is `fact`, `inference`, `uncertain`, `user` or `structure`. Keep decisive caveats visible rather than only in `note`.

`body` supports `paragraph`, `heading`, `list`, `task`, `code` and `equation`. Text blocks use either `text` or `inlines`, not both. Inline items support text with marks, editable equations and soft breaks. Marks include `bold`, `italic`, `underline`, `strike`, `code`, `link` and `relativeSize`. Do not pass native TopicContent objects as MapPlan body items.

`asset_id` makes a resource node and cannot coexist with `body`. Use a neighboring text node or `attachment_ids` for text-plus-resource composition. Other fields include `hyperlink`, `collapsed` and `extensions`.

## Assets

```json
{"id":"a1","path":"assets/figure.png","name":"figure.png","kind":"image","alt":"Trend, labeled axes and units","source_refs":[{"source_id":"s1","locator":"Page 4, figure 2"}],"derivation":{"kind":"crop","note":"Axes and legend retained"},"sha256":"actual-lowercase-sha256"}
```

Kinds: `image`, `pdf`, `text`, `audio`, `video`, `file`. Derivations: `original`, `crop`, `redraw`, `generated`, `render`, `transcribe`, `extract`, `calculation`.

Identical payloads can share physical storage without merging source identities. Every asset must be used by a node or attachment. Symlinks, absolute paths, path traversal and pretend remote assets are rejected.

## Cross-links

`cross_links: [{"id":"r1","from":"a","to":"b","label":"limited by"}]` produces a native canvas link and an attached label node, not a disguised tree edge.

## Review record

`audit.review_version` is `"1.0"`.

- `questions`: question, status, node_ids. Status is answered/partial/unanswered/out-of-scope and must match the required questions.
- `coverage`: source_id, read_scope, unread_scope, method. Distinguish extraction from actual reading, listening and visual review.
- `decisions`: action (retain/merge/omit/downshift/split/reframe), content, reason and affected node/source IDs.
- `issues`: id, scope, severity, status, description and node_ids. A subject-level problem need not block a faithful map; unresolved substantive map/delivery problems block strict compilation.
- `checks`: semantic, reader, numbers_formulas, resources, native_runtime, each with status/reviewer/evidence. Record not_run when appropriate.
- `transformations`: asset_id and the actual transformation record, not invented crop coordinates.

`--strict-review` checks consistency and explicit blockers. It does not prove that the author actually performed a declared semantic check.

## Live evidence bindings

Large tasks should use `extensions.memory_bindings`; see `references/context-atlas.md` and `schemas/memory-bindings.schema.json`. Bound plans require `--memory-workspace` during preflight and compilation. Never remove a binding merely to bypass outdated-evidence rejection. This extension does not change the native file format.

`check-plan` validates input; `review-plan` examines review records; `preflight` performs a temporary strict compilation; `compile` creates a new delivery; `validate-delivery` verifies its files, plan and native package. Native validation accepts ARC's supported profile, not arbitrary future application documents.
