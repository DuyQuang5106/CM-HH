# CMHH — Engineering Handoff Review & Implementation Audit

**Author:** Senior ML Research Engineer  
**Date:** 2026-08-19  
**Repository:** `CM_HH` (`c:\Users\LENOVO\Projects\CM_HH`)  
**Target Specification Documents:**
1. `CMHH_Research_Specification.md` (Source of Truth for Research Thesis, Hypotheses & Protocol)
2. `CMHH_Archivist_Retriever_Design_Specification.md` (Source of Truth for Archivist & Retriever Design)
3. `CMHH_Implementation_Ready_Specification.md` (Source of Truth for Software Architecture & Contracts)

---

## 1. Current System Map

The existing codebase is located under `HeurAgenix/src/cmhh` and `HeurAgenix/src/problems`. The current system architecture consists of the following components:

```text
                                +---------------------------+
                                |      cli.py Entrypoint    |
                                +-------------+-------------+
                                              |
                                              v
                                +---------------------------+
                                |   StreamRunner (runner)   |
                                +-------------+-------------+
                                              |
      +------------------+--------------------+--------------------+-------------------+
      |                  |                    |                    |                   |
      v                  v                    v                    v                   v
+------------+   +---------------+   +------------------+   +--------------+   +---------------+
|TaskRegistry|   |   Generator   |   |    Evaluator     |   | MemoryStore  |   | Reporting &   |
| (tasks.py) |   | (generator.py)|   |(evaluator/worker)|   | (memory.py)  |   | Diagnostics   |
+------------+   +---------------+   +------------------+   +--------------+   +---------------+
                         |                    |                    |                   |
                         v                    v                    v                   v
                 HeurAgenix Worker    Subprocess Sandbox   retrieve_naive()    performance_matrix
                 (heuragenix_worker)   (evaluator/worker)   (standalone fn)     diagnostics.json
```

### Existing Module Breakdown:
1. **CLI (`cli.py`)**: Entrypoint supporting commands: `validate-config`, `generate-data`, `evaluate-baselines`, `generate-references`, `verify-references`, `run-stream`, `run-isolated`, `evolve-task`, and `audit-run`.
2. **Continual Runner (`runner.py`)**: `StreamRunner` orchestrates the sequential execution over tasks $T_1 \dots T_K$. Handles baseline seeding, candidate ranking on validation, memory writing, checkpointing, and post-task test evaluation.
3. **Memory Store & Naive Retrieval (`memory.py`)**: Simple line-delimited JSON store (`MemoryStore`). Implements `MemoryUnit` and a standalone function `retrieve_naive()` based on heuristic string matching.
4. **Evaluator & Sandbox (`evaluation/evaluator.py`, `evaluation/worker.py`)**: Spawns isolated Python subprocesses with instance/batch timeouts to evaluate heuristic code artifacts against problem instances and Concorde reference solutions.
5. **Generator & HeurAgenix Adapter (`agents/heuragenix_generator.py`, `agents/heuragenix_worker.py`)**: Interfaces with the underlying HeurAgenix evolutionary framework, passing seed heuristics and formatted memory context strings into the prompt.
6. **Task Registry (`tasks.py`, `data/tsp_generator.py`)**: Defines task parameters for Euclidean TSP (`n20`, `n50`, `n100`, `n200`) and generates deterministic TSPLIB data splits (`smoke`, `train`, `validation`, `test`).
7. **Reference Solver Pipeline (`references/concorde.py`, `references/pipeline.py`)**: Interfaces with Concorde exact TSP solver to produce certified optimal tour solutions.
8. **Metrics & Audit (`metrics/continual.py`, `audit.py`, `memory_diagnostics.py`)**: Computes Average Final Performance ($AF$), Backward Transfer ($BWT$), and Forward Transfer ($FWT$), and verifies run directory completeness.

---

## 2. Spec-to-Code Matrix

Each subsystem has been audited against `CMHH_Research_Specification`, `CMHH_Archivist_Retriever_Design_Specification`, and `CMHH_Implementation_Ready_Specification`.

