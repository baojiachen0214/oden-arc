# Design references and trade-offs

These notes are for maintainers, not input for every agent batch. They explain design choices; they do not claim to reproduce a paper's implementation or results. Public source pages were checked on 2026-10-22.

| Primary source | Relevant idea | ARC's bounded implementation |
| --- | --- | --- |
| [Agent Skills specification](https://agentskills.io/specification) | Progressive loading of instructions and resources | A short SKILL.md and focused references/prompts; no claim every host has been tested |
| [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), Anthropic | Curated context and just-in-time retrieval | Small task capsules, targeted evidence and host-controlled context acknowledgements |
| [A-MEM](https://arxiv.org/abs/2502.12110), Xu et al. | Attributed notes and connected memory | Explicit hash-bound annotations and relations; no model-driven automatic link generation |
| [SimpleMem](https://arxiv.org/abs/2601.02553), Liu et al. | Structured memory and intent-aware retrieval planning | Multi-question lexical/alias retrieval and source diversity; no dense embeddings or claimed lossless semantic compression |
| [Recursive Language Models](https://arxiv.org/abs/2512.24601), Zhang et al. | Inspect and decompose long inputs in an external environment | Durable source storage and bounded subtask prompts; no recursive model scheduler or autonomous REPL |
| [LongMemEval](https://arxiv.org/abs/2410.10813), Wu et al. | Evaluate extraction, cross-session reasoning, time, updates and abstention separately | Synthetic tests of stale evidence, resets, supersession and missing evidence; its dataset/model QA benchmark has not been run |
| [SQLite Online Backup API](https://www.sqlite.org/backup.html) | Consistent live database snapshots | Copy-based backups/migration; not cloud failover, multi-device sync or automatic corruption recovery |

## Project-specific decisions

Evidence completeness is not identical to nearest-match retrieval. Once a qualifier, contradiction or prerequisite is known, ARC retrieves the connected critical group or reports that it does not fit. This is a design invariant, not a performance theorem established by the cited papers.

Durable storage and a model's current context are different. Only an explicit acknowledgement for the same session and epoch permits a pointer to replace previously delivered text. The tools cannot observe a model's internal retention or validate a false host acknowledgement.

The compiler's evidence gate checks identity, revision, references, graph closure and declared placement. It cannot prove a natural-language sentence faithfully expresses the evidence. A final reader review remains necessary.

## What not to infer

Synthetic aliases and relationships cost work to create; retrieval-only experiments exclude that cost. First complete evidence packets can be larger than baseline matches. Compare first and repeated payloads, expose missed paraphrases, and do not translate byte reduction into billed-token reduction without measurement.

A more elaborate graph, extra agents or a vector store is not automatically a better trade-off. Small tasks retain a direct path. Further work should establish independent task data, actual model quality and cost before adding dependencies.
