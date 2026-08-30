# CMHH Engineering Handoff Review

**Date:** 2026-08-29
**Repository:** `CM_HH/HeurAgenix`
**Purpose:** current implementation status and next engineering steps toward
full CM-HH.

This document is an engineering handoff. The architecture source of truth is
`IDEA/source_of_truth/CMHH_Archivist_Retriever_Design_Specification.md`.

---

## 1. Current repo status

The repo is no longer only a naive-memory prototype. It has a runnable
continual-learning substrate and a managed-memory prototype.

```text
implemented / runnable:
    TSP ascending and descending streams
    Concorde reference pipeline
    EOH cold-start baseline
    HeurAgenix isolated baseline
    population carryover baseline
    naive bounded memory baseline
    naive unbounded memory baseline
    managed Archivist prototype
    MemoryItem / MemoryStore / WorkingBuffer scaffold
    NaiveMemoryManager
    DefaultArchivist
    RetrieverV0 interface
    Stage A pre-learning probe
    Stage C retention probe
    probe read-only state hash checks
    TSP baseline runner scripts
```

The current `archivist_managed` condition is useful for pilot experiments, but
it is not yet the full CM-HH system because transfer planning and
memory-aware population construction are still implicit.

---

## 2. Current architecture map

```text
cli.py
  |
  v
StreamRunner
  |
  +-- TaskSpec / stream config
  +-- Generator: baseline, HeurAgenix, or EOH
  +-- Evaluator: subprocess heuristic execution
  +-- WorkingBuffer
  +-- MemoryStore
  +-- Memory manager:
        - NaiveMemoryManager for naive memory
        - DefaultArchivist for managed memory prototype
  +-- RetrieverV0
  +-- Metrics / audit / checkpoints
```

The target full-CMHH architecture should become:

```text
completed task
    -> CandidateExtractor
    -> Archivist
    -> MemoryStore
    -> Retriever
    -> TransferPolicy
    -> PopulationBuilder
    -> current-task evolution
    -> transfer feedback
    -> CandidateExtractor
    -> Archivist
```

---

## 3. Spec-to-code status

| Requirement | Current status | Next action |
|---|---|---|
| TSP stream and reference data | Runnable | Keep frozen for pilot comparisons |
| EOH baseline | Runnable, but live LLM quality may fail candidate validation | Run with logging and timeout guards |
| HeurAgenix isolated baseline | Runnable | Use as cold-start baseline |
| Population carryover | Runnable | Keep as no-external-memory sequential baseline |
| Naive memory bounded/unbounded | Runnable | Use for capacity/noise diagnostics |
| Managed Archivist | Prototype runnable | Add transfer pipeline and richer evidence |
| `MemoryItem` schema | Partial 3-layer scaffold | Add evidence history, status, updated_at, lineage |
| `WorkingBuffer` | Present | Move candidate selection into `CandidateExtractor` |
| `RetrieverV0` | Present | Strengthen compatibility/interface filtering |
| Stage A pre-learning probe | Present | Keep read-only; separate diagnostic vs planning probes |
| Stage C retention probe | Present | Keep read-only; verify retrieved competence semantics |
| TransferPolicy | Missing | Implement DIRECT_REUSE / REFINE / IGNORE |
| PopulationBuilder | Missing | Implement fixed memory/fresh quota |
| Transfer feedback | Partial/missing | Add validation-only update path |
| Child-memory lineage | Missing | Create child `MemoryItem` for admitted refined artifacts |
| Logging and diagnostics | Partial | Add retrieved -> planned -> inserted -> survived -> child events |

---

## 4. Full CM-HH implementation order

1. **CandidateExtractor**
   - Extract top-k final-population candidates by validation score.
   - Persist candidate id, artifact id, score, source task, generation, code
     hash, and parent artifact ids.

2. **Transfer models**
   - Add `TransferPlan`.
   - Add `TransferRecord`.
   - Add `TransferEvidence`.

3. **TransferPolicy**
   - Implement deterministic V0 policy:
     `DIRECT_REUSE`, `REFINE`, `IGNORE`.
   - Log one action per retrieved memory.

4. **PopulationBuilder**
   - Build `P0` from fixed quotas:
     memory-derived seeds plus fresh generated candidates.
   - Log the source of every `P0` member.

5. **Validation-only feedback**
   - After evolution, check whether memory-derived members survived or produced
     useful children.
   - Update parent memory evidence using validation results only.

6. **Child-memory lineage**
   - Refined code becomes a new artifact.
   - If admitted, it becomes a child memory with `parent_memory_ids`.
   - Parent executable code is never overwritten.

7. **Diagnostics**
   - Add retrieval-to-survival rate.
   - Add retrieval-to-descendant-success rate.
   - Add positive/negative transfer rate.
   - Add memory efficiency and archive churn.

---

## 5. Experiment interpretation

Use current runs as pilot evidence:

```text
EOH cold start
HeurAgenix isolated
population carryover
naive unbounded memory
naive bounded memory
managed Archivist prototype
```

For a managed-memory claim, the key controlled comparison is:

```text
naive bounded vs managed Archivist
same stream
same seed
same LLM/generator
same candidate budget
same memory capacity
same retrieval top-k
```

Naive unbounded should be reported as an auxiliary diagnostic: it helps decide
whether failures come from capacity pressure or from uncurated memory noise.

---

## 6. Engineering warning

Do not describe the current managed condition as "full CM-HH" in a paper result
yet. The honest label is:

```text
managed Archivist prototype
```

It becomes full CM-HH only after `CandidateExtractor`, `TransferPolicy`,
`PopulationBuilder`, validation-only transfer feedback, and child-memory lineage
are implemented and audited.
