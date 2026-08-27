# CMHH — Implementation-Ready Specification

**Project:** Continual Multi-Agent Hyper-Heuristics (CMHH)  
**Document type:** Engineering / Research Implementation Specification  
**Status:** Implementation-ready baseline specification  
**Primary audience:** ML Research Engineers, Research Software Engineers, PhD researchers implementing CMHH  
**Language:** English for code-level precision  
**Intended repository root:** `CM_HH/`  
**Normative keywords:** **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY**

---

# 0. Executive Summary

CMHH is a continual LLM-based heuristic-search system for sequential combinatorial-optimization (CO) tasks.

The core research setting is:

```text
T1 -> T2 -> T3 -> ... -> TK
```

The underlying LLM is not continually fine-tuned. Learning occurs at the **heuristic-search system level** through:

1. evolutionary / LLM-based heuristic discovery;
2. persistent heuristic knowledge;
3. retrieval and selection;
4. memory management;
5. reuse and adaptation across tasks.

The implementation MUST preserve the research distinction:

```text
evolutionary population = working search state

working buffer          = recent, not-yet-consolidated experience

long-term memory        = persistent continual knowledge

Archivist               = controls what is written, updated,
                          protected, consolidated, and evicted

Retriever               = selects/ranks existing memories
                          for a given query

Evaluator               = executes heuristic artifacts and measures quality

Experiment Runner       = enforces sequential protocol and prevents leakage
```

The most important engineering constraint is:

> **Evaluation probes are read-only. Test performance must never update the learner.**

For every task `Tk`, the canonical continual loop is:

```text
state M{k-1}
    |
    v
[A] PRE-LEARNING PROBE
    - retrieve/select only
    - no evolutionary search
    - no new heuristic generation
    - no memory write/update
    |
    v
[B] LEARN / SEARCH Tk
    - normal heuristic search
    - generator + evaluator
    - working buffer
    - Archivist may write/update memory
    |
    v
state Mk
    |
    v
[C] RETENTION PROBE
    - evaluate T1 ... Tk using current retained competence
    - no full re-search
    - no memory write/update
    |
    v
checkpoint + logs + metrics
```

This specification converts the existing research and architecture documents into concrete software contracts while explicitly marking which implementation choices are **engineering defaults** rather than research claims.

---

# 1. Source-of-Truth Hierarchy

The project currently contains three conceptual layers.

## 1.1 Research-level source of truth

`CMHH_Research_Specification`

Defines:

- research thesis;
- task-stream semantics;
- memory / forgetting / transfer definitions;
- RQs and hypotheses;
- evaluation protocol;
- test-set isolation;
- resource matching;
- statistical reporting.

If an implementation choice would change an RQ, hypothesis, metric meaning, or evaluation protocol, the **Research Specification wins**.

---

## 1.2 Architecture-level source of truth

`CMHH_Archivist_Retriever_Design_Specification`

Defines:

- Archivist as a selective consolidation mechanism;
- Retriever as a separate selection/ranking component;
- structured hybrid memory;
- working-buffer vs long-term-memory distinction;
- storage vs retrieval-induced forgetting;
- hybrid target Retriever;
- simpler Retriever v0.

If older project notes combine Archivist and Retriever into one class, the **newer separation is authoritative**.

The implementation MUST NOT expose retrieval as the Archivist's primary responsibility.

Incorrect:

```python
archivist.retrieve(...)
```

Required conceptual separation:

```python
retrieved = retriever.retrieve(
    query=query,
    memory=memory_store.snapshot(),
)
```

The Archivist may maintain metadata used by retrieval, but MUST NOT own the retrieval algorithm.

---

## 1.3 This implementation specification

This document defines:

- package layout;
- data schemas;
- interfaces;
- persistence;
- lifecycle;
- default algorithms;
- event logging;
- configuration;
- failure behavior;
- test contracts;
- acceptance gates.

When this document introduces a value not fixed by the research documents, it is marked:

- **[FIXED]** — required by research/design semantics;
- **[DEFAULT]** — engineering bootstrap default; configurable;
- **[VALIDATE]** — must be chosen/frozen using validation experiments before final test evaluation;
- **[ABLATION]** — experimental variable;
- **[FUTURE]** — not required for the initial implementation.

---

# 2. Scope

## 2.1 In scope

The implementation covered by this specification includes:

- task registry and task adapters;
- fixed train / validation / test splits;
- deterministic dataset manifests and checksums;
- reference objective pipeline;
- normalized optimization scores;
- safe subprocess evaluator for LLM-generated heuristic code;
- HeurAgenix-compatible generator adapter;
- hard search / LLM budget accounting;
- resumable sequential stream runner;
- population-carryover baseline;
- naive persistent-memory baseline;
- full Archivist;
- Retriever v0;
- target hybrid Retriever interface;
- continual performance matrix;
- BWT / forgetting / FWT / adaptation-efficiency metrics;
- retrieval diagnostics;
- reproducibility manifests;
- event-sourced audit logs;
- checkpoints and resume.

---

## 2.2 Initial task scope

**[FIXED for the first reliable implementation]**

The first fully supported stream SHOULD be:

```text
TSP-20 -> TSP-50 -> TSP-100 -> TSP-200
```

with fixed Euclidean instance generation and stable train/validation/test splits.

The architecture MUST remain extensible to:

- distribution shifts within TSP;
- CVRP;
- OVRP;
- VRPTW;
- other CO families;
- constructive and local-search heuristic interfaces.

Cross-problem transfer MUST NOT be required to validate the initial TSP scale-shift implementation.

---

## 2.3 Explicit non-goals for v0/v1

The initial implementation MUST NOT depend on:

- fine-tuning the underlying LLM;
- a learned retriever;
- a vector database;
- ANN infrastructure;
- an LLM reranker on every retrieval;
- online test-set adaptation;
- arbitrary full re-search during retention probes;
- unlimited persistent memory;
- a single universal heuristic across all CO families.

These MAY be added later as controlled extensions.

---

# 3. Required Repository Architecture

Recommended package layout:

```text
CM_HH/
├── pyproject.toml
├── README.md
├── configs/
│   ├── experiments/
│   │   ├── isolated_tsp.yaml
│   │   ├── population_carryover_tsp.yaml
│   │   ├── naive_memory_tsp.yaml
│   │   └── archivist_tsp.yaml
│   ├── streams/
│   │   ├── tsp_size_ascending.yaml
│   │   └── tsp_size_random.yaml
│   ├── tasks/
│   │   ├── tsp_20.yaml
│   │   ├── tsp_50.yaml
│   │   ├── tsp_100.yaml
│   │   └── tsp_200.yaml
│   ├── memory/
│   │   ├── naive.yaml
│   │   ├── archivist.yaml
│   │   └── retriever_v0.yaml
│   ├── generators/
│   │   └── heuragenix.yaml
│   └── solvers/
│       └── concorde.yaml
│
├── src/cmhh/
│   ├── cli.py
│   │
│   ├── core/
│   │   ├── ids.py
│   │   ├── types.py
│   │   ├── errors.py
│   │   └── hashing.py
│   │
│   ├── tasks/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── tsp.py
│   │   └── compatibility.py
│   │
│   ├── data/
│   │   ├── generator.py
│   │   ├── manifests.py
│   │   ├── splits.py
│   │   └── references.py
│   │
│   ├── heuristics/
│   │   ├── artifact.py
│   │   ├── interface.py
│   │   └── validation.py
│   │
│   ├── generation/
│   │   ├── base.py
│   │   ├── heuragenix_adapter.py
│   │   ├── budgets.py
│   │   └── prompts.py
│   │
│   ├── evaluation/
│   │   ├── evaluator.py
│   │   ├── subprocess_runner.py
│   │   ├── objective.py
│   │   └── reference_gap.py
│   │
│   ├── memory/
│   │   ├── models.py
│   │   ├── store.py
│   │   ├── working_buffer.py
│   │   ├── archivist.py
│   │   ├── admission.py
│   │   ├── distillation.py
│   │   ├── protection.py
│   │   ├── consolidation.py
│   │   ├── eviction.py
│   │   └── utility.py
│   │
│   ├── retrieval/
│   │   ├── base.py
│   │   ├── query.py
│   │   ├── structural.py
│   │   ├── retriever_v0.py
│   │   ├── hybrid.py
│   │   └── diagnostics.py
│   │
│   ├── continual/
│   │   ├── runner.py
│   │   ├── probes.py
│   │   ├── conditions.py
│   │   ├── population_carryover.py
│   │   └── checkpoints.py
│   │
│   ├── metrics/
│   │   ├── performance_matrix.py
│   │   ├── continual.py
│   │   ├── transfer.py
│   │   ├── retrieval.py
│   │   └── statistics.py
│   │
│   ├── logging/
│   │   ├── events.py
│   │   ├── event_writer.py
│   │   ├── manifests.py
│   │   └── audit.py
│   │
│   └── persistence/
│       ├── sqlite.py
│       ├── artifacts.py
│       └── snapshots.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   └── fixtures/
│
├── artifacts/
│   └── .gitkeep
│
└── runs/
    └── .gitkeep
```

The package layout MAY differ physically, but the component boundaries MUST remain equivalent.

---

# 4. Runtime Architecture

```text
                           +-------------------+
                           |    StreamSpec     |
                           +---------+---------+
                                     |
                                     v
+-------------+            +-------------------+
| TaskRegistry|----------->| ContinualRunner   |
+-------------+            +---------+---------+
                                     |
                  +------------------+------------------+
                  |                  |                  |
                  v                  v                  v
          Pre-learning Probe   Current-task Search   Retention Probe
                  |                  |                  |
                  |                  v                  |
                  |          +---------------+          |
                  |          |   Generator   |          |
                  |          +-------+-------+          |
                  |                  | candidates       |
                  |                  v                  |
                  |          +---------------+          |
                  |          |   Evaluator   |          |
                  |          +-------+-------+          |
                  |                  | evidence         |
                  |                  v                  |
                  |          +---------------+          |
                  |          | WorkingBuffer |          |
                  |          +-------+-------+          |
                  |                  |                  |
                  |                  v                  |
                  |          +---------------+          |
                  |          |   Archivist   |          |
                  |          +-------+-------+          |
                  |                  | writes/updates   |
                  |                  v                  |
                  +---------->+---------------+<--------+
                              |  MemoryStore  |
                              +-------+-------+
                                      ^
                                      |
                              +-------+-------+
                              |   Retriever   |
                              +---------------+
```

All probe paths MUST be configured with `read_only=True`.

---

# 5. Core Domain Models

All durable domain models SHOULD be dataclasses or Pydantic models with explicit serialization versions.

Every durable record MUST include:

```python
schema_version: int
```

The initial version is:

```text
schema_version = 1
```

---

## 5.1 `TaskSpec`

```python
@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    problem_family: str
    formulation: str
    heuristic_interface: str

    problem_size: int | None
    distribution: str | None
    objective_sense: Literal["min", "max"]

    train_manifest: str
    validation_manifest: str
    test_manifest: str

    reference_set: str
    task_features: Mapping[str, JsonValue]

    schema_version: int = 1
```

Example:

```yaml
task_id: tsp_100_uniform
problem_family: TSP
formulation: euclidean_tsp
heuristic_interface: tsp_constructive_v1
problem_size: 100
distribution: euclidean_uniform
objective_sense: min
train_manifest: data/manifests/tsp_100_train.json
validation_manifest: data/manifests/tsp_100_validation.json
test_manifest: data/manifests/tsp_100_test.json
reference_set: data/references/tsp_100/
task_features:
  metric: euclidean
  coordinate_space: unit_square
```

