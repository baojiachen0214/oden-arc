# Testing and evaluation

Run from a source checkout:

```sh
python3 scripts/run_tests.py
python3 scripts/audit_public.py
```

Install `.[test]` for JSON Schema checks. Image tests need `.[images]`; PDF tests need `.[pdf]` and its separate licensing review. Missing extras are reported as skipped tests, not counted as successful media verification.

The suite covers plan validation, native encoding, resource integrity, crop provenance, durable batches, transaction failure, stale evidence, context acknowledgement and release packaging. It uses synthetic sources; it does not call a model or run OdenMap.

## Save an actual run

```sh
python3 scripts/run_tests.py --out ../arc-test-results
python3 scripts/build_examples.py --out ../arc-example-output --with-atlas
```

Choose new directories. Generated logs, local paths and built packages are intentionally outside the public source tree. The latest run's JSON records test counts, dependency versions and skipped cases. Do not turn historic test counts into a live README badge.

## Reproducible experiments

```sh
python3 scripts/demo_memory.py --help
python3 scripts/demo_atlas.py --out ../arc-atlas-demo
python3 scripts/benchmark_atlas.py --out ../arc-benchmark.json
```

Synthetic aliases and links have annotation costs that these experiments do not measure. Report first-request and repeat-request payloads separately. Payload bytes are not API billing tokens. A successful lookup is not proof that a model answered correctly.

## Required non-automated checks

Inspect the actual reading experience, evidence coverage and high-risk numbers/formulas. Separately open the output in OdenMap, inspect resource previews and link labels, edit a formula, save a new copy and reopen it. Only record checks actually performed. Use [the evaluation rubric](../references/evaluation.md).

## CI scope

The provided GitHub Actions workflow is a configuration, not evidence that GitHub has run it. It uses read-only repository permissions and pinned action revisions. Local acceptance cannot replace macOS application testing or review of incoming contributions.