| Component / Requirement | Specification Contract | Existing Code Implementation | Status | Required Action |
|---|---|---|---|---|
| **Task Registry & Contracts** | Immutable `task_id`, `heuristic_interface` (e.g. `tsp_constructive_v1`), splits (`train`, `val`, `test`), reference paths. | `TaskSpec` in `tasks.py` holds task metadata and dataset split paths. | **PARTIAL** | Add explicit `heuristic_interface` contract & version validation. |
| **Data Splits & Manifests** | Fixed splits; dataset generator computes sha256 checksums in `DatasetManifest`. | `data/tsp_generator.py` writes TSPLIB files; `data/manifest.py` generates sha256 checksums. | **DONE** | Maintain current deterministic pipeline. |
| **Reference Generation** | Certified exact optimal reference bounds using Concorde solver. | `references/concorde.py` and `references/pipeline.py` run Concorde and parse tours. | **DONE** | Maintain Concorde verification pipeline. |
| **Evaluator & Sandbox** | Subprocess isolation, per-instance timeout, zero test leakage during search. | `evaluation/evaluator.py` & `worker.py` execute heuristics in isolated sub-processes. | **DONE** | Enforce timeout and exception safety contracts. |
| **Generator Budget Enforcement** | Hard LLM call budget and search generation limits enforced. | `BudgetedLLMClient` tracks call count; `heuragenix_worker.py` respects `max_llm_calls`. | **DONE** | Maintain budget tracking. |
| **Population Carryover** | Final population of $T_{k-1}$ passed to seed $T_k$; bounded size, no external storage. | `runner.py` passes `ranked_population` as seeds when condition is `population_carryover`. | **DONE** | Maintain baseline behavior. |
| **Pre-Learning Probe ($A$)** | Read-only probe evaluating $T_k$ using $M_{k-1}$ before learning $T_k$; no search, no writes. | Missing in `runner.py`. The runner immediately starts search on $T_k$. | **MISSING / CONFLICTING** | Add `_run_pre_learning_probe()` with `read_only=True` invariant. |
| **Retention Probe ($C$)** | Read-only probe evaluating retained competence on $T_1 \dots T_k$ using current memory $M_k$ + `Retriever`. | `runner.py` evaluates static `selected[prior_task_id]` on test set without re-retrieval from $M_k$. | **CONFLICTING** | Refactor probe to re-retrieve from $M_k$ via `Retriever` without re-search. |
| **Performance Matrix ($R_{k,j}$)** | Matrix storing performance on task $j$ after completing task $k$. | `runner.py` records relative gaps in `performance_matrix.csv`. | **PARTIAL** | Ensure matrix cells record probe evaluations rather than static selection. |
| **Continual Learning Metrics** | Computes $AF$, $BWT$, $FWT$, Adaptation Efficiency. | `metrics/continual.py` computes $AF$, $BWT$, and $FWT$. | **DONE** | Add Adaptation Efficiency metric. |
| **Working Buffer** | Bounded short-term storage holding recent trajectories before Archivist admission. | Absent. Candidates go directly from validation ranking into `MemoryStore`. | **MISSING** | Implement `WorkingBuffer` module. |
| **3-Layer Memory Units** | Hybrid logical unit $m_i = (h_i, k_i, z_i, \mu_i)$ (Episodic, Semantic, Procedural). | `MemoryUnit` in `memory.py` uses flat dict with simple `type` ("trajectory") and string `key`. | **PARTIAL** | Upgrade schema to 3-layer `MemoryItem` specification. |
| **Archivist Lifecycle** | Governs Admission, Distillation, Utility Update, Protection, Consolidation, Eviction. | `runner.py` performs raw validation-score eviction inside `_write_naive_memory()`. | **MISSING / CONFLICTING** | Extract `Archivist` into dedicated lifecycle management module. |
| **Retriever Architecture** | Independent component performing Stage 1 structural filter, Stage 2 semantic match, Stage 3 utility rerank. | `retrieve_naive()` function in `memory.py` performs simple string matching. | **CONFLICTING** | Extract independent `Retriever` interface & implement `RetrieverV0`. |
| **Naive Memory Baseline** | Capacity $C=20$, Top-$k=5$, uncurated admission, no protection, no distillation. | Implemented inside `runner.py` via `_uses_naive_memory`. | **PARTIAL** | Refactor to use independent `RetrieverV0` and `MemoryStore`. |
| **Event Sourcing & Audit** | Structured JSONL event log recording all task state transitions and memory operations. | `runner.py` logs events to `events.jsonl`; `audit.py` checks file presence. | **PARTIAL** | Standardize schema versions and add missing retrieval event fields. |
| **Reproducibility & Resume** | Manifest checksum validation, seed tracking, resumable state checkpoints. | `checkpoint.py` saves latest state; `reproducibility.py` logs environment hash. | **DONE** | Ensure RNG stream isolation across subprocesses. |

---

## 3. P0 Research Integrity Blockers

The following issues pose direct threats to research validity, experimental semantics, or paper reproducibility. They must be resolved before generating publication results.

