# CM-HH Implementation Plan

This file is the **live execution roadmap and milestone tracker** for CM-HH.

It should be maintained next to:

- `../source_of_truth/CMHH_Research_Specification.md` — research questions, hypotheses, metric semantics, experimental meaning, statistical claims;
- `../source_of_truth/CMHH_Archivist_Retriever_Design_Specification.md` — research-level memory and retrieval architecture;
- `../source_of_truth/CMHH_Implementation_Ready_Specification.md` — software contracts, invariants, tests, research-integrity requirements, and acceptance gates;
- `../logs/Implementation_Log.md` — chronological implementation log of what changed, what was verified, and what remains blocked.

The documents have different jobs:

```text
Research Specification
        ↓
defines what the experiment must mean

Archivist / Retriever Design Specification
        ↓
defines the research architecture

Implementation-Ready Specification
        ↓
defines what the implementation must guarantee

Implementation Plan
        ↓
defines the order in which those guarantees are built and verified

Implementation_Log.md
        ↓
records what actually happened
```

The Implementation Plan MUST NOT silently redefine research semantics. If this plan conflicts with the Research Specification or Implementation-Ready Specification, the higher-level specification wins.

---

## Status Legend

- `[x]`: done and locally verified.
- `[~]`: partially implemented, structurally present, or blocked on an external dependency.
- `[ ]`: planned, not implemented.
- **Gate**: a release condition that must pass before the corresponding research capability is considered trustworthy.
- **Pilot**: engineering / preliminary experiment; not paper-grade evidence.
- **Paper-grade**: allowed only after the Final Experiment Readiness Gate passes.

---

# Global Experimental Contracts

These contracts apply to every phase once the relevant infrastructure exists.

## G1. Canonical Continual Lifecycle

Every continual condition MUST obey the same high-level lifecycle for task `T_k`:

```text
state M_{k-1}
    |
    v
[A] PRE-LEARNING PROBE
    - retrieve/select retained competence
    - execute directly applicable retained artifact(s)
    - record Z_k when executable compatibility exists
    - no evolutionary search
    - no heuristic generation
    - no memory write/update
    |
    v
[B] LEARN / SEARCH T_k
    - normal heuristic search
    - generator + evaluator
    - train/validation evidence only
    - working state may update
    - memory may update only in memory-enabled conditions
    - record search trajectory S_k(b)
    |
    v
state M_k
    |
    v
[C] RETENTION PROBE
    - evaluate all previously seen tasks T_1 ... T_k
    - use current retained competence
    - no full evolutionary re-search
    - no memory write/update
    |
    v
checkpoint + logs + metrics + audit state
```

Stage A is not satisfied by logging a retrieval event alone.

When `T_k` is executable under retained heuristic interfaces, the pre-learning probe MUST actually:

```text
retrieve/select
    ↓
execute retained artifact
    ↓
record pre-learning performance Z_k
```

For incompatible interfaces, zero-shot direct execution is recorded as `N/A`; transfer is then evaluated through matched adaptation efficiency rather than an artificial zero-shot score.

---

## G2. Probe Read-Only Invariant

Pre-learning and retention probes MUST be behaviorally read-only.

At minimum, integration tests MUST verify:

```text
behavioral_state_hash_before
run probe
behavioral_state_hash_after

assert before == after
```

Probe execution MUST NOT alter:

- long-term memory;
- memory utility;
- retrieval statistics used by the learner;
- population/search state;
- prompts or hyperparameters for future learning;
- curriculum decisions;
- any other learner-visible state.

This is a release-blocking invariant.

---

## G3. Test Isolation

Test results exist only for final measurement and frozen diagnostics.

Test evidence MUST NOT affect:

- heuristic generation;
- candidate selection;
- memory admission;
- memory utility;
- retrieval tuning;
- capacity selection;
- `top_k` selection;
- prompts;
- stopping decisions;
- curriculum selection.

Train and validation evidence may affect learning according to the frozen protocol.

---

## G4. Comparable Experimental Conditions

Primary comparisons MUST use matched:

- dataset manifests;
- task ordering;
- random seeds where applicable;
- generator configuration;
- evaluator configuration;
- candidate-evaluation budget;
- LLM-call/token budget;
- timeouts/resource limits;
- validation/test splits;
- reference sets.

For RQ2 matched naive-vs-managed comparisons, also match:

- memory capacity `C`;
- retrieval budget / `top_k`, unless explicitly ablated;
- heuristic interface;
- downstream context budget where relevant.