### Contract

- `task_id` MUST be immutable within an experiment.
- `heuristic_interface` MUST determine executable compatibility.
- Test instances MUST NOT be used by generation, search, Archivist admission, retrieval tuning, or curriculum selection.

---

## 5.2 `DatasetManifest`

```python
@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    task_id: str
    split: Literal["smoke", "train", "validation", "test"]
    generator_name: str
    generator_version: str
    seed: int
    instances: tuple["InstanceManifest", ...]
    checksum: str
    schema_version: int = 1
```

Each instance record:

```python
@dataclass(frozen=True)
class InstanceManifest:
    instance_id: str
    relative_path: str
    sha256: str
    generation_seed: int | None
```

### Contract

- Dataset generation MUST be deterministic from manifest inputs.
- The manifest checksum MUST change when any instance changes.
- Resume MUST verify checksums before continuing a run.

---

## 5.3 `ReferenceRecord`

```python
@dataclass(frozen=True)
class ReferenceRecord:
    instance_id: str
    objective: float
    solver: str
    solver_version: str | None
    status: Literal[
        "optimal",
        "best_known",
        "feasible",
        "failed",
    ]
    runtime_seconds: float
    checksum: str | None
    schema_version: int = 1
```

### Contract

- `optimal` MUST only be used when optimality is established by the configured reference pipeline.
- Otherwise report `best_known` / `reference gap`, not "optimality gap".
- Reference generation MUST be resumable per instance.

---

## 5.4 `HeuristicArtifact`

```python
@dataclass(frozen=True)
class HeuristicArtifact:
    artifact_id: str
    code_path: str
    code_sha256: str

    language: Literal["python"]
    entrypoint: str
    heuristic_interface: str

    thought: str | None
    parent_artifact_ids: tuple[str, ...]
    generation_operator: str | None

    source_task_id: str
    source_run_id: str
    source_generation: int | None

    created_at: str
    schema_version: int = 1
```

### Contract

`HeuristicArtifact` is immutable.

If code changes, it receives a new `artifact_id` and new hash.

---

## 5.5 `CandidateEvaluation`

```python
@dataclass(frozen=True)
class CandidateEvaluation:
    evaluation_id: str
    artifact_id: str
    task_id: str
    split: Literal["smoke", "train", "validation", "test"]

    instance_ids: tuple[str, ...]

    mean_objective: float | None
    mean_reference_gap: float | None
    performance_score: float | None

    success_count: int
    failure_count: int
    timeout_count: int

    runtime_seconds: float
    evaluator_version: str

    read_only_probe: bool
    created_at: str
    schema_version: int = 1
```

The canonical continual score is:

```text
performance_score = -relative_reference_gap
```

so:

```text
higher = better
```

---

# 6. Memory Data Model

The conceptual long-term memory unit is:

```text
m_i = (h_i, k_i, z_i, mu_i)
```

The implementation MUST preserve these four logical roles.

---

## 6.1 `MemoryItem`

```python
@dataclass(frozen=True)
class MemoryItem:
    memory_id: str

    # h_i
    artifact_id: str

    # k_i
    applicability: "ApplicabilityDescriptor"

    # z_i
    abstraction: "KnowledgeAbstraction"

    # mu_i
    metadata: "MemoryMetadata"

    episode_refs: tuple[str, ...]

    created_at: str
    updated_at: str
    schema_version: int = 1
```

A memory item MUST be anchored to an executable artifact in the initial implementation.

Semantic knowledge and episodic provenance are linked to the artifact rather than stored as completely detached untraceable text.

---

## 6.2 `ApplicabilityDescriptor`

```python
@dataclass(frozen=True)
class ApplicabilityDescriptor:
    problem_family: str
    formulation: str
    heuristic_interface: str

    min_problem_size: int | None
    max_problem_size: int | None
    distributions: tuple[str, ...]

    heuristic_type: Literal[
        "constructive",
        "local_search",
        "repair",
        "selection",
        "hybrid",
        "unknown",
    ]

    objective_sense: Literal["min", "max"]

    applicability_text: str | None
    tags: tuple[str, ...]

    schema_version: int = 1
```

### Required retrieval rule

`heuristic_interface` is the hard executable-compatibility boundary for direct execution.

For zero-shot execution:

```python
query.heuristic_interface == item.applicability.heuristic_interface
```

MUST hold.

Semantic reuse MAY cross interface boundaries only in later full-retriever / adaptation experiments.

---

## 6.3 `KnowledgeAbstraction`

```python
@dataclass(frozen=True)
class KnowledgeAbstraction:
    summary: str
    reusable_principle: str | None
    known_failure_mode: str | None
    adaptation_hint: str | None

    source: Literal[
        "deterministic",
        "local_llm",
        "large_llm_fallback",
    ]

    model_id: str | None
    prompt_hash: str | None

    schema_version: int = 1
```

### Contract

- Distillation output MUST be structured and schema-valid.
- Free-form LLM output MUST NOT be persisted directly as a memory item before validation.
- The full prompt and model configuration MUST be logged.

---

## 6.4 `MemoryMetadata`

```python
@dataclass(frozen=True)
class MemoryMetadata:
    origin_task_id: str
    origin_run_id: str
    origin_generation: int | None

    parent_memory_ids: tuple[str, ...]

    source_validation_score: float
    source_validation_gap: float | None

    retrieval_count: int
    successful_reuse_count: int
    failed_reuse_count: int

    transfer_scores: Mapping[str, float]

    novelty_score: float | None
    utility_score: float | None

    protection_status: Literal[
        "unprotected",
        "protected_task_anchor",
        "protected_transfer",
        "protected_manual_experiment",
    ]

    last_retrieved_at: str | None
    last_successful_reuse_at: str | None

    active: bool
    eviction_reason: str | None

    schema_version: int = 1
```

Although the dataclass is shown frozen, updates SHOULD be implemented as versioned replacement records, not in-place mutation of historical evidence.

---

# 7. Episodic Layer

The episodic layer stores compressed evidence about important search transitions.

## 7.1 `SearchEpisode`

```python
@dataclass(frozen=True)
class SearchEpisode:
    episode_id: str
    task_id: str
    run_id: str

    parent_artifact_ids: tuple[str, ...]
    child_artifact_id: str

    operator: str
    generation: int

    parent_validation_score: float | None
    child_validation_score: float | None
    validation_delta: float | None

    search_context: Mapping[str, JsonValue]

    trace_path: str | None
    prompt_hash: str | None
    response_hash: str | None

    created_at: str
    schema_version: int = 1
```

The system MUST NOT persist every raw LLM trajectory indefinitely.

Raw traces MAY exist in run artifacts for reproducibility, while only selected episode records become part of persistent continual memory.

---

# 8. Working Buffer

The working buffer is task-local and short-lived.

```python
class WorkingBuffer(Protocol):
    def add_episode(self, episode: SearchEpisode) -> None: ...
    def add_candidate(
        self,
        artifact: HeuristicArtifact,
        evaluation: CandidateEvaluation,
    ) -> None: ...
    def snapshot(self) -> WorkingBufferSnapshot: ...
    def clear(self) -> None: ...
```

## 8.1 Buffer policy

**[DEFAULT]**

During a task, retain:

- best `N_elite_buffer = 10` candidates by validation score;
- most recent `N_recent_buffer = 20` evaluated candidates;
- top `N_improvement_episodes = 10` episodes by positive validation delta;
- top `N_failure_episodes = 5` diagnostically significant failures.

These are bootstrap values.

**[VALIDATE]** before final experiments if they materially affect Archivist behavior.

The working buffer does not count toward long-term memory capacity `C`.

Its serialized size MUST still be logged.

---

# 9. Persistence Architecture

## 9.1 Required persistence model

**[DEFAULT engineering choice]**

Use:

```text
SQLite               -> structured metadata, events, indices, checkpoints
filesystem           -> generated code, prompts, raw traces, snapshots
JSON/YAML             -> human-readable configs and immutable manifests
```

Do not require a vector database for Retriever v0.

Recommended run directory:

```text
runs/<run_id>/
├── config.resolved.yaml
├── reproducibility_manifest.json
├── events.jsonl
├── run.sqlite
├── checkpoints/
│   ├── task_000/
│   ├── task_001/
│   └── ...
├── prompts/
├── responses/
├── heuristics/
├── evaluations/
├── memory_snapshots/
├── metrics/
└── final/
```

---

## 9.2 Content-addressed artifacts

Generated code and raw prompt/response artifacts SHOULD be addressed by SHA-256.

Example:

```text
artifacts/sha256/ab/cd/abcdef....py
```

The DB stores the content hash and relative path.

This allows:

- deduplication;
- reproducibility;
- lineage verification;
- corruption detection.

---

# 10. `MemoryStore` Contract

```python
class MemoryStore(Protocol):
    def count_active(self) -> int: ...

    def get(self, memory_id: str) -> MemoryItem: ...

    def list_active(self) -> Sequence[MemoryItem]: ...

    def add(
        self,
        item: MemoryItem,
        *,
        cause_event_id: str,
    ) -> None: ...

    def replace_version(
        self,
        item: MemoryItem,
        *,
        cause_event_id: str,
    ) -> None: ...

    def mark_evicted(
        self,
        memory_id: str,
        reason: str,
        *,
        cause_event_id: str,
    ) -> None: ...

    def snapshot(self) -> "MemorySnapshot": ...

    def restore(self, snapshot_id: str) -> None: ...
```

## 10.1 Capacity invariant

For bounded-memory experiments:

```text
count_active() <= C
```

MUST hold after every Archivist transaction.

Evicted records MUST remain in the audit database as inactive historical records.

Deletion of historical provenance is forbidden during an experiment.

---

# 11. Archivist Contract

The Archivist governs lifecycle decisions.

```python
class Archivist(Protocol):
    def process_task_experience(
        self,
        *,
        task: TaskSpec,
        buffer: WorkingBufferSnapshot,
        memory: MemoryStore,
        context: ArchivistContext,
    ) -> ArchivistResult:
        ...
```

The Archivist MUST NOT expose `retrieve()`.

---

## 11.1 `ArchivistContext`

```python
@dataclass(frozen=True)
class ArchivistContext:
    run_id: str
    task_index: int

    capacity: int
    admission_policy: str
    consolidation_policy: str
    protection_policy: str
    eviction_policy: str

    validation_only: bool = True
```

`validation_only` MUST remain true for all evidence that influences memory-management decisions in final experiments.

---

## 11.2 Archivist transaction

One Archivist transaction is:

```text
WorkingBufferSnapshot
        |
        v
1. build admission candidates
        |
        v
2. deterministic eligibility filter
        |
        v
3. optional structured distillation
        |
        v
4. novelty / redundancy analysis
        |
        v
5. promote / reject
        |
        v
6. update utility evidence
        |
        v
7. protect anchors if policy requires
        |
        v
8. consolidate duplicates if enabled
        |
        v
9. evict until |M| <= C
        |
        v
10. atomic commit
```

If any step fails, the transaction MUST either:

- roll back completely; or
- produce an explicit partial-failure event and leave memory in a valid pre-transaction state.

Silent partial mutation is forbidden.

---

# 12. Admission Policy

A generated candidate is not automatically long-term memory.

## 12.1 Admission candidate sources

**[DEFAULT]**

