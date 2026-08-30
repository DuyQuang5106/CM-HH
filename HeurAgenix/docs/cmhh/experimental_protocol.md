# Phase 0 experimental protocol

Phase 0 builds and verifies the experimental machinery; it does not test a
research hypothesis.

## Architecture note

The full CM-HH memory path is:

```text
CandidateExtractor -> Archivist -> MemoryStore -> Retriever
    -> TransferPolicy -> PopulationBuilder -> evolution -> transfer feedback
```

The current managed condition is a runnable prototype. It becomes full CM-HH
only after transfer planning, memory-aware population construction,
validation-only transfer feedback, and child-memory lineage are implemented.

## Data isolation

- `train`: material available to heuristic generation/evolution.
- `validation`: ranks candidates and selects the heuristic retained for a task.
- `test`: computes reported performance matrix entries only.
- `smoke`: quickly rejects invalid or non-terminating generated code.

Files and checksums must be disjoint across splits. Test results must not be
included in prompts, candidate ranking, archive retrieval scores, or search
termination decisions.

The dataset seed is fixed independently of experiment seeds. Changing an
evolution seed must not regenerate instances or invalidate cached references.

## Fair comparisons

Conditions compared in later phases must use the same task instances,
references, model configuration, number of LLM calls, candidate budget,
evaluation timeout, and archive capacity. Random seeds and the complete task
order are recorded for every run.

## Full-experiment budget

The frozen report budget for the current TSP/CVRP/JSSP suite is:

```yaml
search:
  generations: 100
  candidates_per_generation: 5
  max_llm_calls: 500
evaluation:
  instance_timeout_seconds: 30
  batch_timeout_seconds: 900
```

The primary stopping budget is the LLM-call budget. The generation limit is
intentionally high so the run is normally call-budget limited rather than
generation-limited. This replaces the old smoke budget of 2 generations,
3 candidates per generation, and 10 LLM calls. `phase0_tsp.yaml` remains a
development/smoke configuration; report runs should use the `h1_*` condition
configs and `archivist_managed.yaml`.

If 500 calls per task is fast and stable enough, rerun the same conditions with
1000 calls per task as a stronger budget. Do not mix 500-call and 1000-call runs
inside the same headline comparison.

## Metrics

TSP is a minimization problem. Per-instance relative gap is

`(candidate_objective - reference_objective) / abs(reference_objective)`.

Raw gaps are reported as lower-is-better. Continual metrics use the transformed
score `-relative_gap`, for which higher is better. A reference is called
`optimal` only when certified by an exact solver; otherwise it is `best_known`.

## Stream suite

The first full CM-HH experiment suite targets TSP, CVRP, and JSSP:

- `tsp_size_ascending`
- `tsp_size_descending`
- `tsp_random_perm_1`
- `tsp_random_perm_2`
- `cvrp_size_ascending`
- `cvrp_size_descending`
- `jssp_size_ascending`
- `jssp_size_descending`
- `cross_problem_tsp_cvrp_jssp`
- `tsp_revisit`
- `tsp_stationary`
- `related_pair_tsp_cvrp_tsp`
- `unrelated_pair_tsp_jssp_tsp`

`tsp_20_50_100` is retained only as a short/debug stream because it is a
truncated version of `tsp_size_ascending`. Legacy OBP/PFSP streams are also
retained for compatibility, but they are not part of the current main suite.

The canonical stream registry is `docs/experiment_streams.md`.
