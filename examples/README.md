# Examples

All included material is synthetic. These examples illustrate contracts and failure boundaries; they are not customer data or model-quality benchmarks. Some advanced fixtures retain Chinese text to exercise multilingual behavior.

| Directory | Demonstrates |
| --- | --- |
| `quickstart/` | English, dependency-free formula, assumptions, resource table and cross-link |
| `math/` | Rich text, formulas, original figures, CSV and Markdown resources |
| `decision/` | Different denominators, measurement scope and acceptance limits |
| `action/` | Timezones, dependencies, estimates and unknown durations |
| `crop/` | A real synthetic-image crop with a newly generated relative-path receipt |
| `durable-memory/` | Local batching and restart demonstration |
| `context-atlas/` | Known critical relations, context ACK/reset and live evidence bindings |

Generate new outputs outside the checkout:

```sh
python3 scripts/build_examples.py --out ../arc-examples --with-atlas
```

Built native packages and local logs are intentionally not committed. Read each generated delivery's actual validation status and perform native application checks separately.