At the end of a task, build admission candidates from:

1. top validation elites;
2. largest positive improvement episodes;
3. retained diagnostic failures that can produce useful warnings;
4. heuristics that showed positive reuse/transfer evidence during the task.

Defaults:

```yaml
admission:
  max_elites: 3
  max_improvement_episodes: 3
  max_failure_warnings: 2
  max_transfer_items: 3
```

These values are **[VALIDATE]**.

---

## 12.2 Deterministic eligibility

Every procedural memory candidate MUST satisfy:

- code parses successfully;
- configured heuristic entrypoint exists;
- smoke evaluation succeeds;
- validation evaluation has sufficient successful instances;
- source artifact hash is available;
- provenance is complete.

A candidate failing these checks MUST NOT become active long-term procedural memory.

---

## 12.3 Promotion criteria

The promotion policy is configurable.

### `elite_validation` — initial deterministic policy

Promote the top `max_elites` valid artifacts on validation score.

This is the preferred first implementation because it is:

- deterministic;
- easy to audit;
- independent of an LLM judge.

### `multi_signal` — full Archivist policy

A candidate may be promoted because of:

- high validation utility;
- high novelty;
- demonstrated positive transfer;
- diagnostically useful failure information.

A recommended implementation interface:

```python
@dataclass(frozen=True)
class AdmissionDecision:
    artifact_id: str
    promote: bool
    reasons: tuple[str, ...]
    quality_component: float | None
    novelty_component: float | None
    transfer_component: float | None
    diagnostic_component: float | None
```

The final threshold values are **[VALIDATE]**.

---

# 13. Distillation

Distillation converts selected evidence into reusable abstraction `z_i`.

## 13.1 Backend interface

```python
class Distiller(Protocol):
    def distill(
        self,
        *,
        task: TaskSpec,
        artifact: HeuristicArtifact,
        episodes: Sequence[SearchEpisode],
        validation_evidence: Sequence[CandidateEvaluation],
    ) -> KnowledgeAbstraction:
        ...
```

---

## 13.2 Model policy

**[FIXED architecture principle]**

When an LLM is required for Archivist operations, use a small local model by default.

**[DEFAULT implementation behavior]**

```yaml
distillation:
  backend: local_llm
  fallback_enabled: false
  temperature: 0.0
  response_format: structured_json
```

A large-model fallback MAY be supported but MUST be:

- disabled by default in primary experiments until explicitly validated;
- logged as a separate model call;
- included in token / cost accounting;
- recorded in `KnowledgeAbstraction.source`.

The exact model identifier is **[VALIDATE]** and MUST be frozen before final test runs.

---

## 13.3 Distillation output schema

The LLM MUST produce JSON equivalent to:

```json
{
  "summary": "...",
  "reusable_principle": "...",
  "known_failure_mode": null,
  "adaptation_hint": "...",
  "applicability_text": "..."
}
```

The implementation MUST:

1. parse JSON;
2. validate schema;
3. reject malformed output;
4. never infer missing critical fields silently;
5. log prompt and raw response hashes.

One retry MAY be allowed for malformed structured output.

Retry count MUST be configurable and logged.

---

# 14. Novelty and Redundancy

Novelty is a memory-management signal, not a test metric.

## 14.1 Retriever v0-compatible novelty

**[DEFAULT]**

Use deterministic feature overlap plus artifact identity:

- exact code hash duplicate -> novelty `0`;
- same applicability descriptor + highly similar normalized source behavior -> low novelty;
- new applicability region or materially different validation behavior -> higher novelty.

No embedding model is required for the first implementation.

A concrete interface:

```python
class NoveltyEstimator(Protocol):
    def score(
        self,
        candidate: MemoryDraft,
        memory: Sequence[MemoryItem],
    ) -> float:
        # Return a score in [0, 1].
        ...
```

The precise estimator is **[VALIDATE]**.

For the first end-to-end build, a simple descriptor/Jaccard implementation is acceptable.

---

# 15. Protection Policy

Protection prevents selected competence anchors from being evicted.

```python
class ProtectionPolicy(Protocol):
    def assign(
        self,
        *,
        memory: Sequence[MemoryItem],
        task: TaskSpec,
        newly_admitted: Sequence[MemoryItem],
    ) -> Mapping[str, str]:
        # memory_id -> protection_status
        ...
```

---

## 15.1 Policies to support

### `none`

No memory is protected.

Required for naive memory baselines.

### `task_anchor`

Maintain at least `q` protected competence anchors per completed task where possible.

**[DEFAULT bootstrap]**

```yaml
protection:
  policy: task_anchor
  anchors_per_task: 1
```

`anchors_per_task` is **[VALIDATE]**.

### `utility_protected`

Protect memories with strong repeated cross-task utility.

**[FUTURE / ABLATION]**

---

# 16. Utility Model

Utility is empirical evidence for memory management.

The implementation MUST store utility components separately, even if it also computes a scalar score.

Required components:

```python
@dataclass(frozen=True)
class UtilityEvidence:
    source_validation_score: float
    reuse_success_rate: float | None
    mean_transfer_delta: float | None
    retrieval_count: int
    successful_reuse_count: int
    failed_reuse_count: int
```

---

## 16.1 Bootstrap utility

For the first deterministic Archivist implementation:

```text
utility = source validation performance
```

where higher `performance_score` is better.

This avoids introducing arbitrary multi-signal weights too early.

---

## 16.2 Full utility-weighted retention

The implementation SHOULD support configurable normalized components:

```text
U_i =
    w_quality  * Q_i
  + w_reuse    * R_i
  + w_transfer * T_i
```

where every component is normalized to `[0,1]`.

Recommended bootstrap configuration:

```yaml
utility:
  quality_weight: 0.60
  reuse_weight: 0.25
  transfer_weight: 0.15
```

These numbers are **[DEFAULT]**, not research claims.

They MUST be selected/frozen using validation experiments before final test evaluation.

To prevent divide-by-zero:

```text
reuse_success_rate =
    (successful_reuse_count + 1)
    /
    (successful_reuse_count + failed_reuse_count + 2)
```

A Bayesian-smoothed rate is recommended because new items otherwise have undefined reuse utility.

---

# 17. Consolidation

Consolidation reduces redundant memory while preserving provenance.

```python
class Consolidator(Protocol):
    def consolidate(
        self,
        *,
        memory: Sequence[MemoryItem],
        drafts: Sequence[MemoryDraft],
    ) -> ConsolidationResult:
        ...
```

## 17.1 v1 behavior

**[DEFAULT]**

Implement conservative consolidation only:

- exact code-hash duplicates;
- duplicate memory records referencing the same artifact;
- identical abstraction hashes.

Do not automatically merge behaviorally different heuristics merely because their natural-language descriptions are similar.

This prevents destructive semantic compression before the mechanism is validated.

---

## 17.2 semantic consolidation

**[FUTURE / ABLATION]**

Embedding or LLM-based semantic merging MAY later merge redundant insights.

Any merge MUST preserve:

- all source memory IDs;
- all source task IDs;
- all artifact IDs;
- the consolidation event;
- the new derived memory ID.

---

# 18. Eviction

Eviction is deliberate and event-logged.

```python
class EvictionPolicy(Protocol):
    def choose(
        self,
        *,
        active_memory: Sequence[MemoryItem],
        target_count: int,
        context: EvictionContext,
    ) -> Sequence[str]:
        ...
```

Protected items MUST NOT be returned by eviction unless the experiment explicitly defines a capacity violation resolution policy.

---

## 18.1 Required policies

### `naive_overwrite`

Required baseline.

Recommended deterministic ordering:

```text
1. unprotected only
2. lowest source validation score first
3. oldest creation time as tie-breaker
4. memory_id lexical order as final deterministic tie-breaker
```

No utility-based protection.

---

### `fifo`

Optional diagnostic baseline.

```text
oldest unprotected memory first
```

---

### `fixed_quota`

Optional replay-like baseline.

Each task receives a quota of active items.

When a task exceeds quota, evict within that task.

---

### `utility_weighted_retention`

Full managed-memory policy.

Evict the lowest normalized utility among unprotected items.

Tie-breakers:

```text
1. lower utility
2. lower novelty
3. older last-successful-reuse time
4. older creation time
5. lexical memory_id
```

All tie-breakers MUST be deterministic.

---

# 19. Retriever Architecture

The Retriever MUST be independent of the Archivist.

```python
class Retriever(Protocol):
    def retrieve(
        self,
        *,
        query: "RetrievalQuery",
        memory: "MemorySnapshot",
        budget: "RetrievalBudget",
        mode: Literal[
            "pre_learning_probe",
            "search_seed",
            "retention_probe",
            "diagnostic",
        ],
    ) -> "RetrievalResult":
        ...
```

The Retriever MUST NOT mutate memory.

Retrieval counters MUST be updated through a separate event/update path after retrieval, and MUST be disabled in read-only probes if such counters influence future behavior.

### Critical rule

If `retrieval_count` affects future utility or eviction, then read-only probes MUST NOT increment it in the learner state.

Probe retrieval MAY be logged in the experiment event stream separately.

---

# 20. `RetrievalQuery`

```python
@dataclass(frozen=True)
class RetrievalQuery:
    query_id: str
    task_id: str

    problem_family: str
    formulation: str
    heuristic_interface: str
    problem_size: int | None
    distribution: str | None

    heuristic_type: str | None

    search_stage: Literal[
        "pre_learning",
        "initialization",
        "generation",
        "retention",
        "diagnostic",
    ]

    search_context: Mapping[str, JsonValue]
    semantic_text: str | None

    schema_version: int = 1
```

The query MUST be reconstructable from logged inputs.

---

# 21. `RetrievalBudget`

```python
@dataclass(frozen=True)
class RetrievalBudget:
    top_k: int
    max_context_tokens: int | None
    max_artifacts: int | None
```

Memory capacity `C`, retrieval `top_k`, and active context budget MUST be logged separately.

---

# 22. Retriever v0

Retriever v0 is the required initial retriever for isolatable experiments.

It MUST NOT require:

- embeddings;
- ANN;
- vector DB;
- LLM reranking.

---

## 22.1 Stage 1 — hard compatibility filter

For direct-execution modes:

```text
pre_learning_probe
retention_probe
```

candidate items MUST satisfy:

```text
item.active == True
item.applicability.heuristic_interface == query.heuristic_interface
```

Additional hard filters MAY include:

- objective sense;
- formulation constraints known to make execution invalid.

---

## 22.2 Stage 2 — structural similarity

Define a deterministic structural similarity in `[0,1]`.

**[DEFAULT]**

```text
s_family       = 1 if same problem family else 0
s_formulation  = 1 if same formulation else 0
s_interface    = 1 if same heuristic interface else 0
s_distribution = 1 if same distribution else 0.5 if unspecified else 0

s_size =
    1 - min(
        abs(log1p(q_size) - log1p(m_size)) / size_scale,
        1
    )
```

If size is unavailable, set `s_size = 0.5`.

Bootstrap weights:

```yaml
structural_weights:
  family: 0.25
  formulation: 0.20
  interface: 0.25
  distribution: 0.10
  size: 0.20
```

Weights MUST sum to `1`.

These are **[DEFAULT]** and **[VALIDATE]**.

For a direct-execution query, interface mismatch should already have been filtered out.

---

## 22.3 Stage 3 — utility normalization

Raw utility values are normalized **within the filtered candidate pool**.

Recommended min-max normalization:

