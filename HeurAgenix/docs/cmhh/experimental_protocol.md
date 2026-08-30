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

## Metrics

TSP is a minimization problem. Per-instance relative gap is

`(candidate_objective - reference_objective) / abs(reference_objective)`.

Raw gaps are reported as lower-is-better. Continual metrics use the transformed
score `-relative_gap`, for which higher is better. A reference is called
`optimal` only when certified by an exact solver; otherwise it is `best_known`.

## Phase 0 stream

The initial integration stream is TSP n20, n50, n100, and n200 in ascending
order. OBP and PFSP are intentionally deferred until the common infrastructure
and TSP pilot are reliable.