### [P0-1] Missing Pre-Learning Probe ($A$) Protocol
* **Description**: `runner.py` currently initiates heuristic discovery on task $T_k$ immediately, skipping the mandatory read-only Pre-learning Probe on $T_k$ using memory state $M_{k-1}$.
* **Impact**: Without Pre-learning Probe ($A$), zero-shot Forward Transfer ($FWT_0$) cannot be measured dynamically. The system relies on static external `cold_start_scores`, violating the specification requirement.
* **Required Fix**: Implement `_run_pre_learning_probe()` in `StreamRunner` prior to search on $T_k$. Enforce `read_only=True` (no evolutionary search, no memory updates).

### [P0-2] Flawed Retention Probe ($C$) Execution
* **Description**: In `runner.py`, post-task evaluation on prior task $T_j$ executes the static heuristic artifact `selected[prior_task_id]` stored when task $j$ was completed. It does NOT query the current long-term memory $M_k$ using the `Retriever`.
* **Impact**: This measures the static persistence of a single historic code file, NOT the retained competence of the evolving system $M_k$. Functional forgetting induced by memory growth or retrieval interference cannot be detected.
* **Required Fix**: Refactor Retention Probe to query `Retriever.retrieve(query_for_Tj, M_k)` and evaluate the selected executable heuristic on $T_j$'s test split without re-optimization or memory mutation.

### [P0-3] Architectural Coupling of Memory & Retrieval Operations
* **Description**: `runner.py` directly handles memory writing (`_write_naive_memory`) and calls helper function `retrieve_naive()`. The Archivist lifecycle and Retriever are mixed into the runner code.
* **Impact**: Violates research isolation. It prevents independent ablation of memory admission policies versus retrieval ranking strategies (RQ2 & RQ3).
* **Required Fix**: Decouple `Retriever` into a standalone interface and `Archivist` into a distinct lifecycle manager.

### [P0-4] Unenforced Seed Determinism across Subprocess Invocations
* **Description**: Worker subprocesses (`heuragenix_worker.py` and `evaluation/worker.py`) receive a seed argument, but internal Python/NumPy RNG states and LLM client sampling parameters are not fully pinned to a single deterministic RNG stream hierarchy.
* **Impact**: Search trajectories may vary slightly across runs or hardware platforms despite using the same master random seed.
* **Required Fix**: Implement explicit per-generation RNG stream derivation (`master_seed -> task_seed -> gen_seed -> worker_seed`) and enforce deterministic parameters in worker subprocesses.

---

## 4. P1 Implementation Blockers

The following structural gaps block clean implementation of the Full Archivist and Hybrid Retriever.

### [P1-1] Missing Independent `Retriever` Interface
* **Specification Requirement**: `Retriever` MUST be a standalone component with interface `R(q_t, M_t, B) -> S_t`. `Archivist.retrieve(...)` or monolithic store functions are strictly prohibited.
* **Current Status**: `retrieve_naive()` is a standalone helper function in `memory.py`.
* **Required Action**: Create `src/cmhh/retrieval/base.py` defining abstract class `Retriever` and `src/cmhh/retrieval/retriever_v0.py` implementing `RetrieverV0`.

### [P1-2] Absence of `WorkingBuffer`
* **Specification Requirement**: Generated search experience must pass through a bounded `WorkingBuffer` before Archivist evaluation and promotion into long-term memory.
* **Current Status**: Candidate artifacts are evaluated on validation and directly upserted into `MemoryStore`.
* **Required Action**: Implement `WorkingBuffer` class in `src/cmhh/memory/working_buffer.py` to buffer recent trajectories.

### [P1-3] Incomplete 3-Layer `MemoryItem` Schema
* **Specification Requirement**: Logical memory units must explicitly represent procedural artifact $h_i$, applicability descriptor $k_i$, semantic abstraction $z_i$, and lifecycle metadata $\mu_i$.
* **Current Status**: `MemoryUnit` in `memory.py` is a simplified data container with unstructured fields.
* **Required Action**: Refactor `memory.py` to implement the full 3-layer `MemoryItem` dataclass with `schema_version = 1`.

### [P1-4] Lack of Explicit Heuristic Interface Contracts
* **Specification Requirement**: Heuristics must specify explicit interface versions (e.g., `tsp_constructive_v1`) defining exact input signatures, expected return types, and solver state boundary contracts.
* **Current Status**: Compatibility is implicitly assumed by matching the `problem` string ("tsp").
* **Required Action**: Define explicit `heuristic_interface` attributes on `TaskSpec` and `HeuristicArtifact` and enforce validation during candidate generation and evaluation.

---

## 5. Missing Domain Decisions

The following business/domain semantics require explicit contracts before locking final implementation.