---

# Global Definition of Done

A result is **not paper-grade** merely because an experiment finished.

Every final reported score MUST be traceable through an audit chain equivalent to:

```text
reported aggregate metric
        ↓
per-run metric
        ↓
evaluation record
        ↓
task + evaluation instances
        ↓
executed heuristic artifact
        ↓
retained-state / memory snapshot
        ↓
retrieval event(s), when applicable
        ↓
experiment config
        ↓
seed + budgets
        ↓
dataset/reference hashes
        ↓
code version / git commit
```

A paper-grade run MUST satisfy all of the following:

- frozen config;
- frozen task stream;
- frozen data splits;
- verified reference set;
- valid artifact hashes;
- complete performance matrix;
- no train/test or validation/test overlap;
- no Stage B test evaluation;
- no probe mutation;
- no future-task leakage;
- matched resource budgets for compared conditions;
- memory/retrieval budgets matched where required;
- reproducibility manifest complete;
- final `audit-run` passes.

---

# Research-Integrity Requirements

The implementation plan inherits the following release-blocking integrity requirements.

| ID | Requirement | First enforced |
|---|---|---|
| RI-1 | No test leakage into Stage B learning | Phase 0 |
| RI-2 | No memory/learner mutation during probes | Phase 0 |
| RI-3 | No future-task leakage | Phase 0 |
| RI-4 | Matched budgets for paired conditions | Phase 1 |
| RI-5 | Matched memory capacity for RQ2 conditions | Phase 2 |
| RI-6 | Matched retrieval budget / `top_k` for RQ2 unless explicitly ablated | Phase 2 |
| RI-7 | Final test evaluation uses frozen configuration only | Final experiment gate |

---

# Phase Overview

| Phase | Theme | Research role | Implementation-ready gates | Current status |
|---|---|---|---|---|
| Phase 0 | Reproducible experimental foundation | Build a trustworthy A/B/C continual substrate before any hypothesis test | Gate 0 + RI-1/2/3 foundation | `[~]` Core code mostly present; references, live LLM, resume, probe/audit gates remain |
| Phase 1 | RQ1 / H1 sequential baselines | Establish whether simple continuity causes forgetting/interference and establish strong simple retention baselines | Gate 1 + Gate 2 subset + RI-4 | `[ ]` Planned |
| Phase 2 | RQ2 / H2 managed memory | Test whether bounded managed memory improves stability–plasticity over naive/simple persistence | Gate 2 + Gate 3 + Gate 4 + RI-5/6 | `[ ]` Planned |
| Phase 3 | RQ3 / H3 forward transfer | Measure zero-shot transfer and adaptation efficiency using the already-existing A/B/C lifecycle | Gate 5 preparation | `[ ]` Planned |
| Phase 4 | Secondary extensions and paper study | Stress tests: distribution shift, task order/curriculum, selected cross-problem transfer, final reporting | Gate 5 final | `[ ]` Optional / secondary |

---

# Phase 0 — Reproducible Experimental Foundation

**Goal:** build a trustworthy experimental substrate before any H1 claim is made.

**Research capability unlocked:** reliable pilot execution only. No memory-mechanism claim is unlocked by Phase 0.

## Phase 0A — Data, Tasks, and References

### Build

- [x] Task registry for TSP/OBP/PFSP scaffolding.
- [x] TSP size stream: `TSP-20 -> TSP-50 -> TSP-100 -> TSP-200`.
- [x] Deterministic data generation with manifests and checksums.
- [x] TSPLIB-compatible TSP reader/fallback.
- [~] Exact/best-known reference pipeline.
- [ ] Generate and verify validation/test references for all primary TSP tasks.
- [ ] Freeze validation/reference policy before Phase 1.

### Verify

- [ ] deterministic generation test passes;
- [ ] split non-overlap test passes;
- [ ] reference-gap formula tests pass;
- [ ] reference generation is resumable per instance;
- [ ] reference status uses `optimal` only when justified.

---

## Phase 0B — Evaluator, Generator, and Budget Control

### Build

- [x] Subprocess evaluator for generated heuristic code.
- [x] Smoke baseline evaluation.
- [~] HeurAgenix generator adapter.
- [~] Hard LLM-call / candidate-evaluation budget accounting.
- [ ] Complete failure semantics and explicit timeout handling.
- [ ] Record generator/evaluator versions in run manifests.

### Verify