```text
if max_u == min_u:
    normalized_u = 0.5
else:
    normalized_u = (u - min_u) / (max_u - min_u)
```

This avoids requiring a globally calibrated utility range.

---

## 22.4 Final v0 score

```text
score(q, m_i) =
    alpha * structural_similarity(q, m_i)
  + beta  * normalized_utility(m_i)
```

Bootstrap:

```yaml
alpha: 0.70
beta: 0.30
```

These values are **[DEFAULT]** and MUST be treated as **[VALIDATE]** before final evaluation.

Tie-break:

```text
1. higher final score
2. higher structural similarity
3. higher utility
4. newer successful reuse
5. lexical memory_id
```

---

## 22.5 Retrieval result

```python
@dataclass(frozen=True)
class RetrievedItem:
    memory_id: str
    rank: int

    final_score: float
    structural_score: float
    utility_score_normalized: float

    filter_reasons: tuple[str, ...]
    contribution: Literal[
        "executable_skill",
        "semantic_hint",
        "evolution_seed",
    ]


@dataclass(frozen=True)
class RetrievalResult:
    query_id: str
    items: tuple[RetrievedItem, ...]
    candidate_count_before_filter: int
    candidate_count_after_filter: int
    top_k: int
    mode: str
    read_only: bool
```

Every retrieval event MUST persist this diagnostic information.

---

# 23. Full Hybrid Retriever Interface

The target architecture is:

```text
query
  |
  v
structural / metadata filtering
  |
  v
candidate subset
  |
  v
semantic similarity
  |
  v
utility-aware reranking
  |
  v
Top-k
```

The module boundary MUST support later insertion of:

```python
class SemanticMatcher(Protocol):
    def score(
        self,
        query_text: str,
        memory_abstraction: KnowledgeAbstraction,
    ) -> float:
        ...
```

The initial implementation SHOULD leave this component disabled:

```yaml
semantic_matcher:
  enabled: false
```

This allows Retriever v0 and hybrid Retriever to share the same public API.

---

# 24. Generator Adapter

The generator should wrap HeurAgenix-style heuristic generation rather than duplicating the framework's entire codebase.

```python
class GeneratorAdapter(Protocol):
    def initialize_population(
        self,
        *,
        task: TaskSpec,
        seeds: Sequence[HeuristicArtifact],
        context: GenerationContext,
    ) -> "Population":
        ...

    def generate(
        self,
        *,
        task: TaskSpec,
        population: "Population",
        context: GenerationContext,
    ) -> Sequence[GeneratedCandidate]:
        ...
```

---

## 24.1 Hard budget enforcement

Budget enforcement MUST live outside the LLM client.

```python
@dataclass
class SearchBudget:
    max_candidate_evaluations: int
    max_llm_calls: int | None
    max_total_tokens: int | None
    max_generations: int | None
    max_wallclock_seconds: float | None
```

Primary matched experimental budget SHOULD use candidate evaluations.

The runner MUST stop before exceeding the configured hard limit.

An over-budget LLM call or evaluation MUST NOT be started.

---

## 24.2 LLM call record

Every call MUST log:

```python
@dataclass(frozen=True)
class LLMCallRecord:
    call_id: str
    run_id: str
    task_id: str
    role: str

    provider: str
    model_id: str
    model_version: str | None

    temperature: float
    seed: int | None

    prompt_path: str
    prompt_sha256: str

    response_path: str
    response_sha256: str

    input_tokens: int | None
    output_tokens: int | None

    started_at: str
    completed_at: str
    runtime_seconds: float
```

---

# 25. Candidate Evaluator

LLM-generated code MUST run in an isolated subprocess.

Never execute generated heuristic code with `exec()` in the main experiment process.

---

## 25.1 `Evaluator` interface

```python
class Evaluator(Protocol):
    def evaluate(
        self,
        *,
        artifact: HeuristicArtifact,
        task: TaskSpec,
        split: str,
        instance_ids: Sequence[str],
        read_only_probe: bool,
    ) -> CandidateEvaluation:
        ...
```

---

## 25.2 Subprocess isolation

Required controls:

- dedicated temporary working directory;
- subprocess timeout;
- kill process tree on timeout;
- clean environment variables;
- no inherited secrets/API keys;
- stdout/stderr capture;
- output-size cap;
- deterministic instance input;
- explicit entrypoint contract.

Recommended primary experiment environment:

```text
Linux
```

so CPU / memory resource limits can be enforced reliably.

Container isolation MAY replace process-level limits if configured consistently across all methods.

---

## 25.3 Failure semantics

A candidate may fail through:

```text
syntax_error
import_error
interface_error
runtime_error
timeout
invalid_solution
non_finite_objective
resource_limit
```

Failures MUST be recorded, not silently dropped.

The experiment config MUST define candidate fitness treatment for failures.

**[DEFAULT]**

```text
failed candidate -> worst score for selection
```

Raw failure type remains available for diagnostics and potential failure-warning memory.

---

# 26. Task Adapter Contract

```python
class TaskAdapter(Protocol):
    @property
    def spec(self) -> TaskSpec: ...

    def load_instance(self, instance_id: str): ...

    def validate_heuristic_interface(
        self,
        artifact: HeuristicArtifact,
    ) -> None:
        ...

    def run_heuristic(
        self,
        artifact_path: str,
        instance_id: str,
    ) -> float:
        ...

    def objective_to_score(
        self,
        objective: float,
        reference: float,
    ) -> tuple[float, float]:
        # Return (reference_gap, higher_is_better_score).
        ...
```

Each heuristic interface MUST have a documented function signature.

Example concept:

```python
def select_next_node(
    current_node: int,
    unvisited: Sequence[int],
    distance_matrix: np.ndarray,
    state: Mapping[str, Any],
) -> int:
    ...
```

The exact signature MUST be frozen per adapter version.

Changing the signature requires a new `heuristic_interface` identifier.

---

# 27. Compatibility Service

Executable compatibility and semantic relatedness MUST be separate concepts.

```python
@dataclass(frozen=True)
class CompatibilityResult:
    executable: bool
    same_family: bool
    same_formulation: bool
    structural_relation: str
    reasons: tuple[str, ...]
```

A TSP heuristic may be directly executable across TSP sizes.

A TSP heuristic is not automatically executable on CVRP.

For incompatible problem-family transitions:

- zero-shot direct-execution FWT is `N/A`;
- transfer SHOULD be measured through adaptation efficiency;
- semantic knowledge MAY later be used to condition generation.

The implementation MUST NOT assign artificial zero-shot scores to incompatible interfaces.

---

# 28. Continual Experimental Conditions

The runner MUST support conditions as explicit configs, not scattered `if` statements.

```python
class ConditionKind(str, Enum):
    ISOLATED = "isolated"
    POPULATION_CARRYOVER = "population_carryover"
    NAIVE_PERSISTENT_MEMORY = "naive_persistent_memory"
    MANAGED_ARCHIVIST = "managed_archivist"
```

---

## 28.1 Isolated baseline

```yaml
memory:
  enabled: false

population_carryover:
  enabled: false
```

Each task starts independently.

No stream state influences learning.

Retention probes for this condition are not interpreted as continual retention unless a separate frozen task-indexed library baseline is explicitly defined.

---

## 28.2 Population carryover

```yaml
memory:
  enabled: false

population_carryover:
  enabled: true
```

After task `Tk`:

```text
final population P*k
      |
      v
initial population P{k+1,0}
```

No persistent external memory.

No Archivist.

No Retriever.

Retention probes evaluate the currently available population-derived competence under the protocol defined for this condition, without restarting search.

---

## 28.3 Naive persistent memory

```yaml
memory:
  enabled: true
  manager: naive
  bounded: true
  protection: none
  distillation: minimal_or_disabled
  eviction: naive_overwrite

retriever:
  type: v0
```

This is a failure-mode baseline, not the full Archivist.

Memory capacity MUST match the managed condition when used for RQ2 comparison.

---

## 28.4 Managed Archivist

```yaml
memory:
  enabled: true
  manager: archivist
  bounded: true
  admission: multi_signal
  protection: task_anchor
  consolidation: conservative
  eviction: utility_weighted_retention

retriever:
  type: v0
```

The full hybrid Retriever may replace `v0` only as a later controlled change.

---

# 29. Canonical Continual Runner

```python
def run_stream(spec: ExperimentSpec) -> RunResult:
    state = initialize_state(spec)

    for k, task in enumerate(spec.stream.tasks):

        # A. Pre-learning probe
        z_k = probe_runner.pre_learning(
            task=task,
            state=state,
            read_only=True,
        )

        # B. Learn/search current task
        learning_result = learner.learn_task(
            task=task,
            state=state,
            budget=spec.search_budget,
        )

        state = learning_result.updated_state

        # C. Retention probe
        row = probe_runner.retention(
            seen_tasks=spec.stream.tasks[:k + 1],
            state=state,
            read_only=True,
        )

        metrics_store.write_performance_row(k, row)
        checkpoint_manager.commit_task_boundary(
            task_index=k,
            state=state,
        )

    return finalize_run(state)
```

The implementation MAY differ, but the stage ordering MUST NOT.

---

# 30. Stage A — Pre-Learning Probe

Purpose: measure competence available before learning the current task.

## 30.1 Required flags

```python
ProbeContext(
    allow_generation=False,
    allow_evolution=False,
    allow_memory_write=False,
    allow_memory_update=False,
    update_retrieval_statistics=False,
    expose_test_results_to_learner=False,
)
```

## 30.2 Procedure

```text
Tk
 |
 v
build retrieval query from Tk
 |
 v
retrieve current retained competence
 |
 v
select directly executable artifact(s)
 |
 v
execute on probe evaluation instances
 |
 v
Zk
```

For final evaluation, `Zk` is evaluated on the designated test split according to the frozen protocol, but the result remains experiment-only.

The learner never receives `Zk`.

---

# 31. Stage B — Learn/Search Current Task

This is the only normal learning stage.

Procedure:

```text
1. build search initialization
2. optionally retrieve search seeds/hints
3. initialize population
4. generate candidates
5. train/smoke evaluation as required
6. validation candidate evaluation / selection
7. update population
8. record search curve S_k(b)
9. add evidence to working buffer
10. Archivist processes eligible experience
11. enforce memory capacity
12. commit memory state Mk
```

Only train and validation evidence may influence learning.

Test split results MUST NOT be queried here.

---

# 32. Stage C — Retention Probe

After learning `Tk`, evaluate:

```text
T1 ... Tk
```

using the current retained state `Mk`.

Required flags:

```python
ProbeContext(
    allow_generation=False,
    allow_evolution=False,
    allow_memory_write=False,
    allow_memory_update=False,
    update_retrieval_statistics=False,
    expose_test_results_to_learner=False,
)
```

The probe MUST use the same deployed retrieval/selection policy available to the continual system, except learner-state updates are disabled.

Output:

```text
A[k,1], A[k,2], ..., A[k,k]
```

---

# 33. Performance Matrix

```python
class PerformanceMatrix:
    def set(self, k: int, j: int, score: float) -> None: ...
    def get(self, k: int, j: int) -> float: ...
    def row(self, k: int) -> Sequence[float]: ...
    def to_numpy(self) -> np.ndarray: ...
```

Invariant:

```text
A[k,j] is defined only for j <= k
```

The matrix MUST be written incrementally after every task so a crashed run retains completed rows.

---

# 34. Optimization Score

For minimization:

```text
gap =
    (candidate - reference)
    /
    max(abs(reference), epsilon)
```