### A. Heuristic Execution Semantics
* **Contract Needed**: Explicit signature contract for constructive vs local-search heuristics.
* **Decision**: All initial TSP heuristics operate under contract `tsp_constructive_v1` taking node coordinates and returning a tour permutation list `list[int]`. Solver state remains strictly immutable.

### B. Meaning of "Retained Competence" in Probes
* **Contract Needed**: When Retention Probe runs on prior task $T_j$, does `Retriever` return a single executable or top-$k$?
* **Decision**: In deployment/probe evaluation, `Retriever` returns top-$k$ ranked items. The item with highest combined structural-utility score is executed. No validation tuning or re-search is permitted during probes.

### C. Meaning of "Reuse" & Detailed Event Logging
* **Contract Needed**: Distinguish whether a memory item was merely retrieved versus actually utilized.
* **Decision**: Log 5 discrete lifecycle stages: `retrieved` $\rightarrow$ `included_in_prompt` $\rightarrow$ `used_as_seed` $\rightarrow$ `produced_child` $\rightarrow$ `improved_validation`.

### D. Memory Item Granularity
* **Contract Needed**: Capacity $C$ unit definition.
* **Decision**: Capacity $C$ strictly measures the count of active persistent `MemoryItem` instances in long-term memory (default $C=20$).

### E. Naive Memory Baseline Isolation
* **Contract Needed**: Ensure Naive Memory baseline differs from Managed Archivist ONLY in memory management logic.
* **Decision**: Both conditions share identical task stream, seeds, LLM generator, search budget, evaluator, capacity $C=20$, and top-$k=5$. Naive memory uses uncurated FIFO/score admission without distillation or protection.

### F. Population Carryover Semantics
* **Contract Needed**: Behavior when task instance scale changes (e.g. TSP-20 to TSP-100).
* **Decision**: Carried heuristics must be executable without code modification (`tsp_constructive_v1` is scale-agnostic). Carried population is bounded by search population size $P$.

### G. Archivist Admission Timing
* **Contract Needed**: Transaction timing for Archivist processing.
* **Decision**: End-of-task transaction processing for v1 (Archivist processes `WorkingBuffer` at task completion $T_k$).

### H. Utility Scalar Metric Decomposition
* **Contract Needed**: Tracking component scores within scalar utility.
* **Decision**: Persist individual utility components (`source_validation_score`, `retrieval_count`, `successful_reuse_count`, `transfer_delta`) alongside composite scalar utility $\mu_i$.

### I. Protection Invariant Policy
* **Contract Needed**: Invariant behavior when protected anchor count exceeds capacity $C$.
* **Decision**: If protected items $> C$, the Archivist MUST raise an explicit `CapacityOverflowError` rather than silently evicting protected anchors.

### J. Semantic vs Executable Transfer Policy
* **Contract Needed**: Handling cross-family shifts (e.g. TSP $\to$ CVRP).
* **Decision**: Executable transfer is marked `Incompatible` (`FWT_0 = N/A`). Transfer is evaluated exclusively via Semantic Adaptation Efficiency.

---

## 6. Safe Engineering Defaults

The following engineering choices are adopted as safe bootstrap defaults. They do not alter underlying research claims and are fully configurable:

1. **Initial Task Stream**: `TSP-20 -> TSP-50 -> TSP-100 -> TSP-200` with Euclidean uniform instance distribution.
2. **Archivist Processing Model**: End-of-task transaction batching for initial release.
3. **Memory Capacity & Budget**: Capacity $C=20$, Retrieval top-$k=5$.
4. **Retriever v0 Algorithm**: Deterministic structural filter + normalized utility reranking ($O(|M|)$ memory scan without external vector database).
5. **Archivist LLM Backend**: Small local LLM (e.g., Qwen-2.5-7B or Llama-3-8B local server endpoint) with `temperature=0.0`.
6. **Storage Layer**: Line-delimited JSONL with atomic rename (`.tmp` $\rightarrow$ target) for single-node execution.

---

## 7. Conflicts & Ambiguities

1. **Retriever Coupling Conflict**:
   * *Specification*: `CMHH_Archivist_Retriever_Design_Specification` explicitly requires `Retriever` to be an independent class separate from `Archivist` and `MemoryStore`.
   * *Current Code*: `memory.py` defines `retrieve_naive()` helper, which is called directly by `StreamRunner`.
   * *Resolution*: Extract `RetrieverV0` into `src/cmhh/retrieval/retriever_v0.py`.

