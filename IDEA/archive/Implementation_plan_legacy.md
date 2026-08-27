# CM-HH Implementation Plan

This file is the live milestone tracker for CM-HH. It should be updated next to
`Implement_docs.md`, but the two files have different jobs:

- `Implement_docs.md`: chronological implementation log of what changed, what
  was verified, and what remains blocked.
- `Implementation_plan.md`: forward roadmap, phase gates, and milestone status.

## Status Legend

- `[x]`: done and locally verified.
- `[~]`: partially implemented, structurally present, or blocked on an external
  dependency.
- `[ ]`: planned, not implemented.
- `Gate`: a condition that must pass before the next phase can be treated as a
  scientific experiment.

## Phase Overview

| Phase | Theme | Scientific Role | Current Status |
| --- | --- | --- | --- |
| Phase 0 | Experimental foundation | Make data, evaluation, references, budgets, resume, and audit trustworthy before testing hypotheses. | `[~]` Code mostly present; live references/LLM gates remain. |
| Phase 1 | H1/H1b memory baselines | Test whether sequential adaptation and naive memory produce forgetting or retrieval interference. | `[~]` Phase 1A-D implemented; live experiment gates remain. |
| Phase 2 | H2 Archivist memory | Implement protected/distilled insight memory and compare against Phase 1 baselines. | `[ ]` Planned. |
| Phase 3 | H3 curriculum and full study | Run curriculum ablations, cross-problem stream, diagnostics, and paper-ready reporting. | `[ ]` Planned. |

---

## Phase 0 - Reproducible Experimental Foundation

**Goal:** build a trustworthy substrate before any H1 claim is made.

### Milestones

- [x] Task registry for TSP/OBP/PFSP scaffolding.
- [x] TSP size stream: `TSP-20 -> TSP-50 -> TSP-100 -> TSP-200`.
- [x] Deterministic data generation with manifests and checksums.
- [x] TSPLIB-compatible TSP reader/fallback.
- [~] Exact/best-known reference pipeline.
- [x] Subprocess evaluator for generated heuristic code.
- [x] Smoke baseline evaluation.
- [~] HeurAgenix generator adapter with hard LLM-call budget.
- [~] Resumable stream runner.
- [x] Continual metrics: average performance, BWT, FWT plumbing.
- [~] Reproducibility manifest and audit path.

### Gates

- [ ] Concorde pilot references pass verification for all TSP sizes.
- [ ] Full frozen test references exist and verify.
- [ ] Validation/reference policy is frozen and documented.
- [ ] One real low-budget `evolve-task` run succeeds with a live LLM provider.
- [ ] One interrupted stream run resumes without regenerating completed tasks.
- [ ] `audit-run` passes on a complete pilot run.

### Deliverables

- Frozen Phase 0 TSP data and reference artifacts.
- One complete baseline performance matrix.
- Verified runner/evaluator/audit logs.
- Finalized experiment budget values for Phase 1.

---

## Phase 1 - H1 and H1b Baselines

**Goal:** test the lowest levels of continual behavior before introducing the
full Archivist.

Phase 1 separates three ideas that are easy to accidentally mix:

1. isolated cold-start search has no stream and no forgetting;
2. population-carryover sequential search has no explicit memory, but transfers
   the final population from task `k` to task `k+1`;
3. naive external memory keeps the same population carryover as (2), then adds
   an uncurated memory pool. This isolates retrieval-side interference beyond
   population drift.

### Phase 1A - Population-Carryover Sequential

- [x] Add a `population_carryover` condition/config.
- [x] Persist the final selected candidate population after each task.
- [x] Seed the next task's generator from the previous final population.
- [x] Disable external memory retrieval, Archivist distillation, protection,
  and eviction.
- [x] Re-evaluate after every task on all previously seen test tasks.
- [x] Emit a performance matrix compatible with existing BWT/FWT metrics.

**H1 gate:** compare isolated cold-start against population-carryover
sequential. H1 is only about forgetting from sequential adaptation/population
drift, not about memory retrieval.

### Phase 1B - Explicit Memory Object Model

- [x] Add a first-class `MemoryUnit` model:
  - `scope`: problem/task/heuristic family/generation;
  - `key`: task signature, state signature, bottleneck type, applicability;
  - `value`: insight, rule, warning, code adjustment, or trajectory;
  - `evidence`: artifact paths, validation scores, code hashes;
  - `policy`: confidence, retrieval count, success/failure count, protected.
- [x] Persist memory as JSONL or manifest-backed records under the run output.
- [x] Add deterministic memory IDs.
- [x] Add validation-only evidence updates.
- [x] Block test results from memory writing, retrieval scoring, selection, and
  stopping decisions.

### Phase 1C - Naive External-Memory Sequential

- [x] Preserve all `population_carryover` behavior: task `k+1` must still be
  seeded from task `k`'s final ranked population.
- [x] Add a `naive_memory_sequential` condition/config.
- [x] Implement `naive_overwrite` over `MemoryUnit` records.
- [x] Start with weak/no distillation to model an uncurated archive.
- [x] Retrieve top-m memory units at the start of each task-generation episode.
- [x] Insert retrieved memory into the generator prompt/seed protocol in a
  deterministic, logged format.
- [x] Log retrieval ranks, source task, retrieval score, duplicate-key rate, and
  whether each retrieved unit was actually used.

**H1b gate:** compare population-carryover against naive-memory sequential.
H1b is about retrieval-side interference beyond population drift. Therefore
`naive_memory_sequential` must differ from `population_carryover` only by
enabling the naive external memory pool and retrieval path.