- [ ] no candidate evaluation beyond hard budget;
- [ ] no LLM call beyond hard budget;
- [ ] failed candidate execution is logged, not silently dropped;
- [ ] one real low-budget live-LLM `evolve-task` run succeeds.

---

## Phase 0C — Canonical Continual Runner

### Build

- [~] Resumable stream runner.
- [ ] Enforce the canonical Stage A -> B -> C ordering.
- [ ] Implement explicit read-only `ProbeContext`.
- [ ] Stage A MUST execute retained competence and persist `Z_k` when applicable.
- [ ] Stage B MUST record search trajectory `S_k(b)`.
- [ ] Stage C MUST evaluate all seen tasks without full re-search.
- [ ] Checkpoint after every task boundary.

### Verify

- [ ] tiny deterministic stream executes the complete A/B/C lifecycle;
- [ ] Stage A occurs before any learning event for `T_k`;
- [ ] Stage C occurs only after Stage B commits `M_k`;
- [ ] interrupted stream resume is equivalent to uninterrupted execution in deterministic mock mode.

---

## Phase 0D — Continual Metrics

### Build

- [x] Average performance / AP plumbing.
- [x] BWT plumbing.
- [x] FWT plumbing.
- [ ] Persist real `Z_k` values from Stage A.
- [ ] Build continual performance matrix `A_{k,j}` from Stage C.
- [ ] Standardize canonical performance score as higher-is-better normalized score.
- [ ] Keep raw objective and reference gap in evaluation records.

### Verify

- [ ] AP known-matrix test;
- [ ] BWT known-matrix test;
- [ ] average / worst-case forgetting tests;
- [ ] FWT handling for `N/A` incompatible transitions;
- [ ] performance matrix completeness test.

---

## Phase 0E — Integrity, Audit, and Resume

### Build

- [~] Reproducibility manifest.
- [~] `audit-run`.
- [ ] Behavioral state hash / snapshot comparison around probes.
- [ ] Future-task leakage checks.
- [ ] Test-leakage checks.
- [ ] Artifact/hash lineage needed for the Global Definition of Done.

### Required integrity tests

- [ ] **RI-1:** fail if Stage B references test instances/results.
- [ ] **RI-2:** fail if learner-affecting state mutates during Stage A or C.
- [ ] **RI-3:** fail if `T_k` learner input references evidence from a future task.

### Phase 0 Acceptance Gate — maps to Implementation-Ready Gate 0

Phase 0 passes only when:

- [ ] Concorde/reference pilot passes for all TSP sizes.
- [ ] Frozen validation/test references exist and verify.
- [ ] Validation/reference policy is documented and frozen.
- [ ] One live low-budget LLM evolution succeeds.
- [ ] One interrupted stream resumes without regenerating verified completed work.
- [ ] Same deterministic smoke config produces the same non-LLM artifacts and metrics.
- [ ] A/B/C lifecycle integration test passes.
- [ ] Probe read-only/hash invariant passes.
- [ ] A real executable pre-learning probe produces `Z_k` when applicable.
- [ ] `audit-run` passes on a complete pilot run.

### Deliverables

- Frozen Phase 0 TSP data and reference artifacts.
- One complete audited baseline stream.
- One valid continual performance matrix.
- Recorded `Z_k` probe outputs.
- Verified runner/evaluator/probe/audit logs.
- Frozen Phase 1 pilot budgets.

### Not yet claimed

- No H1 conclusion from one engineering smoke run.
- No managed-memory superiority.
- No forward-transfer claim from FWT plumbing alone.

---

# Phase 1 — RQ1 / H1 Sequential and Simple-Memory Baselines

**Goal:** determine whether simple forms of sequential knowledge continuity exhibit functional forgetting and/or harmful interference before introducing the full Archivist.

Phase 1 MUST distinguish five conceptually different conditions:

```text
1. isolated cold-start
2. population carryover
3. task-indexed heuristic library
4. naive bounded persistent memory
5. managed Archivist  ← not implemented until Phase 2
```

The `task_indexed_library` condition is required as a strong simple-retention baseline because storing the best specialist per known task may already provide excellent seen-task retention.

> Dependency note: if `TASK_INDEXED_LIBRARY` is still missing from the Implementation-Ready condition enum, align that specification before treating the Phase 1 baseline suite as final.

---

## Phase 1A — Isolated Cold-Start Reference

### Build / Verify

- [ ] Explicit isolated condition/config.
- [ ] No cross-task population state.
- [ ] No persistent external memory.
- [ ] No Archivist.
- [ ] No Retriever.
- [ ] Record independent search curves for use as cold-start baselines.
- [ ] Do not interpret isolated search itself as continual retention.