For maximization:

```text
gap =
    (reference - candidate)
    /
    max(abs(reference), epsilon)
```

Continual score:

```text
S = -gap
```

Required outputs:

- raw objective;
- reference objective;
- raw gap;
- percentage gap;
- continual score.

`epsilon` MUST be fixed globally in configuration.

**[DEFAULT]**

```yaml
metrics:
  reference_epsilon: 1.0e-12
```

---

# 35. Continual Metrics

All primary metric functions MUST operate from persisted performance matrices rather than ad hoc in-memory results.

---

## 35.1 Final average performance

```text
AP_K = mean_j A[K,j]
```

Higher is better.

---

## 35.2 Backward transfer

```text
BWT_K =
    mean_{j=1..K-1} (
        A[K,j] - A[j,j]
    )
```

Interpretation:

```text
BWT > 0  positive backward transfer
BWT ~ 0  approximate preservation
BWT < 0  negative backward transfer
```

---

## 35.3 Average forgetting

For task `j`:

```text
best_j = max_{l=j..K-1} A[l,j]

F_j = best_j - A[K,j]
```

Then:

```text
F_K = mean_{j=1..K-1} F_j
```

Lower is better.

---

## 35.4 Worst-case forgetting

```text
F_worst = max_j F_j
```

---

## 35.5 Zero-shot forward transfer

For interface-compatible tasks:

```text
FWT_0 =
    mean_{k=2..K} (
        Z_k - B_k
    )
```

where:

- `Z_k` = continual pre-learning score;
- `B_k` = matched cold-start pre-learning baseline.

For incompatible executable interfaces, mark the term as `N/A`.

Do not substitute `0`.

---

# 36. Adaptation Efficiency

During learning, record:

```text
S_k(b)
```

at fixed budget checkpoints.

Primary budget axis:

```text
candidate evaluations
```

Other tracked axes:

- generations;
- LLM calls;
- cumulative input/output tokens;
- wall-clock time.

---

## 36.1 Checkpoints

**[DEFAULT]**

For maximum evaluation budget `B`, record at:

```text
0%, 10%, 20%, ..., 100%
```

or at the closest completed candidate evaluation count.

The exact checkpoint grid MUST be identical across compared methods.

---

## 36.2 Adaptation Curve Area

Use numerical trapezoidal integration over fixed checkpoints:

```text
ACA_k(B) =
    (1/B) * integral_0^B S_k(b) db
```

Transfer gain:

```text
Delta_ACA_k =
    ACA_continual_k - ACA_cold_k
```

Aggregate over applicable future tasks.

---

## 36.3 Fixed-budget gain

```text
FBG_k(B) =
    S_continual_k(B) - S_cold_k(B)
```

---

## 36.4 Budget-to-target

```text
BTT_k =
    min b such that S_k(b) >= tau_k
```

`tau_k` MUST be frozen using validation/domain criteria before final testing.

If target is not reached within budget, mark the observation as censored.

---

# 37. Retrieval Diagnostics

Retrieval diagnostics explain mechanism but do not replace end-to-end performance.

---

## 37.1 Validation relevance matrix

Where feasible, construct validation-only relevance:

```text
r[i,j] =
    Utility(memory_i, task_j, validation_j)
```

Test data MUST NOT be used.

Persist:

```python
@dataclass(frozen=True)
class ValidationRelevance:
    memory_id: str
    task_id: str
    score: float
    evaluation_method: str
```

---

## 37.2 Recall@k

Report when relevant-item labels/thresholds are defined on validation data.

---

## 37.3 NDCG@k

Use validation relevance grades.

---

## 37.4 Competence coverage

For each seen task:

```text
Coverage[k,j] = 1
```

if current active memory contains at least one item whose validation utility for `Tj` exceeds the frozen competence threshold.

Threshold is **[VALIDATE]**.

---

## 37.5 Validation-oracle retrieval

Diagnostic only.

Oracle selects top-k memories using validation relevance, then actual and oracle-selected competence are evaluated on the same test instances.

```text
RetrievalRegret =
    A_oracle - A_actual
```

The oracle MUST NOT influence learning or deployment behavior.

---

# 38. Controlled Memory-Pollution Experiment

Required diagnostic capability.

Procedure:

```text
1. choose task Tj
2. identify retained useful memory item(s)
3. pin them so they cannot be evicted
4. progressively add distractor memories
5. keep retrieval top-k fixed
6. keep active context budget fixed
7. query Tj repeatedly in read-only mode
8. record Recall@k / NDCG@k / end-to-end performance
```

This requires a `protected_manual_experiment` protection state.

The pollution driver MUST be separate from the normal learning runner.

---

# 39. Event Model

Every scientifically meaningful state transition MUST emit an event.

Recommended event envelope:

```python
@dataclass(frozen=True)
class Event:
    event_id: str
    run_id: str
    sequence_number: int

    event_type: str
    task_id: str | None
    task_index: int | None

    timestamp: str

    payload: Mapping[str, JsonValue]
    schema_version: int = 1
```

Sequence numbers MUST be monotonically increasing within a run.

---

# 40. Required Event Types

At minimum:

```text
RunStarted
RunResumed
RunCompleted
RunFailed

TaskStarted
TaskCompleted

PreLearningProbeStarted
PreLearningProbeCompleted

SearchStarted
SearchBudgetCheckpoint
SearchCompleted

LLMCallStarted
LLMCallCompleted
LLMCallFailed

CandidateGenerated
CandidateEvaluationCompleted
CandidateEvaluationFailed
PopulationUpdated

WorkingBufferItemAdded
WorkingBufferCleared

ArchivistTransactionStarted
ArchivistCandidateRejected
MemoryPromoted
MemoryMetadataUpdated
MemoryProtected
MemoryProtectionRemoved
MemoryConsolidated
MemoryEvicted
ArchivistTransactionCompleted
ArchivistTransactionFailed

RetrievalStarted
RetrievalCompleted
RetrievedItemUsed
ReuseOutcomeObserved

RetentionProbeStarted
RetentionProbeTaskCompleted
RetentionProbeCompleted

PerformanceMatrixCellWritten
MetricsComputed

CheckpointCreated
CheckpointVerified
```

Every event type SHOULD have a typed payload model.

---

# 41. Read-Only Probe Isolation

This is a hard research integrity requirement.

During probes, the following MUST NOT change:

- active memory set;
- memory utility;
- protection status;
- eviction order;
- retrieval counters used by future learner behavior;
- working population;
- working buffer;
- generator state;
- curriculum;
- hyperparameters.

The easiest implementation is:

```python
with state.read_only_view() as probe_state:
    result = probe(...)
```

followed by a state-hash assertion.

Example:

```python
before = state.behavioral_hash()
probe(...)
after = state.behavioral_hash()

assert before == after
```

Every integration test MUST verify this.

---

# 42. Behavioral State Hash

Compute a hash over learner-affecting state:

```text
active memory IDs + active memory versions
protection states
utility values
population artifact IDs
generator persistent state
retriever learned state (if any)
```

Logs/events are excluded.

Read-only probes MUST preserve the behavioral hash.

---

# 43. Checkpointing

Create a checkpoint after each completed task.

A checkpoint contains:

```text
resolved experiment config
task index
completed task IDs
active memory snapshot
memory DB transaction/version
population state
working-buffer cleared state
budget accounting
performance matrix rows completed
event sequence number
artifact checksums
random generator states
```

---

## 43.1 Resume contract

On resume:

1. locate latest committed task-boundary checkpoint;
2. verify config hash;
3. verify dataset manifest hashes;
4. verify artifact hashes;
5. restore random states;
6. restore memory;
7. restore population if relevant;
8. restore budget accounting;
9. verify performance matrix;
10. resume from next task.

A partially completed task SHOULD be restarted from its task-start checkpoint unless generation-level resume has been explicitly implemented and tested.

This simplifies reproducibility.

---

# 44. Reproducibility Manifest

Every run MUST produce:

```json
{
  "run_id": "...",
  "git_commit": "...",
  "dirty_worktree": false,
  "python_version": "...",
  "platform": "...",

  "experiment_config_sha256": "...",
  "stream_config_sha256": "...",

  "dataset_manifests": [],
  "reference_manifests": [],

  "random_seeds": {},

  "generator": {
    "provider": "...",
    "model_id": "...",
    "temperature": 0.0
  },

  "archivist": {},
  "retriever": {},

  "memory_capacity": 0,
  "retrieval_top_k": 0,

  "search_budget": {},
  "stopping_conditions": {},

  "started_at": "...",
  "completed_at": null
}
```

The manifest MUST be immutable after run completion except for a final completion record/hash.

---

# 45. Configuration Model

All experiment behavior MUST be resolved from version-controlled config plus explicit CLI overrides.

Example:

```yaml
experiment:
  name: tsp_scale_archivist_v1
  condition: managed_archivist
  seed: 42

stream:
  config: configs/streams/tsp_size_ascending.yaml

search:
  primary_budget_axis: candidate_evaluations
  max_candidate_evaluations_per_task: 200
  max_llm_calls_per_task: 100
  max_generations: 20

generator:
  adapter: heuragenix
  model_id: ${CMHH_GENERATOR_MODEL}
  temperature: 0.7

memory:
  enabled: true
  capacity_items: 50

  admission:
    policy: multi_signal
    max_elites: 3
    max_improvement_episodes: 3
    max_failure_warnings: 2

  protection:
    policy: task_anchor
    anchors_per_task: 1

  consolidation:
    policy: conservative

  eviction:
    policy: utility_weighted_retention

retriever:
  type: v0
  top_k: 5
  alpha: 0.70
  beta: 0.30

distillation:
  backend: local_llm
  model_id: ${CMHH_ARCHIVIST_MODEL}
  temperature: 0.0
  fallback_enabled: false

evaluation:
  timeout_seconds_per_instance: 5
  reference_epsilon: 1.0e-12

logging:
  save_prompts: true
  save_responses: true
  save_memory_snapshots: true
  event_format: jsonl
```

All `${...}` substitutions MUST be resolved before execution and the resolved config MUST be stored.

Secrets MUST NOT be persisted in resolved configs.

---

# 46. Config Validation Rules

Startup MUST fail before any expensive work if:

- memory is enabled but capacity `< 1`;
- `top_k > capacity` for a bounded memory condition, unless empty-memory startup is explicitly handled;
- retriever weights do not sum approximately to `1`;
- task interface is unregistered;
- dataset manifest missing;
- test and train instance IDs overlap;
- validation and test instance IDs overlap;
- reference records missing for required test/validation instances;
- budget is non-positive;
- managed condition has no Archivist policy;
- naive condition accidentally enables protection;
- probe config enables writes;
- the same output run directory already contains a different config hash.

---

# 47. Train / Validation / Test Isolation

## Train

Allowed:

- search/generation;
- candidate execution;
- heuristic discovery.

## Validation

Allowed:

- candidate selection;
- memory admission decisions;
- utility computation;
- retrieval hyperparameter tuning;
- memory capacity tuning;
- competence threshold tuning;
- curriculum pilot decisions.

## Test

Allowed:

- final performance measurement;
- pre-learning probe;
- retention probe;
- final diagnostic comparisons using frozen mechanisms.

Forbidden:

- memory admission;
- utility update;
- retriever tuning;
- threshold tuning;
- curriculum selection;
- choosing capacity;
- choosing top-k;
- changing prompts;
- changing generator hyperparameters.

---

