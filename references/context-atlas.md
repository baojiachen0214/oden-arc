# Context Atlas

Use after a durable workspace contains evidence cards and cross-source synthesis is needed. Small tasks can skip this layer to avoid annotation overhead.

## 1. Separate facts, indices and model context

Original snapshots and committed cards are durable state. Rooms, aliases, classes and relations are retrieval annotations. `session/epoch` records the host's assertion that a particular model window still holds content. A card existing on disk does not mean the model received it; tools cannot detect host-side compaction automatically.

Classes: `concept` for relatively stable definitions/mechanisms; `event` for time-anchored changes; `record` for precise facts, quotes, values or formulas. The default is record, so classification is not mandatory. The agent supplies annotations; the engine does not infer truth, entity identity or authority. `time_anchor` is a string, not automatic timezone reasoning.

## 2. Add only useful annotations

```json
{"chunk_id":"actual-card-id","card_hash":"actual-sha256","facets":{"memory_class":"record","aliases":["cold-start latency","冷启动耗时"],"entities":["Falcon v2"],"scope":"Process-level timing; network excluded"}}
```

Run `annotate annotation.json`. The card hash must match. Updating an annotation requires the previous `expected_hash` for compare-and-swap; identical content can be replayed idempotently. Do not merely refresh a hash after changed evidence without reviewing it.

Keep aliases verified and minimal. Put version, denominator and measurement environment in scope. A shared name does not prove two entities can be merged.

## 3. Explicit relations

Kinds: `contradicts`, `qualifies`, `requires`, `supersedes`, `supports`, `related`.

```json
{"source":"claim-card","source_hash":"actual-sha256","target":"limitation-card","target_hash":"actual-sha256","kind":"qualifies","reason":"The measurement covers warm starts only"}
```

Both endpoints of `link relation.json` must be current reviewed cards. The first four kinds are critical: retrieval traverses an undirected connected closure, preserving the original direction for interpretation. Support and related links do not force expansion.

Directions: qualifies = claim → qualifier; requires = dependent → prerequisite; supersedes = authorized new version → old version; supports = supporting evidence → supported claim. Contradicts and related are symmetric. A later date alone does not justify supersession.

A critical group is indivisible: return it complete or report `blocked_groups`. Stale or retired endpoints block apparent completeness. Review the relationship and explicitly `retire-link ID --reason ...` only when it is wrong; never remove an inconvenient counterexample just to pass retrieval.

Closures are bounded to 100 cards and 1,000 incident links per endpoint. Limits are explicit failures, not silent truncation. Broad thematic similarity usually belongs under `related`, not a critical link joining the whole corpus.

## 4. Retrieve a focused packet

```json
{"queries":["Falcon v2 cold start","memory measurement scope"],"budget_bytes":16000,"max_cards":16,"mode":"full"}
```

```sh
python "$S/scripts/arc_memory.py" --workspace "$W" context request.json > packet.json
```

At most eight queries; `must_include` pins cards. A room restricts seed search but does not remove cross-room critical evidence. Requests without a query or pin are rejected.

Search uses words/CJK bigrams, explicit aliases, multi-query rank fusion and source diversity. It is not an embedding service or BM25 implementation and cannot guarantee paraphrase recall. Bounded candidate truncation is exposed through `retrieval_truncated`.

A packet includes cards, provenance, critical relations, uncovered queries, blocked groups and global reading progress. `ready_for_review` is not task completion or factual correctness. Budgeting uses compact UTF-8 JSON including a newline; it is not tokenizer or billing measurement.

## 5. Reuse only acknowledged context

`full` always returns selected card bodies. Delta requires `session-new --id window-1` and a request containing `mode: delta`, `session: window-1`, `epoch: 1`. The initial request and all unacknowledged repetitions still return full content.

Only after the host confirms the response reached the same still-retained model context:

```sh
python "$S/scripts/arc_memory.py" --workspace "$W" ack PACKET_ID --session window-1 --epoch 1
```

Subsequent unchanged cards can become `held_references`. Changes to cards, facets, provenance or critical relations resend content. A changed evidence snapshot rejects the ACK and requires a fresh packet.

Compaction, pruning, model/worker changes, an uncertain restart or backup restoration require `session-reset window-1` and the returned new epoch. A new session plus full packets is the safest resume path. Never share one session between two model workers.

Writing a packet to disk is not ACK. Tools cannot prove a host's retention assertion; a false ACK can omit required context. Reception confirmation and content review are separate concepts.

## 6. Bind maps to live evidence

In large tasks, `extensions.memory_bindings` names the workspace, goal revision and evidence backing fact/inference nodes. Several cards may support one synthesized node; one card does not imply one map node.

```json
{"version":"1.0","workspace_id":"actual-workspace-id","goal_rev":1,"nodes":{"conclusion":[{"chunk_id":"actual-card-id","card_hash":"actual-sha256","plan_source_id":"source-1","placement":"label"}]}}
```

Placement is label/body/note/resource. Source refs and hashes must match current evidence. Bind the complete critical closure. When a claim is visible, known contradictory, qualifying or prerequisite evidence must be declared in visible labels/body rather than notes, attachments or collapsed descendants. Superseded evidence remains traceable without requiring the old claim on the same visible layer.

Pass `--memory-workspace "$W"` to compilation. A transactional snapshot checks bindings and writes `evidence-audit.json`; the lock lasts through compilation, temporarily blocking concurrent writers. Finish extraction before compiling large resources and avoid simultaneous recompilation workers.

The gate validates identity, revision, references, closure and **declared** position. It cannot prove that a sentence actually expresses its qualifier. A reader must still check meaning. Historic exports remain valid files even after evidence changes; a new current map must pass the live gate again.

## 7. Copy-based upgrade

```sh
python "$S/scripts/arc_memory.py" --workspace OLD_WORKSPACE enable-atlas --out NEW_WORKSPACE
```

This backs up a consistent copy, adds Atlas tables and leaves the old workspace untouched. Legacy visual caches may require rereading; re-ingest active sources after upgrade. Cached originals and parsing can be reused, but corrected identity rules may incur one-time semantic review cost. Old ACK state must not be treated as retained model context.

## 8. Incremental edge cases

Appending externally extracted units no longer changes every unit solely because the complete extraction digest changed. New and adjacent boundary units are reconsidered; an extractor-version change still invalidates results.

If bytes change in a source with visual units, even identical extracted text requires renewed visual review. This is conservative source-level invalidation, not page-pixel optimal caching. Checkpoints depend on evidence hashes, not only chunk IDs.

## 9. Bounded scope

Source quotas exclude additional SQLite/index/log overhead. Packet records are limited to 10,000; reaching the limit fails explicitly rather than silently deleting history. No automatic garbage collector, distributed sync, background model recursion or vector service is included.

Annotations and relationships require host work and review. Synthetic retrieval measurements exclude that cost. Unrecognized contradictions do not magically enter the graph; they must be discovered through actual coverage and cross-source review.