### Purpose

Provides the no-continuity reference for new-task adaptation cost and quality.

---

## Phase 1B — Population-Carryover Sequential

### Build

- [ ] Add `population_carryover` condition/config.
- [ ] Persist final selected candidate population after each task.
- [ ] Initialize `T_{k+1}` from compatible members of the final `T_k` population.
- [ ] Log effective carried population size.
- [ ] Reject incompatible interfaces without hidden conversion.
- [ ] Disable external memory, Archivist, and Retriever.

### Evaluate

- [ ] Run Stage A/B/C lifecycle.
- [ ] Stage C evaluates current population-derived retained competence without full re-search.
- [ ] Populate `A_{k,j}` after every task.
- [ ] Compute forgetting/BWT from Stage C, not from post-hoc re-optimization.

### Purpose

Isolates forgetting caused by sequential population drift without retrieval-side memory interference.

---

## Phase 1C — Task-Indexed Heuristic Library

### Build

- [ ] Add `task_indexed_library` condition/config.
- [ ] After learning each `T_k`, freeze the best validation-selected executable heuristic under its task identity.
- [ ] On a previously seen `T_j`, retrieve the frozen specialist for `T_j`.
- [ ] No cross-task semantic retrieval.
- [ ] No Archivist distillation/consolidation.
- [ ] No reuse on unseen tasks unless explicitly defined as a separate ablation.

### Evaluate

- [ ] Retention probe executes the stored specialist directly.
- [ ] Report seen-task retention and storage cost.
- [ ] Compare against population carryover and managed memory.

### Purpose

Answers the reviewer-level question:

> Why not simply save the best heuristic for every known task?

---

## Phase 1D — Explicit Memory Object Model

### Build

Use the Implementation-Ready memory schema rather than introducing a competing ad-hoc memory abstraction.

- [ ] First-class memory item anchored to executable heuristic artifact.
- [ ] Applicability / retrieval descriptor.
- [ ] Semantic/procedural abstraction field.
- [ ] Empirical/lifecycle metadata.
- [ ] Provenance and episode references.
- [ ] Deterministic memory IDs and artifact hashes.
- [ ] Persistent bounded `MemoryStore`.
- [ ] Separate scientific raw logs from learner-accessible memory.

### Verify

- [ ] add/get;
- [ ] capacity enforcement;
- [ ] deterministic IDs;
- [ ] immutable executable artifact hash;
- [ ] provenance survives eviction/history tracking;
- [ ] test evidence cannot update learner-visible memory.

---

## Phase 1E — Naive Bounded Persistent Memory

### Build

- [ ] Add `naive_persistent_memory` condition/config.
- [ ] Bounded memory enabled.
- [ ] No protection.
- [ ] Minimal/no distillation.
- [ ] Naive overwrite/FIFO-style eviction policy.
- [ ] Retriever v0 or deterministic equivalent.
- [ ] Retrieval result inserted into generation context in a deterministic logged format.

### Retrieval logging

Record at least:

- memory IDs;
- source task;
- retrieval rank;
- structural score;
- utility score if used;
- final score;
- context inclusion/omission;
- prompt/context hash;
- retrieval set size.

### Purpose

Isolates whether mere persistent memory creates retrieval-side interference and establishes the direct baseline for managed memory.

---

## Phase 1F — Retriever v0

### Build

- [ ] Explicit `RetrievalQuery`.
- [ ] Hard interface compatibility filter.
- [ ] Structural similarity.
- [ ] Deterministic utility normalization where applicable.
- [ ] Deterministic tie-breaking.
- [ ] Configurable `top_k`.
- [ ] Read-only retrieval mode.
- [ ] Retrieval diagnostics.
- [ ] No learned retriever / ANN / vector DB required.

### Verify — maps to Implementation-Ready Gate 2 subset

- [ ] structural filtering unit test;
- [ ] deterministic ranking test;
- [ ] exact `top_k` test;
- [ ] no-memory-mutation test;
- [ ] repeated identical query/snapshot returns identical ranking.

---

## Phase 1G — RQ1 Diagnostics

### Build

- [ ] competence coverage;
- [ ] retrieval coverage;
- [ ] source-task distribution;
- [ ] memory-age distribution;
- [ ] top-k concentration;
- [ ] duplicate / near-duplicate rate where defined;
- [ ] post-reuse validation delta;
- [ ] failure labels:
  - harmful reuse;
  - ineffective reuse;
  - retrieval pollution;
  - context competition;
  - memory dilution;
  - retrieval diversity collapse.