2. **Memory Schema Conflict**:
   * *Specification*: `CMHH_Implementation_Ready_Specification` specifies a 3-layer unit ($h_i, k_i, z_i, \mu_i$).
   * *Current Code*: `MemoryUnit` is a flat dict with simple `type` and string `key`.
   * *Resolution*: Upgrade `MemoryUnit` in `src/cmhh/memory/models.py` to match the 3-layer specification with `schema_version = 1`.

3. **Forward Transfer Baseline Calculation Conflict**:
   * *Specification*: `CMHH_Research_Specification` requires Pre-learning Probe ($A$) to measure zero-shot transfer before learning $T_k$.
   * *Current Code*: `runner.py` uses external static dictionary `cold_start_scores`.
   * *Resolution*: Implement dynamic Pre-learning Probe ($A$) in `StreamRunner`.

---

## 8. Recommended Implementation Order

To maintain codebase stability and experimental integrity, implementation should follow this phased sequence:

```text
Phase 0: Research Integrity & Protocol Alignment
  ├── Implement read-only Pre-learning Probe (A)
  ├── Refactor Retention Probe (C) to query Retriever over current memory M_k
  └── Enforce subprocess RNG stream determinism
        │
        v
Phase 1: Architecture Refactoring & Data Models
  ├── Extract independent Retriever interface (src/cmhh/retrieval/base.py & retriever_v0.py)
  ├── Upgrade MemoryItem schema to 3-layer model (h_i, k_i, z_i, mu_i)
  └── Implement WorkingBuffer (src/cmhh/memory/working_buffer.py)
        │
        v
Phase 2: Baseline Standardization
  ├── Refactor Naive Memory baseline to use standalone RetrieverV0 and MemoryStore
  └── Standardize Population Carryover baseline
        │
        v
Phase 3: Archivist Lifecycle Implementation
  ├── Implement Admission Gate (elite_validation & novelty check)
  ├── Implement Distillation backend (local LLM adapter)
  ├── Implement Protection & Utility Update rules
  └── Implement Eviction Policy (utility-recency-protection ranking)
        │
        v
Phase 4: Continual Logging & Audit Diagnostics
  ├── Standardize event-sourced logging schema
  └── Implement memory diagnostic reporting (retrieval rate, utility drift, eviction lineage)
        │
        v
Phase 5: Full Stream Validation & Verification
  ├── Run end-to-end TSP stream verification
  └── Execute regression test suite
```

---

## 9. Proposed First PR

### PR Title: `refactor: extract independent Retriever interface and enforce read-only probe protocol`

#### Primary Objective
Fix P0 research protocol issues (Pre-learning Probe $A$ and Retention Probe $C$) and P1 component coupling by extracting an independent `Retriever` class, without disrupting existing CLI functionality.

#### Proposed File Changes:
1. **`[NEW] src/cmhh/retrieval/base.py`**:
   Define `Retriever` abstract base class with signature `retrieve(query: RetrievalQuery, memory: Sequence[MemoryItem], budget: RetrievalBudget) -> Sequence[RetrievedMemory]`.
2. **`[NEW] src/cmhh/retrieval/retriever_v0.py`**:
   Implement `RetrieverV0` incorporating Stage 1 structural filtering and Stage 3 utility reranking.
3. **`[MODIFY] src/cmhh/runner.py`**:
   * Add `_run_pre_learning_probe()` executed before search on $T_k$.
   * Refactor post-task evaluations into `_run_retention_probe()` that re-queries `Retriever` on $M_k$.
   * Enforce `read_only=True` invariant during all probe calls (preventing memory updates or evolutionary search).
4. **`[NEW] tests/cmhh/test_retriever_and_probes.py`**:
   Add unit tests verifying:
   * Independent execution of `RetrieverV0`.
   * Read-only invariant during Pre-learning and Retention probes.
   * Correct recording of performance matrix cells $R_{k,j}$.

---

## 10. Questions Requiring Research-Owner Decision

1. **Retention Probe Selection Procedure**:
   When `Retriever` returns top-$k$ memory items for a previously learned task $T_j$ during Retention Probe ($C$), what exact deterministic tie-breaking or selection procedure should pick the final executable heuristic when $k > 1$, given that no validation tuning or re-search is permitted during probes?

2. **Protection Anchor Capacity Overflow Policy**:
   When the cumulative number of protected memory items across tasks reaches or exceeds total memory capacity $C$, should the system explicitly halt with a `CapacityOverflowError`, or automatically trigger semantic consolidation to merge protected anchors?

3. **Incompatible Task Shift Protocol**:
   For task transitions where executable code cannot be transferred zero-shot (e.g. TSP $\to$ CVRP due to interface changes), should zero-shot Forward Transfer be explicitly recorded as `N/A`, with transfer performance measured solely through Adaptation Efficiency?