### Phase 1D - Diagnostics

- [x] Add retrieval coverage.
- [x] Add top-k concentration.
- [x] Add duplicate-key or near-duplicate key rate.
- [x] Add source-task and memory-age distribution.
- [x] Add post-reuse validation delta.
- [x] Label failure modes:
  - harmful reuse;
  - ineffective reuse;
  - retrieval pollution;
  - context competition;
  - memory dilution;
  - retrieval diversity collapse.

### Phase 1 Gates

- [ ] H1 and H1b conditions run on the TSP size stream for one seed.
- [ ] H1/H1b pilot reruns for at least three seeds after audit passes.
- [ ] Results include mean and variance for average performance, BWT, and FWT.
- [ ] Retrieval diagnostics are computed without test leakage.
- [x] Phase 1 run guide documents command order and artifacts.
- [ ] Decision recorded: whether H1/H1b show enough signal to justify H2.

---

## Phase 2 - H2 Archivist and Protected Insight Memory

**Goal:** implement the proposed memory mechanism and compare it against Phase 1
baselines.

### Phase 2A - Archivist Distillation

- [ ] Implement `Archivist.write_from_run()`.
- [ ] Distill candidate traces, bottlenecks, validation outcomes, rejected
  candidates, selected candidates, and refinement suggestions into memory units.
- [ ] Prefer abstract insight/rule/warning/code-adjustment memory values.
- [ ] Keep raw trajectories and full code as evidence links, not default prompt
  content.
- [ ] Generate retrieval keys from applicability conditions, not only source
  task IDs.

### Phase 2B - Protected Memory Policies

- [ ] Implement `fixed_quota_replay`.
- [ ] Implement `utility_weighted_retention`.
- [ ] Add protected units per completed task.
- [ ] Add deterministic eviction tie-breakers.
- [ ] Update confidence using validation deltas after reuse.
- [ ] Add memory compaction for duplicate or near-identical units.

### Phase 2C - Retrieval Protocol

- [ ] Build task/generation query objects from task features, seed population,
  problem family, known bottlenecks, and current generation context.
- [ ] Implement transparent retrieval scoring.
- [ ] Add top-k retrieval configuration.
- [ ] Add prompt insertion templates for retrieved memory.
- [ ] Log prompt hashes and memory IDs used.

### Phase 2D - H2 Evaluation

- [ ] Run isolated, population-carryover, naive-memory, fixed-quota, and
  utility-retention conditions on the TSP size stream.
- [ ] Compare BWT/FWT and final average performance.
- [ ] Report whether protected insight memory reduces forgetting relative to
  naive memory without materially hurting new-task performance.
- [ ] Include retrieval diagnostics explaining why memory helped or harmed.

### Phase 2 Gates

- [ ] All memory policies share the same data, task order, LLM budget, candidate
  budget, timeout, validation split, test split, and archive capacity.
- [ ] Audit verifies test artifacts are not present in generation or memory
  prompts.
- [ ] At least three seeds complete for the TSP size stream.
- [ ] H2 result is recorded as positive, negative, or inconclusive before
  moving to broad curriculum ablations.

---

## Phase 3 - H3 Curriculum, Cross-Problem Stream, and Paper Study

**Goal:** move from the TSP-size pilot to the full research study.

### Phase 3A - Curriculum Conditions

- [ ] Implement fixed size-ascending order.
- [ ] Implement random order with recorded seed.
- [ ] Implement empirically measured similarity order.
- [ ] Keep memory policy fixed while varying order for H3.
- [ ] Record complete task order in every manifest.

### Phase 3B - Cross-Problem Stream

- [ ] Finalize CVRP adapter.
- [ ] Finalize OBP/BPP adapter.
- [ ] Finalize PFSP adapter.
- [ ] Add problem-specific data generation and references/best-known records.
- [ ] Add smoke, validation, and test splits for each problem.
- [ ] Verify evaluator compatibility across objective directions and scales.

### Phase 3C - Full Ablation Grid

- [ ] Run memory-policy x curriculum grid on the TSP size stream.
- [ ] Run selected grid on the cross-problem stream.
- [ ] Use at least three seeds per reported condition.
- [ ] Stop expanding conditions if Phase 1/2 gates show no reliable signal.

### Phase 3D - Reporting and Figures

- [ ] Forgetting curves for early tasks.
- [ ] Policy x curriculum BWT heatmap.
- [ ] Forward transfer bar chart against cold-start.
- [ ] Per-task optimality gap table.
- [ ] Memory retrieval diagnostics table.
- [ ] Case studies of helpful and harmful retrieved memories.
- [ ] Audit appendix with data/config/code hashes.

### Phase 3 Gates

- [ ] All reported results are computed from frozen test references.
- [ ] All candidate selection uses validation only.
- [ ] Variance is reported across seeds.
- [ ] Negative or inconclusive H1/H2/H3 outcomes are reported honestly.
- [ ] Paper claim wording matches the actual measured signal.

---

## Immediate Next Actions

1. Finish Phase 0 gates:
   - generate and verify full TSP references;
   - run one real low-budget LLM evolution;
   - complete one audited stream pilot.
2. Run the Phase 1 smoke commands in `docs/cmhh/phase1_experiment_guide.md`.
3. Run H1/H1b for seed 1 with a live HeurAgenix generator.
4. Audit the seed-1 population-carryover and naive-memory runs.
3. Add the explicit `MemoryUnit` schema before implementing any more archive
   behavior.
4. Run the H1 pilot before building protected memory.
5. Only start H2/H3 after H1/H1b are measured cleanly.