These are diagnostic metrics, not replacements for end-to-end retained competence.

---

## Phase 1 Integrity Requirement

### RI-4 — Matched budgets

For paired baseline comparisons:

- [ ] same task instances;
- [ ] same stream;
- [ ] same paired seed;
- [ ] same generator;
- [ ] same candidate-evaluation budget;
- [ ] same LLM budget;
- [ ] same evaluator limits.

Audit MUST flag mismatched conditions before aggregate statistics are accepted.

---

## Phase 1 Acceptance Gate — maps to Implementation-Ready Gate 1 + Gate 2 subset

Phase 1 passes when:

- [ ] isolated baseline completes end-to-end;
- [ ] population carryover completes end-to-end;
- [ ] task-indexed library completes end-to-end;
- [ ] naive bounded memory completes end-to-end;
- [ ] Stage A/B/C lifecycle is used consistently where semantically applicable;
- [ ] retention probes occur after every task;
- [ ] no full re-search occurs during retention;
- [ ] probe read-only invariant passes;
- [ ] real `Z_k` is recorded for directly executable Stage A probes;
- [ ] Retriever v0 ranking is deterministic and unit-tested;
- [ ] RI-1 to RI-4 pass;
- [ ] one-seed pilot is audited before repeated pilot runs;
- [ ] multi-seed pilot results include mean/variance and paired differences where appropriate.

### Statistical target

- Pilot/debugging may use fewer runs.
- Primary paper comparisons SHOULD target `n >= 5` paired independent seeds where computationally feasible.
- Fewer runs MUST be labeled preliminary and interpreted conservatively.

### Research capability unlocked

- RQ1/H1 can be evaluated.
- Functional forgetting/interference can be measured.
- Simple specialist storage can be compared against sequential continuity.
- Retrieval-side failures can be diagnosed.

### Not yet claimed

- Managed memory superiority.
- Full RQ2 stability–plasticity benefit.
- Full RQ3 forward-transfer/adaptation claim.

---

# Phase 2 — RQ2 / H2 Managed Archivist Memory

**Goal:** implement the proposed bounded managed-memory mechanism and test whether it improves retained competence over naive/simple persistence without unacceptable loss of new-task plasticity.

Phase 2 should compare at least:

```text
population carryover
task-indexed heuristic library
naive bounded persistent memory
managed Archivist
```

Isolated cold-start remains the learning-efficiency reference where needed.

---

## Phase 2A — Working Buffer and Archivist Lifecycle

### Build

- [ ] Bounded working buffer for recent uncommitted experience.
- [ ] Archivist admission.
- [ ] Promotion / rejection.
- [ ] Distillation.
- [ ] Utility evidence update.
- [ ] Provenance preservation.
- [ ] Transactional memory update / rollback.

The Archivist decides what becomes persistent memory; it MUST NOT own the retrieval algorithm.

---

## Phase 2B — Protection, Consolidation, and Eviction

### Build

- [ ] task-anchor / competence protection policy;
- [ ] utility-weighted retention;
- [ ] conservative exact/near-duplicate consolidation according to frozen policy;
- [ ] bounded eviction;
- [ ] deterministic eviction tie-breaking;
- [ ] capacity-invariant enforcement;
- [ ] explicit handling of protection-overflow/deadlock.

### Verify — maps to Implementation-Ready Gate 3

- [ ] protected item not evicted;
- [ ] naive overwrite order test;
- [ ] utility eviction order test;
- [ ] provenance preserved;
- [ ] exact duplicate consolidation test;
- [ ] transaction rollback test;
- [ ] capacity invariant holds after each task.

---

## Phase 2C — Managed Retrieval Protocol

### Build

- [ ] Use Retriever v0 as the initial managed-memory retriever.
- [ ] Query from observable task/search context.
- [ ] Structural filtering before ranking.
- [ ] Utility-aware deterministic reranking.
- [ ] Configurable `top_k`.
- [ ] Dedicated retrieval-context builder.
- [ ] Log omitted memories due to context budget.
- [ ] Keep probe retrieval counters separate from learner-affecting retrieval counters.

Do not introduce semantic vector retrieval until Retriever v0 produces trustworthy continual results.

---

## Phase 2D — RQ2 Diagnostic Controls

### Validation-Oracle Retrieval