# 48. Reference Pipeline

CLI:

```bash
python -m cmhh.cli generate-references \
  --stream configs/streams/tsp_size_ascending.yaml \
  --splits validation test \
  --solver-config configs/solvers/concorde.yaml
```

Required behavior:

- per-instance status file;
- skip verified completed references;
- retry failed instances only when requested;
- write objective and solver status atomically;
- verify input checksum;
- support dry-run;
- produce summary manifest.

Train exact references are not required unless a specific experiment needs them.

---

# 49. Dataset Generation CLI

```bash
python -m cmhh.cli generate-data \
  --stream configs/streams/tsp_size_ascending.yaml \
  --seed 1234
```

Required behavior:

- deterministic;
- manifest before/after verification;
- fixed split sizes;
- no overlapping instance IDs;
- checksums;
- refusal to overwrite changed data unless explicitly forced.

---

# 50. Experiment CLI

Recommended:

```bash
python -m cmhh.cli run \
  --experiment configs/experiments/archivist_tsp.yaml
```

Useful commands:

```bash
python -m cmhh.cli validate-config ...
python -m cmhh.cli run ...
python -m cmhh.cli resume --run-id ...
python -m cmhh.cli compute-metrics --run-id ...
python -m cmhh.cli audit-run --run-id ...
python -m cmhh.cli export-results --run-id ...
```

---

# 51. Statistical Execution Plan

Primary comparisons SHOULD use paired runs.

Practical target:

```text
n >= 5 independent seeds
```

where computationally feasible.

At minimum, the code MUST support arbitrary seed lists:

```yaml
seeds: [11, 22, 33, 44, 55]
```

Comparison pairing key:

```text
(stream_id, dataset_manifest_hash, seed)
```

A run missing its paired counterpart SHOULD be flagged before aggregate statistics.

---

# 52. Metrics Output Contract

Each run MUST export machine-readable metrics:

```json
{
  "run_id": "...",
  "AP_K": 0.0,
  "BWT_K": 0.0,
  "average_forgetting": 0.0,
  "worst_case_forgetting": 0.0,
  "FWT_0": null,
  "delta_ACA": null,
  "fixed_budget_gain": {},
  "budget_to_target": {},
  "memory": {
    "final_items": 0,
    "serialized_bytes": 0,
    "stored_tokens": 0
  },
  "cost": {
    "candidate_evaluations": 0,
    "llm_calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "wallclock_seconds": 0.0
  }
}
```

Aggregate analysis MUST compute:

- mean;
- standard deviation;
- paired method difference;
- confidence interval for paired difference.

---

# 53. Memory Accounting

For every task boundary, log:

```text
active item count
inactive/evicted historical item count
serialized active bytes
estimated active stored tokens
number of executable artifacts
number of abstraction records
number of episode refs
retrieval context tokens
```

`C` is measured in **active persistent memory items** for primary experiments.

The additional size measures are diagnostics.

---

# 54. Retrieval Context Construction

Retrieved items are converted to generator context through a dedicated adapter.

```python
class RetrievalContextBuilder(Protocol):
    def build(
        self,
        *,
        result: RetrievalResult,
        mode: str,
        max_tokens: int,
    ) -> RetrievalContext:
        ...
```

The builder MUST log:

- memory IDs included;
- order;
- content type;
- token estimate;
- omitted memories due to context budget.

This is required to distinguish retrieval success from context truncation.

---

# 55. Search Initialization from Memory

The generator may receive:

1. executable seed heuristics;
2. semantic hints;
3. warnings;
4. adaptation constraints.

For Retriever v0 on the TSP size stream, the primary reusable form SHOULD be executable seeds plus associated abstraction.

No test performance may influence which seed is chosen.

---

# 56. Reuse Outcome Tracking

During Stage B only, a retrieved memory can receive reuse evidence.

```python
@dataclass(frozen=True)
class ReuseOutcome:
    reuse_event_id: str
    memory_id: str
    target_task_id: str

    baseline_validation_score: float | None
    post_reuse_validation_score: float | None
    validation_delta: float | None

    success: bool | None
    measurement_method: str
```

The outcome MUST be based on train/validation evidence.

Probe/test outcomes MUST NOT update reusable-memory utility.

---

# 57. Population Carryover Contract

```python
class PopulationCarryover:
    def export_final_population(
        self,
        population: Population,
    ) -> PopulationSnapshot:
        ...

    def initialize_next_task(
        self,
        snapshot: PopulationSnapshot,
        target_task: TaskSpec,
    ) -> Population:
        ...
```

Carryover requires executable interface compatibility.

If task interfaces differ:

- incompatible members are rejected;
- the condition MUST log effective carried population size;
- no hidden conversion is allowed unless explicitly defined as a separate adaptation mechanism.

---

# 58. Failure Recovery

## 58.1 LLM API failure

- retry policy configurable;
- retry attempts counted in logs;
- billing/token accounting preserved where known;
- hard budget remains enforced;
- after retry limit, task/run fails explicitly.

## 58.2 Candidate evaluator crash

- mark candidate failed;
- preserve stderr;
- continue search if policy allows.

## 58.3 Archivist distillation failure

Preferred fallback hierarchy:

```text
structured local LLM
    |
    failed
    v
deterministic minimal abstraction
```

A large LLM fallback is used only if enabled by experiment config.

The failure path MUST be logged.

## 58.4 Memory-capacity deadlock

Example:

```text
capacity C = 3
protected active items = 4
```

Startup/transaction MUST raise:

```text
MemoryCapacityInvariantError
```

unless the config explicitly defines a protection-overflow policy.

Do not silently evict protected items.

---

# 59. Security and Code Execution

Generated code is untrusted.

The production experiment runner SHOULD:

- disable network access for heuristic subprocesses;
- strip secrets from environment;
- use a non-privileged user;
- enforce timeout;
- cap memory/CPU where platform permits;
- cap stdout/stderr;
- isolate temporary files;
- validate returned solution structure.

Generated code MUST NOT be allowed to modify:

- dataset files;
- memory DB;
- experiment configs;
- event logs;
- reference files.

---

# 60. Unit Test Requirements

Minimum unit tests:

### Data

- deterministic dataset generation;
- checksum mismatch detection;
- split non-overlap;
- reference-gap minimization formula;
- reference-gap maximization formula.

### Tasks

- registry lookup;
- unknown interface rejection;
- compatibility classification.

### Artifacts

- immutable code hash;
- interface validation;
- duplicate artifact detection.

### Memory

- add/get;
- capacity enforcement;
- protected item not evicted;
- naive overwrite order;
- utility eviction order;
- provenance preserved after eviction;
- exact duplicate consolidation.

### Retriever

- hard interface filter;
- structural score deterministic;
- utility min-max normalization;
- tie-breaking deterministic;
- top-k exact size;
- no mutation of memory.

### Metrics

- AP known matrix;
- BWT known matrix;
- average forgetting known matrix;
- worst-case forgetting;
- FWT with N/A terms;
- ACA trapezoidal integration.

### Budgets

- no evaluation beyond hard limit;
- no LLM call beyond hard limit.

---

# 61. Integration Test Requirements

## 61.1 Tiny deterministic stream

Use a toy stream with:

```text
2 tasks
2-3 instances per split
mock generator
deterministic evaluator
small memory capacity
```

Verify full A/B/C lifecycle.

---

## 61.2 Probe read-only test

```text
hash_before
run pre-learning probe
hash_after
assert equal

hash_before
run retention probe
hash_after
assert equal
```

This is a release-blocking test.

---

## 61.3 Resume equivalence

Run:

```text
A. uninterrupted
B. stop after task 1 -> resume
```

For deterministic mock mode, final:

- memory snapshot;
- performance matrix;
- event-semantic outcomes;
- metrics

MUST match.

---

## 61.4 Matched-condition isolation

Run naive vs managed with the same:

- task instances;
- seed;
- generator;
- evaluator budget;
- top-k;
- memory capacity.

Audit MUST report only the intended mechanism differences.

---

# 62. Regression Tests

Maintain golden fixtures for:

- dataset manifests;
- score calculations;
- retrieval ranking;
- memory eviction sequence;
- performance matrix metrics;
- config resolution.

Golden updates require explicit review.

---

# 63. Research Integrity Tests

These tests specifically prevent invalid experimental claims.

## RI-1 Test leakage

Fail if any Stage B event references a test instance.

## RI-2 Probe write leakage

Fail if a memory mutation event occurs between probe start/end.

## RI-3 Future-task leakage

At `Tk`, fail if learner input references any artifact or evidence with source task index `> k`.

## RI-4 Budget mismatch

Aggregate paired conditions and flag if candidate-evaluation budgets differ beyond configured tolerance.

## RI-5 Memory mismatch

For matched bounded-memory comparisons, flag unequal `C`.

## RI-6 Retrieval mismatch

For RQ2 matched conditions, flag unequal `top_k` unless retriever size is the independent variable.

## RI-7 Test-tuned config

Final test runs MUST load a frozen config with:

```yaml
experiment:
  config_status: frozen
```

---

# 64. Acceptance Gates

The project should not proceed to expensive final experiments until each gate passes.

---

## Gate 0 — Experimental foundation

Required:

- task registry works;
- deterministic TSP data;
- manifests/checksums;
- reference generation resumable;
- sandbox evaluator;
- relative gap tests;
- generator adapter with hard budget;
- stream runner resumable;
- performance matrix;
- AP/BWT/FWT plumbing;
- reproducibility manifest.

Pass condition:

```text
same deterministic smoke config -> same non-LLM artifacts and metrics
```

---

## Gate 1 — Sequential baselines

Required:

- isolated baseline;
- population carryover;
- naive persistent memory;
- retention probes after every task;
- no full re-search during retention;
- read-only probe invariant.

Pass condition:

```text
one TSP size stream completes end-to-end
for each condition
```

---

## Gate 2 — Retriever v0

Required:

- explicit RetrievalQuery;
- structural filter;
- deterministic scoring;
- top-k;
- retrieval diagnostics;
- read-only mode.

Pass condition:

```text
retrieval ranking is reproducible
and unit-tested
```

---

## Gate 3 — Full Archivist lifecycle

Required:

- working buffer;
- admission;
- distillation;
- promotion/rejection;
- utility evidence;
- protection;
- conservative consolidation;
- bounded eviction;
- provenance;
- transaction rollback.

Pass condition:

```text
capacity invariant holds after every task
and every active memory item is traceable to evidence
```

---

## Gate 4 — RQ1/RQ2 diagnostic readiness

Required:

- competence coverage;
- Recall@k/NDCG@k where labels available;
- validation oracle retrieval;
- controlled memory-pollution runner;
- memory capacity sweep config.

Pass condition:

```text
a synthetic test can separately demonstrate:
storage loss
vs retrieval failure
vs downstream-use failure
```

---

## Gate 5 — Final experiment readiness

Required:

- validation-frozen hyperparameters;
- frozen task streams;
- frozen splits;
- frozen reference sets;
- paired seed schedule;
- matched budgets;
- final audit command passes;
- no test leakage;
- full reproducibility manifest.

Only after Gate 5 should results be treated as paper-grade final evidence.

---

# 65. Implementation Sequence

Recommended engineering order:

```text
1. core types + config validation
2. task registry
3. deterministic data + references
4. evaluator
5. generator adapter
6. budget manager
7. continual runner without memory
8. performance matrix + metrics
9. population carryover
10. MemoryStore
11. naive persistent memory
12. Retriever v0
13. read-only probe framework
14. working buffer
15. Archivist deterministic admission
16. protection + eviction
17. local-model distillation
18. utility/reuse tracking
19. retrieval diagnostics
20. memory-pollution/oracle diagnostics
21. statistical aggregation
22. final audit tooling
```

Do not implement semantic vector retrieval before the v0 system produces trustworthy continual results.

---

# 66. Recommended Pull-Request Boundaries

A clean implementation can be split into PRs:

```text
PR-01  core models + config validation
PR-02  task registry + TSP adapter
PR-03  deterministic data + manifests
PR-04  reference solver pipeline
PR-05  subprocess evaluator
PR-06  generator / HeurAgenix adapter + budget
PR-07  continual runner + checkpointing
PR-08  performance matrix + metrics
PR-09  population carryover baseline
PR-10  persistent MemoryStore + naive memory
PR-11  Retriever v0
PR-12  read-only probes + integrity tests
PR-13  Archivist admission + working buffer
PR-14  protection + consolidation + eviction
PR-15  distillation backend
PR-16  retrieval / memory diagnostics
PR-17  statistical aggregation + export
PR-18  audit + final reproducibility gates
```

Each PR SHOULD include tests and migration notes if schemas change.

---

# 67. Definition of Done per Component

## Task adapter

Done when:

- train/validation/test load deterministically;
- interface contract documented;
- smoke heuristic executes;
- objective maps to normalized score.

## Evaluator

Done when:

- generated code cannot crash main process;
- timeouts work;
- failure reasons persist;
- reference-gap tests pass.

## Generator

Done when:

- hard budget cannot be exceeded;
- prompts/responses are logged;
- deterministic mock backend exists for tests.

## MemoryStore

Done when:

- persistent;
- transactional;
- versioned;
- bounded;
- snapshot/restorable.

## Retriever

Done when:

- deterministic;
- independent from Archivist;
- diagnostic scores logged;
- read-only behavior verified.

## Archivist

Done when:

- selected experiences are admitted/rejected;
- provenance complete;
- capacity invariant maintained;
- protection respected;
- rollback tested.

## ContinualRunner

Done when:

- A/B/C protocol enforced;
- resume works;
- future-task/test leakage tests pass.

---

# 68. Experimental Parameter Registry

The following parameters MUST have explicit status in config metadata.

```yaml
parameter_registry:

  memory_capacity:
    status: validate

  retrieval_top_k:
    status: validate

  retriever_alpha:
    status: validate

  retriever_beta:
    status: validate

  structural_similarity_weights:
    status: validate

  admission_limits:
    status: validate

  novelty_threshold:
    status: validate

  promotion_threshold:
    status: validate

  utility_weights:
    status: validate

  anchors_per_task:
    status: validate

  archivist_model:
    status: validate

  competence_threshold:
    status: validate

  non_inferiority_margin:
    status: validate

  budget_to_target_thresholds:
    status: validate
```

Final experiment configs MUST resolve every `validate` parameter to a frozen value.

---

# 69. Default-vs-Claim Rule

A default implementation value MUST NOT silently become a paper claim.

Example:

```text
alpha = 0.70
```

means:

> "the bootstrap software default is 0.70"

not:

> "CMHH theoretically requires alpha=0.70."

The paper must report the final frozen value and how it was selected.

---

# 70. Known Architecture Inconsistency Resolved Here

Older notes/pseudocode may show:

```python
archivist.retrieve(...)
```

This implementation MUST NOT preserve that coupling.

The authoritative design is:

```python
memory_snapshot = memory_store.snapshot()

retrieval = retriever.retrieve(
    query=query,
    memory=memory_snapshot,
    budget=retrieval_budget,
    mode=mode,
)

# only during Stage B and only via explicit update path:
reuse_tracker.record(...)
archivist.update_from_reuse_evidence(...)
```

This separation is necessary to independently ablate:

- storage/curation;
- retrieval;
- downstream reuse.

---

# 71. Baseline Fairness Audit

Implement:

```bash
python -m cmhh.cli audit-comparison \
  --run-a <naive_run> \
  --run-b <archivist_run>
```

The audit compares:

- task-stream hash;
- dataset hashes;
- seed;
- generator model/config;
- evaluator version;
- candidate-evaluation budget;
- memory capacity;
- retrieval top-k;
- active context cap;
- reference-set hash.

Output:

```text
PASS: matched
or
FAIL: unmatched fields [...]
```

For paper-grade RQ2 comparisons, this audit MUST pass.

---

# 72. Run Audit

Implement:

```bash
python -m cmhh.cli audit-run --run-id <id>
```

Checks:

```text
[ ] config frozen?
[ ] git commit recorded?
[ ] dataset checksums valid?
[ ] references complete?
[ ] no train/test overlap?
[ ] no validation/test overlap?
[ ] no Stage B test evaluation?
[ ] no probe memory mutation?
[ ] capacity invariant always true?
[ ] future-task leakage absent?
[ ] budgets respected?
[ ] performance matrix complete?
[ ] artifacts hashes valid?
[ ] final memory snapshot valid?
```

Return non-zero exit code on failure.

---

# 73. Logging Volume and Retention

Scientific logs and long-term continual memory are different.

The experiment MAY log all raw traces to disk for reproducibility.

Those logs DO NOT count as persistent learner memory unless the learner can retrieve/use them.

Therefore:

```text
scientific audit storage != learner-accessible memory
```

The implementation MUST make this distinction explicit.

A raw trace stored under `runs/<id>/responses/` but not indexed by MemoryStore is not part of `M_k`.

---

# 74. Model Backends

Use abstract model clients:

```python
class LLMClient(Protocol):
    def complete(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        ...
```

Separate named roles/configurations:

```text
generator_model
archivist_model
optional_archivist_fallback_model
optional_semantic_embedding_model
```

Do not assume they are the same model.

The final run manifest MUST record each independently.

---

# 75. Deterministic Test Backend

Provide:

```python
class MockLLMClient:
    ...
```

with fixture-driven responses.

All CI/integration tests SHOULD use MockLLM.

Live LLM calls MUST NOT be required for core test suite success.

---

# 76. Data and Artifact Versioning

Any change to:

- task instance format;
- heuristic interface;
- memory schema;
- event schema;
- evaluator result schema;

requires a version bump.

Never silently reinterpret historical run artifacts under a new schema.

Migration utilities MAY be added, but original data MUST remain immutable.

---

# 77. Initial TSP End-to-End Reference Workflow

The first paper-quality technical workflow should be:

```text
1. generate TSP-20/50/100/200 data
2. freeze manifests
3. generate validation/test references
4. audit references
5. run isolated baselines
6. run population carryover
7. run naive bounded memory
8. run managed Archivist
9. after every task:
      pre-learning probe was already recorded
      learn/search
      retention probe all seen tasks
10. build A matrix
11. compute AP/BWT/forgetting
12. compute zero-shot FWT where applicable
13. compute adaptation curves
14. run retrieval diagnostics
15. aggregate paired seeds
16. audit all comparisons
```

---

# 78. Phase-Specific Minimal Implementations

## Phase A — H1 sequential behavior

Need:

- isolated;
- population carryover;
- naive persistent memory;
- no full Archivist requirement.

Retriever for naive memory MAY be deterministic v0.

Purpose:

```text
Does sequential continuity produce functional forgetting/interference?
```

---

## Phase B — H2 managed memory

Add:

- admission;
- protection;
- utility retention;
- bounded capacity;
- controlled consolidation;
- retrieval diagnostics.

Purpose:

```text
Does managed memory improve stability
without unacceptable plasticity loss?
```

---

## Phase C — H3 forward transfer

Add complete:

- pre-learning probe;
- adaptation curves;
- cold-start matched baselines;
- FWT0;
- ACA;
- FBG;
- BTT.

---

## Phase D — task order

Keep mechanism fixed and vary only stream order.

Curriculum/order MUST be chosen without final test leakage.

---

# 79. Performance and Scaling Constraints

Retriever v0 MAY scan all active memory items:

```text
O(|M|)
```

This is acceptable for initial bounded-memory experiments.

Do not prematurely add ANN infrastructure.

Instrument:

```text
retrieval latency
memory count
candidate count after filter
context-construction latency
```

A future migration to indexed retrieval should preserve the `Retriever` API.

---

# 80. Memory Snapshot Format

At each task boundary export a human-readable summary:

```json
{
  "snapshot_id": "...",
  "run_id": "...",
  "after_task_id": "...",
  "active_count": 42,
  "capacity": 50,
  "items": [
    {
      "memory_id": "...",
      "artifact_id": "...",
      "origin_task_id": "...",
      "problem_family": "TSP",
      "size_range": [50, 100],
      "utility_score": 0.81,
      "protection_status": "protected_task_anchor",
      "retrieval_count_learning_only": 3
    }
  ]
}
```

Raw test-probe retrieval counts MUST NOT be mixed into learner-affecting retrieval counts.

---

# 81. Retrieval Counter Separation

Maintain at least:

```text
learning_retrieval_count
probe_retrieval_count
diagnostic_retrieval_count
```

Only `learning_retrieval_count` MAY affect memory utility, and only if the configured utility policy uses retrieval frequency.

This prevents evaluation from altering future behavior.

---

# 82. Randomness Control

Record independent seeds for:

```text
dataset_generation_seed
stream_order_seed
generator_sampling_seed
evolutionary_operator_seed
population_selection_seed
evaluation_sampling_seed
archivist_sampling_seed
```

Where the backend does not support deterministic seeding, record that fact explicitly.

Do not pretend full determinism for remote LLM APIs.

Reproducibility means reconstructable conditions and stochastic replication, not necessarily byte-identical remote responses.

---

# 83. Prompt Versioning

Prompts are experiment code.

Store:

```text
prompt_name
prompt_version
prompt_template_sha256
rendered_prompt_sha256
```

Changing a prompt requires a version change or commit change.

Final compared conditions MUST use the same generator prompt unless prompt behavior is the independent variable.

---

# 84. Experiment Immutability

Once a final test run begins, the resolved config should be copied into the run directory and treated as immutable.

If a user attempts resume with changed config:

```text
ResumeConfigMismatchError
```

A new run ID is required.

---

# 85. Error Taxonomy

Define typed errors:

```text
CMHHError
├── ConfigError
├── DatasetIntegrityError
├── ReferenceIntegrityError
├── HeuristicInterfaceError
├── EvaluationError
│   ├── CandidateTimeoutError
│   └── InvalidSolutionError
├── BudgetExceededError
├── MemoryError
│   ├── MemoryCapacityInvariantError
│   ├── MemoryTransactionError
│   └── MemorySchemaError
├── RetrievalError
├── ProbeMutationError
├── CheckpointError
└── ResearchIntegrityError
```

Errors that threaten experimental validity SHOULD fail the run rather than be silently recovered.

---

# 86. Minimal Database Tables

Recommended SQLite tables:

```text
runs
tasks
dataset_manifests
reference_records

heuristic_artifacts
candidate_evaluations
search_episodes

memory_items
memory_item_versions
memory_episode_links

retrieval_events
retrieval_items
reuse_outcomes

events

performance_matrix
adaptation_checkpoints

checkpoints
```

Avoid storing large code/prompt bodies directly in SQLite; store paths + hashes.

---

# 87. Transaction Boundaries

Use DB transactions for:

### candidate evaluation commit

```text
evaluation record + event
```

### Archivist commit

