# CM-HH experiment stream registry

This file separates main experiment streams from short/debug streams. A stream
is only an ordering of task IDs; it does not change solver budgets, LLM budget,
memory capacity, or seed settings.

The current full-experiment search budget is 100 generations, 5 candidates per
generation, and 500 LLM calls per task. The generation limit is intentionally
high; `max_llm_calls` is the primary stopping budget. All compared memory
conditions should use this same budget unless the experiment is explicitly
labelled as a budget ablation.

## Main streams

Use these streams for the first full CM-HH experimental report.

| Stream | Order | Purpose |
| --- | --- | --- |
| `tsp_size_ascending` | TSP20 -> TSP50 -> TSP100 -> TSP200 | Primary within-problem scale-up test. |
| `tsp_size_descending` | TSP200 -> TSP100 -> TSP50 -> TSP20 | Reverse-curriculum control for scale direction. |
| `tsp_random_perm_1` | TSP50 -> TSP200 -> TSP20 -> TSP100 | TSP order-sensitivity control. |
| `tsp_random_perm_2` | TSP100 -> TSP20 -> TSP200 -> TSP50 | Second TSP order-sensitivity control. |
| `cvrp_size_ascending` | CVRP20 -> CVRP50 -> CVRP100 | CVRP within-problem scale-up test. |
| `cvrp_size_descending` | CVRP100 -> CVRP50 -> CVRP20 | CVRP reverse-curriculum control. |
| `jssp_size_ascending` | JSSP10x5 -> JSSP20x5 -> JSSP50x10 | JSSP within-problem scale-up test. |
| `jssp_size_descending` | JSSP50x10 -> JSSP20x5 -> JSSP10x5 | JSSP reverse-curriculum control. |
| `cross_problem_tsp_cvrp_jssp` | TSP50 -> CVRP50 -> JSSP20x5 -> TSP50 | Cross-problem transfer and revisit probe. |
| `tsp_revisit` | TSP20 -> TSP50 -> TSP100 -> TSP20 | Same-task revisit probe for retention/reuse. |
| `tsp_stationary` | TSP50-A -> TSP50-B -> TSP50-C -> TSP50-D | Stationary same-problem same-size control. |
| `related_pair_tsp_cvrp_tsp` | TSP20 -> CVRP50 -> TSP100 | Related routing-transfer pair. |
| `unrelated_pair_tsp_jssp_tsp` | TSP20 -> JSSP20x5 -> TSP100 | Less-related transfer pair. |

## Debug streams

These are useful for smoke tests, development, or shortened checks, but they
should not be reported as main evidence unless explicitly labelled as a pilot.

| Stream | Order | Notes |
| --- | --- | --- |
| `tsp_20_50_100` | TSP20 -> TSP50 -> TSP100 | Short form of `tsp_size_ascending`; excluded from main experiments. |
| `random_perm_1` | TSP50 -> TSP200 -> TSP20 -> TSP100 | Legacy alias; prefer `tsp_random_perm_1`. |
| `random_perm_2` | TSP100 -> TSP20 -> TSP200 -> TSP50 | Legacy alias; prefer `tsp_random_perm_2`. |

Legacy PFSP/OBP streams remain in the repo but are not part of the current
TSP/CVRP/JSSP experiment suite.

## Reference semantics

- TSP gaps are against Concorde proven-optimal references when available.
- CVRP gaps are against PyVRP best-known references unless optimality is proven
  by the backend.
- JSSP gaps are against OR-Tools CP-SAT references: `optimal` if CP-SAT proves
  optimality, otherwise `best_known`.

When reporting cross-problem results, keep per-problem reference status visible
instead of mixing all gaps under the word "optimal".
