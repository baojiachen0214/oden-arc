# Plan a bounded context request
State the current subquestion and why answering it matters to the user's goal. Read room/card metadata first. Select a small number of query facets: entity/version, metric, condition, time and possible counterexample. Use verified aliases only where necessary.

Request full evidence groups within a byte budget that leaves room for the host's other context and output. Use must_include for actual known cards, not invented IDs. Inspect uncovered queries, truncated retrieval and blocked groups. Never drop a known qualifier to fit a budget.

After two rounds with no new evidence or actionable step, stop blind retries. Inspect missing coverage, aliases or an exact source segment with a reason. Delegate only a bounded subproblem with relevant evidence; do not broadcast the corpus to every worker. The host executes this policy; no autonomous recursion is implied.