- [ ] Implement validation-defined oracle/near-oracle retrieval.
- [ ] Use only validation evidence.
- [ ] Never use test labels/utilities for oracle selection.

**Purpose:** estimate whether failures are caused by poor retrieval versus poor memory content.

### Controlled Memory Pollution

- [ ] Implement a synthetic/controlled pollution runner.
- [ ] Add irrelevant/conflicting memories without changing the target useful memory.
- [ ] Measure retrieval degradation and downstream competence.

**Purpose:** separate storage loss from retrieval competition / functional forgetting.

### Retrieval Quality Diagnostics

Where labels are available:

- [ ] Recall@k;
- [ ] NDCG@k;
- [ ] competence coverage;
- [ ] context inclusion rate;
- [ ] downstream-use success.

Diagnostics MUST remain secondary to end-to-end task performance.

---

## Phase 2E — Capacity Sweep

RQ2 MUST NOT be interpreted from a single arbitrarily chosen memory capacity.

### Build

- [ ] capacity sweep configuration;
- [ ] validation procedure for selecting/fixing capacity regimes;
- [ ] matched naive-vs-managed comparisons for every capacity regime.

### Final RQ2 evidence

Where computationally feasible, use multiple pre-frozen capacity regimes such as:

```text
C_small
C_medium
C_large
```

Exact values are selected on validation and frozen before final test evaluation.

All comparisons at a given capacity MUST use the same `C`.

---

## Phase 2F — Plasticity / Non-Inferiority Criterion

H2 is not satisfied by reducing forgetting while severely harming learning on new tasks.

Before final test evaluation:

- [ ] define the primary new-task plasticity metric(s);
- [ ] define and freeze a practically meaningful non-inferiority margin `δ`;
- [ ] document how the margin was selected using domain/validation reasoning rather than test outcomes.

Conceptually:

```text
managed-memory retention gain
        AND
new-task plasticity degradation <= frozen acceptable margin
```

If no defensible non-inferiority margin can be defined, report the stability–plasticity trade-off transparently rather than making a binary “no plasticity cost” claim.

---

## Phase 2 Integrity Requirements

### RI-5 — Memory Capacity Matching

- [ ] naive and managed RQ2 conditions use identical `C` within each paired comparison.

### RI-6 — Retrieval Budget Matching

- [ ] naive and managed RQ2 conditions use identical `top_k` / retrieval budget unless retrieval size is itself the ablated variable.

Audit MUST flag violations.

---

## Phase 2 Acceptance Gate — maps to Implementation-Ready Gates 2, 3, and 4

Phase 2 passes when:

- [ ] Retriever v0 is deterministic and reproducible;
- [ ] full Archivist lifecycle exists;
- [ ] every active memory item is traceable to evidence;
- [ ] capacity invariant holds after every task;
- [ ] protection/eviction/consolidation tests pass;
- [ ] validation-oracle retrieval exists;
- [ ] controlled memory-pollution runner exists;
- [ ] capacity sweep config exists;
- [ ] matched multi-capacity RQ2 pilot runs complete where feasible;
- [ ] synthetic diagnostic can separately demonstrate:
  - storage loss;
  - retrieval failure;
  - downstream-use failure;
- [ ] RI-1 through RI-6 pass;
- [ ] test artifacts never enter prompts/memory utility;
- [ ] H2 pilot outcome is recorded as positive, negative, mixed, or inconclusive.

### Research capability unlocked

- RQ2/H2 can be tested.
- Managed vs naive bounded memory can be compared under matched capacity/search budgets.
- Stability and plasticity can be analyzed separately.
- Storage forgetting and retrieval-induced forgetting can be diagnosed mechanistically.

### Not yet claimed

- Final paper-grade H2 result before Gate 5.
- Broad cross-family generalization.
- Curriculum benefit.
- Semantic-retriever superiority.

---

# Phase 3 — RQ3 / H3 Forward Transfer and Adaptation Efficiency

**Goal:** evaluate when retained heuristic knowledge improves zero-shot competence and/or adaptation efficiency on later tasks.

Phase 3 does **not** introduce a new lifecycle stage.

The Stage A/B/C lifecycle already exists from Phase 0. Phase 3 completes the RQ3 analysis built on that instrumentation.

---

## Phase 3A — Zero-Shot Forward Transfer (`FWT_0`)

For executable-compatible transitions:

- [ ] use Stage A `Z_k` recorded before learning;
- [ ] define matched cold-start baseline `B_k`;
- [ ] compute `FWT_0 = Z_k - B_k`;
- [ ] preserve `N/A` for incompatible interfaces rather than inventing a score.

Ensure `Z_k` is generated by real execution of retained competence, not retrieval logging.

---

## Phase 3B — Adaptation Curves

### Build / Verify

- [ ] persist `S_k(b)` for every condition;
- [ ] choose a primary fixed budget axis per experiment;
- [ ] keep the same budget axis across compared methods;
- [ ] record checkpoints at the required search-budget resolution.

Candidate budget axes may include:

- candidate evaluations;
- generations;
- LLM calls;
- cumulative tokens.

The primary axis MUST be frozen before final evaluation.

---

## Phase 3C — Adaptation-Efficiency Metrics

- [ ] ACA / area-under-adaptation-curve comparison;
- [ ] fixed-budget gain (FBG);
- [ ] budget-to-target (BTT);
- [ ] paired cold-start vs continual comparisons;
- [ ] cost reporting:
  - LLM calls;
  - input/output tokens;
  - candidate evaluations;
  - generations;
  - wall-clock time;
  - memory/context size.

---

## Phase 3D — Forward-Transfer Conditions

Primary RQ3 should begin with transitions where interface compatibility and structural relation are cleanly defined, especially:

```text
TSP scale shift
TSP distribution shift
```

Cross-problem-family transitions may be added selectively, but direct zero-shot FWT is `N/A` when heuristic interfaces are incompatible.

For such transitions, evaluate transfer through adaptation efficiency under matched budgets.

---

## Phase 3 Acceptance Gate

Phase 3 passes when:

- [ ] every eligible task transition has a valid pre-learning `Z_k`;
- [ ] incompatible transitions are correctly marked `N/A`;
- [ ] matched cold-start baselines exist;
- [ ] adaptation curves are complete;
- [ ] ACA/FBG/BTT outputs are unit-tested and machine-readable;
- [ ] paired resource accounting is complete;
- [ ] no probe output updates the learner;
- [ ] forward-transfer conclusions distinguish zero-shot competence from adaptation efficiency.

### Research capability unlocked

- RQ3/H3 can be evaluated.
- The project can distinguish:
  - immediate reusable competence;
  - faster adaptation;
  - better fixed-budget quality;
  - no transfer / negative transfer.

### Not yet claimed

- Curriculum causality.
- General cross-family transfer unless explicitly tested.
- Final paper-grade result before Gate 5.

---

# Phase 4 — Secondary Extensions and Final Paper Study

**Goal:** stress-test the core findings without allowing secondary questions to block the primary CM-HH contribution.

These experiments are secondary unless promoted in a pre-frozen final protocol.

---

## Phase 4A — TSP Distribution-Shift Stress Test

Predefine this as a stress-test environment, not as a fallback chosen after seeing scale-shift results.

Example:

```text
uniform Euclidean TSP
        ↓
clustered / other pre-specified distribution
```

- [ ] freeze distributions before final test;
- [ ] preserve heuristic interface;
- [ ] run selected primary conditions;
- [ ] evaluate forgetting, retrieval interference, and transfer under a stronger shift.

A negative/weak signal on scale shift does not automatically invalidate the study and MUST NOT trigger opportunistic test-set redesign.

---

## Phase 4B — Task Ordering / Curriculum (Secondary RQ)

- [ ] fixed ascending order;
- [ ] random order with recorded seed;
- [ ] similarity-based order selected without final-test leakage;
- [ ] memory mechanism fixed while order varies;
- [ ] record complete order in every manifest.

Curriculum is a property of the continual environment, not a prerequisite for the core managed-memory mechanism.

---

## Phase 4C — Selected Cross-Problem Stream

Only implement when core TSP experiments are stable enough to justify the cost.

- [ ] finalize selected adapters;
- [ ] generate/freeze problem-specific splits;
- [ ] generate verified references/best-known records;
- [ ] validate objective direction and heuristic interfaces;
- [ ] define compatibility relations explicitly;
- [ ] use adaptation efficiency rather than artificial zero-shot scores for incompatible interfaces.

Do not require every candidate family (CVRP/OVRP/VRPTW/OBP/PFSP) for the first paper.

---

# Final Experiment Readiness Gate — maps to Implementation-Ready Gate 5

No result is considered paper-grade until all items below pass.

## Frozen Protocol