```text
memory additions
memory version updates
protection changes
evictions
events
snapshot pointer
```

### task boundary

```text
performance row
metrics checkpoint
learner snapshot
checkpoint record
TaskCompleted event
```

A process crash must not produce a state where the DB claims a task completed but the corresponding snapshot/performance row is missing.

---

# 88. Observability

Console logs are for humans.

Structured events are the scientific record.

Recommended console format:

```text
[run=abc task=2/4 tsp_100 stage=search]
eval=120/200 gen=11 best_gap=2.31% memory=38/50
```

Never rely on console logs alone for analysis.

---

# 89. Final Result Export

Command:

```bash
python -m cmhh.cli export-results --run-id <id>
```

Output:

```text
final/
├── performance_matrix.csv
├── adaptation_curves.csv
├── continual_metrics.json
├── retrieval_metrics.json
├── memory_accounting.csv
├── cost_accounting.json
├── run_audit.json
└── reproducibility_manifest.json
```

Aggregate multi-seed export SHOULD additionally produce paired comparison tables.

---

# 90. Design Review Checklist Before Coding Full Archivist

The engineer implementing the Archivist should be able to answer:

```text
1. What exact evidence enters the working buffer?
2. What exact evidence can trigger admission?
3. Which decisions use validation only?
4. Which memory fields affect retrieval?
5. Which memory fields affect eviction?
6. Which fields are updated after successful reuse?
7. Which counters exclude probes?
8. How is a protected item represented?
9. How is capacity enforced atomically?
10. How is an evicted item still auditable?
11. How is a memory traced back to code and source episode?
12. How does resume reconstruct identical learner state?
```

If any answer is "whatever the LLM decides", the implementation is not ready.

---

# 91. Design Review Checklist Before Coding Retriever

The engineer should be able to answer:

```text
1. What is the RetrievalQuery schema?
2. What is a hard compatibility constraint?
3. What is only a soft similarity signal?
4. How is utility normalized?
5. What are tie-break rules?
6. What does top-k mean under context limits?
7. What happens when memory is empty?
8. What happens when no executable item survives filtering?
9. Which retrieval events affect future learner behavior?
10. How is retrieval diagnosed independently of downstream performance?
```

---

# 92. Empty and Degenerate Cases

## Empty memory

Return:

```python
RetrievalResult(items=(), ...)
```

No error.

Pre-learning score is obtained from the defined cold/default deployment policy if one exists; otherwise mark no retained competence.

## No compatible executable memory

For zero-shot direct execution:

```text
not applicable / no compatible retained artifact
```

Do not adapt/generate during the probe.

## `top_k > candidate_count`

Return all candidates.

## Equal retrieval scores

Use deterministic tie-break rules.

## All items protected and over capacity

Fail transaction with `MemoryCapacityInvariantError`.

---

# 93. Research-vs-Engineering Decision Table

| Decision | Status |
|---|---|
| Population is distinct from persistent memory | **FIXED** |
| Working buffer before long-term admission | **FIXED** |
| Archivist and Retriever are separate | **FIXED** |
| Memory is bounded in primary memory experiments | **FIXED** |
| Memory item represents artifact + applicability + abstraction + metadata | **FIXED** |
| Forgetting includes retrieval-induced functional forgetting | **FIXED** |
| Retention probe uses no full re-search | **FIXED** |
| Probe/test results do not update learner | **FIXED** |
| Structural filter precedes semantic matching in full Retriever | **FIXED** |
| Retriever v0 may omit embeddings/LLM reranking | **FIXED** |
| SQLite + filesystem persistence | **DEFAULT** |
| Retriever `alpha=0.70`, `beta=0.30` | **DEFAULT + VALIDATE** |
| Structural feature weights | **DEFAULT + VALIDATE** |
| Admission item counts | **DEFAULT + VALIDATE** |
| Utility weights | **DEFAULT + VALIDATE** |
| `anchors_per_task=1` | **DEFAULT + VALIDATE** |
| Exact memory capacity `C` | **VALIDATE** |
| Exact retrieval top-k | **VALIDATE** |
| Exact local Archivist model | **VALIDATE** |
| Semantic embedding model | **FUTURE / VALIDATE** |
| ANN/vector DB | **FUTURE** |
| LLM reranker | **FUTURE / ABLATION** |

---

# 94. Implementation Acceptance Definition

The project is **implementation-ready** when a new research engineer can:

1. clone the repository;
2. install dependencies;
3. generate/fetch deterministic TSP data;
4. verify reference records;
5. run a smoke isolated task;
6. run a tiny sequential stream;
7. inspect memory snapshots;
8. reproduce a deterministic mock run;
9. resume from checkpoint;
10. compute the continual matrix and metrics;
11. audit that probes did not mutate learner state;
12. compare naive and managed memory under matched budgets;
13. trace every reported final score back to:
    - task;
    - instances;
    - heuristic artifact;
    - memory snapshot;
    - retrieval event;
    - evaluation record;
    - config;
    - code commit.

If this traceability is not possible, the system may be a working prototype but is not yet a paper-grade research implementation.

---

# 95. Final System Contract

The completed CMHH implementation must preserve this loop:

```text
                    TASK STREAM
                        |
                        v
              +-------------------+
              | Continual Runner  |
              +---------+---------+
                        |
       +----------------+----------------+
       |                                 |
       v                                 v
 read-only probes                 learning/search
       |                                 |
       |                        +--------+--------+
       |                        | Generator      |
       |                        +--------+--------+
       |                                 |
       |                                 v
       |                        +-----------------+
       |                        | Evaluator       |
       |                        +--------+--------+
       |                                 |
       |                                 v
       |                        +-----------------+
       |                        | Working Buffer  |
       |                        +--------+--------+
       |                                 |
       |                                 v
       |                        +-----------------+
       |                        | Archivist       |
       |                        +--------+--------+
       |                                 |
       +------------+         writes     |
                    |                    v
                    |          +-----------------+
                    +--------->| Long-term Memory|
                               +--------+--------+
                                        ^
                                        |
                               +--------+--------+
                               | Retriever       |
                               +-----------------+
```

The central scientific boundary is:

```text
Archivist decides what survives.

Retriever decides what is accessible now.

Evaluator measures what actually works.

The continual runner prevents evaluation from becoming learning.
```

---

# Appendix A — Bootstrap Configs

## A.1 Naive memory

```yaml
memory:
  enabled: true
  capacity_items: 50
  manager: naive
  admission:
    policy: elite_validation
    max_elites: 3
  protection:
    policy: none
  consolidation:
    policy: exact_duplicate_only
  eviction:
    policy: naive_overwrite

retriever:
  type: v0
  top_k: 5
  alpha: 0.70
  beta: 0.30
```

---

## A.2 Managed Archivist

```yaml
memory:
  enabled: true
  capacity_items: 50
  manager: archivist

  admission:
    policy: multi_signal
    max_elites: 3
    max_improvement_episodes: 3
    max_failure_warnings: 2
    max_transfer_items: 3

  protection:
    policy: task_anchor
    anchors_per_task: 1

  consolidation:
    policy: conservative

  utility:
    quality_weight: 0.60
    reuse_weight: 0.25
    transfer_weight: 0.15

  eviction:
    policy: utility_weighted_retention

retriever:
  type: v0
  top_k: 5
  alpha: 0.70
  beta: 0.30
```

All numeric values in this appendix are bootstrap defaults and must be validation-frozen before final test claims.

---

# Appendix B — Example TSP Stream

```yaml
stream_id: tsp_size_ascending_v1

tasks:
  - task_id: tsp_20_uniform
    config: configs/tasks/tsp_20.yaml

  - task_id: tsp_50_uniform
    config: configs/tasks/tsp_50.yaml

  - task_id: tsp_100_uniform
    config: configs/tasks/tsp_100.yaml

  - task_id: tsp_200_uniform
    config: configs/tasks/tsp_200.yaml
```

---

# Appendix C — Example Event

```json
{
  "event_id": "evt_01...",
  "run_id": "run_01...",
  "sequence_number": 184,
  "event_type": "MemoryPromoted",
  "task_id": "tsp_100_uniform",
  "task_index": 2,
  "timestamp": "2026-08-19T16:00:00Z",
  "payload": {
    "memory_id": "mem_...",
    "artifact_id": "art_...",
    "reasons": [
      "top_validation_elite",
      "novel_size_region"
    ],
    "source_validation_score": -0.0213,
    "protection_status": "unprotected"
  },
  "schema_version": 1
}
```

---

# Appendix D — Example Retrieval Event

```json
{
  "query_id": "qry_...",
  "mode": "search_seed",
  "read_only": false,
  "candidate_count_before_filter": 47,
  "candidate_count_after_filter": 31,
  "top_k": 5,
  "items": [
    {
      "memory_id": "mem_17",
      "rank": 1,
      "final_score": 0.842,
      "structural_score": 0.91,
      "utility_score_normalized": 0.683,
      "contribution": "evolution_seed"
    }
  ]
}
```

---

# Appendix E — Required Final Audit Evidence

Before a result enters a paper table, the following evidence must exist:

```text
result cell
   |
   +--> performance_matrix[k,j]
   |
   +--> evaluation IDs
   |
   +--> heuristic artifact hash
   |
   +--> retrieval event IDs
   |
   +--> memory snapshot ID
   |
   +--> test instance manifest hash
   |
   +--> reference set hash
   |
   +--> resolved config hash
   |
   +--> git commit
```

This audit chain is a first-class requirement of CMHH because the project studies system-level continual competence, not merely final heuristic quality.

---

# Appendix F — Open Decisions That Must Be Frozen Later

The following remain deliberately open in the research design and are therefore configurable in this implementation:

```text
[ ] exact persistent memory capacity values
[ ] exact retrieval top-k
[ ] exact structural feature weights
[ ] alpha / beta retrieval weights
[ ] exact promotion thresholds
[ ] exact novelty threshold
[ ] full utility weights
[ ] task-anchor quota
[ ] local Archivist model
[ ] large-model fallback threshold
[ ] competence coverage threshold
[ ] new-task non-inferiority margin
[ ] budget-to-target thresholds
[ ] semantic embedding model
[ ] semantic consolidation threshold
```

Selection process:

```text
development intuition
      |
      v
validation experiments
      |
      v
freeze config
      |
      v
final test runs
```

No value may be selected after inspecting final test outcomes.

---

# Appendix G — Traceability to Existing CMHH Decisions

This specification operationalizes the following existing project decisions:

- CMHH studies continual competence at the heuristic-system level rather than continual LLM parameter training.
- Working population and persistent memory are distinct.
- Structured memory contains executable competence, applicability descriptors, abstraction, and lifecycle/empirical metadata.
- Long-term memory is bounded in primary experiments.
- Forgetting can be caused by physical memory loss or inability to retrieve/use still-stored knowledge.
- Archivist manages admission, distillation, update, protection, consolidation, capacity, and eviction.
- Retriever is a separate selection/ranking component.
- Full retrieval is structurally filtered before semantic matching and utility reranking.
- Retriever v0 is intentionally simpler and interpretable.
- Pre-learning and retention probes do not run full evolutionary search.
- Probe/test measurements do not update the learner.
- End-to-end continual performance is primary evidence; retrieval/memory metrics are diagnostic.
- Candidate-evaluation budget is the preferred primary search-budget axis; LLM/token/runtime costs are additionally logged.
- Train/validation/test roles are strictly separated.
- Repeated paired runs and uncertainty reporting are required for primary comparisons.