- [ ] validation-frozen hyperparameters;
- [ ] frozen task streams;
- [ ] frozen distributions/order;
- [ ] frozen train/validation/test splits;
- [ ] frozen reference sets;
- [ ] frozen memory capacities;
- [ ] frozen retrieval budgets / `top_k`;
- [ ] frozen prompts and generator hyperparameters;
- [ ] frozen plasticity/non-inferiority criterion where used.

## Statistical Execution

- [ ] paired seed schedule finalized;
- [ ] primary comparisons target `n >= 5` independent paired seeds where computationally feasible;
- [ ] smaller `n` explicitly labeled as a limitation;
- [ ] report mean and standard deviation;
- [ ] report paired method differences;
- [ ] report confidence intervals;
- [ ] predefine primary metrics per RQ;
- [ ] use multiple-comparison correction where appropriate.

## Integrity

- [ ] RI-1 passes;
- [ ] RI-2 passes;
- [ ] RI-3 passes;
- [ ] RI-4 passes;
- [ ] RI-5 passes;
- [ ] RI-6 passes;
- [ ] **RI-7:** final test runs use `config_status: frozen`;
- [ ] no test leakage;
- [ ] no future-task leakage;
- [ ] no probe mutation.

## Audit

- [ ] every final metric satisfies the Global Definition of Done;
- [ ] complete reproducibility manifest;
- [ ] git commit recorded;
- [ ] dataset/reference hashes valid;
- [ ] performance matrices complete;
- [ ] final memory snapshots valid;
- [ ] artifact hashes valid;
- [ ] final `audit-run` returns success.

Only after this gate may results be described as final paper evidence.

---

# Final Reporting

## Primary RQ1 outputs

- forgetting curves;
- final / average BWT;
- average and worst-case forgetting;
- per-task retained performance;
- comparison:
  - population carryover;
  - task-indexed library;
  - naive bounded memory.

## Primary RQ2 outputs

- managed vs naive retention under matched capacity;
- final/average performance;
- forgetting/BWT;
- new-task plasticity;
- capacity sensitivity;
- validation-oracle diagnostic;
- memory-pollution diagnostic;
- retrieval-quality diagnostics.

## Primary RQ3 outputs

- `FWT_0` where executable;
- adaptation curves;
- `ΔACA`;
- FBG;
- BTT;
- resource-efficiency metrics.

## Secondary outputs

- task-order sensitivity;
- distribution-shift stress test;
- selected cross-problem transfer;
- qualitative cases of helpful/harmful retrieved memory.

## Statistical honesty

- Negative and inconclusive results are valid.
- Do not select the main claim based on whichever metric happens to look favorable.
- Distinguish primary end-to-end competence metrics from diagnostic retrieval metrics.
- Paper wording MUST match the measured signal.

---

# Immediate Next Actions

1. **Finish Phase 0 acceptance gate.**
   - generate and verify full TSP validation/test references;
   - complete one real low-budget LLM run;
   - enforce the canonical A/B/C lifecycle;
   - make Stage A produce real `Z_k`;
   - add probe behavioral-hash/read-only test;
   - complete one interrupted/resumed deterministic equivalence test;
   - pass `audit-run` on one complete pilot.

2. **Align the task-indexed baseline across specifications.**
   - add/confirm `TASK_INDEXED_LIBRARY` in the Implementation-Ready experimental conditions;
   - then implement the Phase 1 condition.

3. **Implement Phase 1 baseline suite before the full Archivist.**
   - population carryover;
   - task-indexed heuristic library;
   - explicit memory model/store;
   - naive bounded memory;
   - Retriever v0;
   - RI-4 matched-budget audit.

4. **Run an audited RQ1 pilot before Phase 2.**
   - do not require a positive forgetting result to proceed;
   - record whether scale shift produces strong, weak, or negligible interference;
   - use the pre-specified distribution-shift/pollution diagnostics later as mechanistic stress tests, not post-hoc rescue experiments.

5. **Only then implement the full Archivist and RQ2 diagnostic suite.**
   - working buffer;
   - admission/distillation;
   - protection/consolidation/eviction;
   - oracle retrieval;
   - controlled pollution;
   - capacity sweep;
   - plasticity criterion.

6. **Complete RQ3 analysis after the continual instrumentation is stable.**
   - use already-collected `Z_k`;
   - adaptation curves;
   - FWT0 / ACA / FBG / BTT;
   - matched cold-start comparisons.

7. **Treat curriculum and broad cross-problem experiments as secondary.**
   - they must not block the core CM-HH paper if RQ1–RQ3 are already answered cleanly.
