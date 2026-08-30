# CM-HH Archivist, Retriever, and Memory-Transfer Design Specification

**Document role:** source of truth for CM-HH memory architecture
**Status:** authoritative research-level architecture
**Last updated:** 2026-08-29
**Audience:** research owner, implementation engineer, experiment operator

This document defines how continual memory works in CM-HH. It is intentionally
more specific than the original research idea, but it still avoids fixing
hyperparameters that must be selected by validation experiments.

---

## 1. One-screen mental model

CM-HH is not just "save old heuristics and paste them into the next prompt".
It is a controlled loop with four separate questions:

```text
COMPLETED TASK
    |
    v
final population + search history
    |
    v
+--------------------+
| CandidateExtractor |  What should even be considered?
+--------------------+
    |
    v
memory candidates
    |
    v
+-----------+
| Archivist |          What should be remembered?
+-----------+
    |
    v
Long-Term MemoryStore
    |
    | next task arrives
    v
+-----------+
| Retriever |          What should be recalled now?
+-----------+
    |
    v
retrieved memories
    |
    v
+------------------------------+
| TransferPolicy               |  How should recalled knowledge be used?
| PopulationBuilder            |
+------------------------------+
    |
    v
initial population P0
    |
    v
heuristic evolution on current task
```

The key design boundary is:

```text
CandidateExtractor selects candidate experiences.
Archivist writes, updates, protects, consolidates, and evicts memory.
Retriever reads and ranks memory for the current query.
TransferPolicy decides REUSE / REFINE / IGNORE.
PopulationBuilder turns the transfer plan into the actual initial population.
```

These boundaries are required because CM-HH wants to measure not only whether
memory helps, but where memory fails:

```text
stored memory bad?
retrieval bad?
transfer policy bad?
population initialization bad?
evolution failed to exploit transferred knowledge?
```

---

## 2. Core research principles

1. **Memory is selective, not a raw log.**
   Search history is evidence. It only becomes long-term memory after an
   Archivist decision.

2. **Population is not memory.**
   The evolutionary population is current-task search state. Long-term memory
   is persistent cross-task knowledge.

3. **Retrieved does not mean transferred.**
   A memory can be retrieved, omitted from context, inserted as a seed, refined,
   eliminated, or become the ancestor of a better child heuristic. These are
   different events.

4. **Zero-shot success is not adaptation success.**
   A heuristic can perform poorly unchanged but still be a useful parent for
   fast refinement.

5. **Forgetting can be physical or functional.**
   A memory can be evicted from storage, or it can remain stored but stop being
   retrieved or used effectively.

6. **Test probes are read-only.**
   Test results can measure retained competence, but must never update memory,
   prompts, retrieval scores, selection thresholds, or future learning state.

7. **All claims require matched budgets.**
   Naive memory and managed memory must share task stream, seeds, generator,
   evaluator, candidate budget, LLM budget, capacity, and retrieval top-k unless
   the changed quantity is explicitly the ablation.

---

## 3. Component ownership

| Component | Owns | Must not own |
|---|---|---|
| `CandidateExtractor` | selecting notable candidates from completed search | long-term admission, retrieval, generation |
| `Archivist` | admission, dedup, evidence update, protection, consolidation, eviction | retrieval ranking, population building, future-task prediction |
| `MemoryStore` | durable add/load/save/query primitives | policy decisions |
| `Retriever` | read-only filtering/ranking for a query | memory writes, transfer decisions |
| `TransferProbe` | optional empirical diagnostic of retrieved memories | learner mutation, hidden test adaptation |
| `TransferPolicy` | REUSE / REFINE / IGNORE planning | memory admission, final evolution selection |
| `PopulationBuilder` | constructing P0 from memory-derived and fresh candidates | retrieval scoring, Archivist decisions |
| `StreamRunner` | enforcing A/B/C protocol and logging | hiding policy logic inside orchestration |

The runner may orchestrate these components, but it should not become the place
where memory policy secretly lives.

---

## 4. Memory representation

The logical memory unit is:

```text
m_i = (h_i, k_i, z_i, mu_i)
```

where:

```text
h_i   executable procedural artifact
k_i   applicability / retrieval descriptor
z_i   semantic or procedural abstraction
mu_i  empirical, lifecycle, and provenance metadata
```

### 4.1 Minimum `MemoryItem` schema

```python
@dataclass(frozen=True)
class MemoryItem:
    memory_id: str

    # h_i: executable artifact
    artifact_id: str
    code_path: str
    code_sha256: str
    heuristic_interface: str

    # k_i: applicability descriptor
    problem_family: str
    task_id: str
    size_tier: str | None
    distribution: str | None
    task_signature: dict[str, Any]

    # z_i: abstraction
    abstraction_type: str
    summary: str
    prompt_hint: str | None
    tags: tuple[str, ...]

    # mu_i: metadata
    origin_task_id: str
    origin_generation: int
    source_artifact_ids: tuple[str, ...]
    parent_memory_ids: tuple[str, ...]
    evidence: tuple[MemoryEvidence, ...]
    transfer_history: tuple[TransferEvidence, ...]
    utility_score: float
    retrieval_count_learning: int
    retrieval_count_probe: int
    successful_reuse_count: int
    protected: bool
    status: Literal["provisional", "validated", "transferable", "retired"]
    created_at: str
    updated_at: str
    schema_version: int = 1
```

The current implementation may use a smaller subset, but these logical fields
must remain recoverable or explicitly marked as not-yet-implemented.

### 4.2 Evidence model

Evidence should grow over time without overwriting the original knowledge:

```text
M17 created on TSP20
    evidence: source_validation(TSP20)

M17 reused on TSP50
    evidence: source_validation(TSP20)
              direct_transfer(TSP50)
              refinement_outcome(TSP50)

M17 reused on TSP100
    evidence: source_validation(TSP20)
              direct_transfer(TSP50)
              refinement_outcome(TSP50)
              direct_transfer(TSP100)
```

Only train/validation learning evidence may update learner-visible memory. Test
evidence may be stored in final audit artifacts, but not in fields that affect
future retrieval, utility, admission, or eviction.

### 4.3 Knowledge evolution vs evidence evolution

Do this:

```text
M17
 |
 | refinement produces new code
 v
M31 child memory
```

Do not do this:

```python
M17.code = refined_code
```

The parent memory records reuse evidence. The refined heuristic receives a new
artifact id and, if admitted, a child memory id with `parent_memory_ids=["M17"]`.

This preserves lineage and lets the experiment answer:

```text
Did old memory directly solve the new task?
Did old memory become a useful parent?
Did evolution discard or amplify transferred knowledge?
```

---

## 5. CandidateExtractor

After a task finishes, evolution may produce many artifacts. The Archivist
should not be asked to inspect every noisy candidate unless the budget says so.

The CandidateExtractor answers:

```text
From the completed task, which candidates are worth considering for memory?
```

### 5.1 V0 extractor

The first implementation should be deliberately simple:

```python
def extract(result, k):
    ranked = sort_by_validation_score(result.final_population)
    return ranked[:k]
```

Example:

```text
Final population on TSP50:

H21 gap=2.1%
H22 gap=2.4%
H23 gap=2.5%
H24 gap=4.7%
H25 gap=5.0%

CandidateExtractor(top_k=3) -> H21, H22, H23
```

### 5.2 Why this is a separate module

Later extractor variants can use:

```text
top-k quality
top-k + exact duplicate removal
quality + diversity
quality + complementarity
Pareto quality/runtime/robustness
```

Changing candidate extraction must not require rewriting Archivist admission.

---

## 6. Archivist

The Archivist is the write-side memory manager.

It answers:

```text
Which candidates become persistent memory?
Which existing memories receive new evidence?
Which memories are protected?
Which redundant memories are merged?
Which memories are evicted under capacity pressure?
```

### 6.1 Archivist transaction

At the end of task `T_k`:

```python
def process_transaction(task, candidates, memory_store):
    admitted = []
    updated = []
    rejected = []
    merged = []
    evicted = []

    for candidate in candidates:
        duplicate = find_duplicate(candidate, memory_store)

        if duplicate:
            updated.append(update_evidence(duplicate, candidate))
            merged.append((candidate.id, duplicate.id))
            continue

        if should_admit(candidate, memory_store):
            admitted.append(create_memory_item(candidate))
        else:
            rejected.append(candidate)

    protected = update_protection(memory_store, admitted, updated)
    evicted = enforce_capacity(memory_store, protected)

    commit_atomically(admitted, updated, merged, evicted)
    return ArchivistTransactionResult(...)
```

### 6.2 V0 managed Archivist

For the first reliable CM-HH version:

```text
Admission:
    admit top validation candidates from CandidateExtractor

Deduplication:
    exact artifact hash or exact applicability/summary match

Protection:
    protect the best validation item per completed task as a task anchor

Utility:
    start from validation score
    later add validation-only transfer feedback

Eviction:
    never evict protected anchors
    evict lowest utility non-protected items
    deterministic tie-break by created_at then memory_id

Capacity:
    active MemoryItem count
```

If the number of protected anchors exceeds capacity, the system must fail with
an explicit capacity error rather than silently evicting protected competence.

### 6.3 Naive memory baseline

Naive memory is not the Archivist.

```text
naive_memory_sequential:
    write raw/top candidates
    no protection
    no selective admission beyond simple candidate source
    no distillation
    no consolidation
    FIFO/newest or configured simple capacity policy
```

This condition is useful exactly because it is less intelligent. It isolates
whether curation, protection, and utility-aware eviction add value beyond "just
remember stuff".

---

## 7. Retriever

The Retriever is the read-side memory manager.

It answers:

```text
Given current task/query and current memory snapshot M, which memories are most
likely useful now?
```

Formal form:

```text
R(q_t, M_t, B) -> S_t
```

where `B` is the retrieval budget and `S_t` is an ordered list with
`len(S_t) <= B`.

The Retriever must be read-only. It may emit diagnostic events, but probe
retrieval counters must not affect future learner-visible utility.

### 7.1 Target Retriever pipeline

```text
current task / search context
    |
    v
RetrievalQuery
    |
    v
hard structural filtering
    |
    v
candidate compatible memories
    |
    v
semantic similarity over z_i
    |
    v
utility-aware reranking
    |
    v
top-k RetrievedMemory
```

The ordering is fixed:

```text
filter structurally first, then rank semantically/empirically.
```

This avoids retrieving a linguistically similar but executable-incompatible
memory.

### 7.2 Retriever v0

Initial experiments should use a simple deterministic scan:

```python
def retrieve_v0(query, memory, top_k, alpha=0.7, beta=0.3):
    compatible = []

    for item in memory:
        if item.problem_family != query.problem_family:
            continue
        if item.heuristic_interface != query.heuristic_interface:
            continue

        structural = structural_similarity(query, item)
        utility = normalized_validation_utility(item)
        score = alpha * structural + beta * utility
        compatible.append((score, item))

    return stable_sort(compatible)[:top_k]
```

No learned retriever, vector database, ANN index, or LLM reranker is required
for v0.

---

## 8. TransferProbe

A TransferProbe evaluates what a retrieved memory can do before new learning.

There are two modes:

| Mode | Split | Purpose | Can affect learner? |
|---|---|---|---|
| diagnostic/reporting probe | test | final zero-shot measurement | no |
| planning probe | validation/probe split | optional input to TransferPolicy | yes, if pre-declared |

The first implementation should keep probes diagnostic only unless a separate
validation-only planning protocol is added.

### 8.1 Pre-learning probe A

Before learning task `T_k`:

```text
state M_{k-1}
    |
    v
retrieve/select compatible retained artifact
    |
    v
execute directly on T_k test split
    |
    v
record Z_k
    |
    v
assert learner-visible state unchanged
```

`Z_k` is used for zero-shot FWT measurement:

```text
FWT_0(k) = Z_k - cold_start_baseline(k)
```

If no compatible executable exists:

```text
Z_k = N/A
```

Do not create an artificial zero.

---

## 9. TransferPolicy

TransferPolicy decides how retrieved memory influences the next search.

It answers:

```text
For each retrieved memory, should we directly reuse it, refine it, or ignore it?
```

### 9.1 V0 actions

```text
DIRECT_REUSE
    Insert the executable artifact unchanged as a seed.

REFINE
    Ask the generator/evolver to create a child candidate using the memory as
    parent/context.

IGNORE
    Do not insert this memory into the population or prompt context.
```

`ADAPT` and `RECOMBINE` can be added later, but they are not required for the
first full CM-HH implementation.

### 9.2 TransferPlan schema

```python
@dataclass(frozen=True)
class TransferPlan:
    memory_id: str
    artifact_id: str
    action: Literal["direct_reuse", "refine", "ignore"]
    reason: str
    retrieval_rank: int
    retrieval_score: float
    expected_role: Literal["seed", "prompt_context", "parent", "none"]
```

---

## 10. PopulationBuilder

PopulationBuilder turns transfer plans into the initial population `P0`.

It should keep a fixed quota so comparisons are fair:

```text
population_size = N
memory_seed_quota = M
fresh_quota = N - M
```

Example for `N=8`, `memory_seed_quota=3`:

```text
P0 for TSP50:

H21 = direct reuse from M1
H22 = refinement child from M2
H23 = refinement child from M3
H24 = fresh generated
H25 = fresh generated
H26 = fresh generated
H27 = fresh generated
H28 = fresh generated
```

This makes transfer observable:

```text
retrieved -> planned -> inserted into P0 -> survived selection -> produced child -> improved validation
```

---

## 11. Full end-to-end algorithm

This is the practical algorithm the reader should imagine when reading the
codebase.

```python
memory_store = MemoryStore()

for k, task in enumerate(task_stream):
    # ---------------------------------------------------------
    # A. PRE-LEARNING PROBE: measurement only
    # ---------------------------------------------------------
    before = learner_state_hash()

    zero_shot = run_pre_learning_probe(
        task=task,
        memory_store=memory_store,
        retriever=retriever,
        split="test",
        read_only=True,
    )

    after = learner_state_hash()
    assert before == after
    log("pre_learning_probe_completed", score=zero_shot)

    # ---------------------------------------------------------
    # B1. RETRIEVE FOR LEARNING: validation/search path
    # ---------------------------------------------------------
    query = make_retrieval_query(task)
    retrieved = retriever.retrieve(
        query=query,
        memory=memory_store.snapshot(),
        budget=RetrievalBudget(top_k=K),
    )
    log("memory_retrieved", items=retrieved)

    # ---------------------------------------------------------
    # B2. PLAN TRANSFER
    # ---------------------------------------------------------
    plans = transfer_policy.plan(
        task=task,
        retrieved=retrieved,
        validation_probe_results=None,  # optional in later versions
    )
    log("memory_transfer_planned", plans=plans)

    # ---------------------------------------------------------
    # B3. BUILD INITIAL POPULATION
    # ---------------------------------------------------------
    initial_population = population_builder.build(
        task=task,
        transfer_plans=plans,
        carried_population=previous_population,
        fresh_quota=fresh_quota,
    )
    log("memory_inserted_into_population", population=initial_population)

    # ---------------------------------------------------------
    # B4. EVOLVE CURRENT TASK
    # ---------------------------------------------------------
    result = evolver.run(
        task=task,
        initial_population=initial_population,
        train_split="train",
        validation_split="validation",
        budget=budget,
    )

    # ---------------------------------------------------------
    # B5. UPDATE VALIDATION-ONLY TRANSFER EVIDENCE
    # ---------------------------------------------------------
    transfer_feedback = extract_transfer_feedback(
        plans=plans,
        final_population=result.final_population,
        validation_history=result.validation_history,
    )
    archivist.update_transfer_evidence(
        feedback=transfer_feedback,
        memory_store=memory_store,
        split="validation",
    )
    log("memory_transfer_feedback", feedback=transfer_feedback)

    # ---------------------------------------------------------
    # B6. EXTRACT AND ARCHIVE NEW KNOWLEDGE
    # ---------------------------------------------------------
    candidates = candidate_extractor.extract(
        final_population=result.final_population,
        history=result.history,
        top_k=candidate_k,
    )
    log("memory_candidate_extracted", candidates=candidates)

    transaction = archivist.process_candidates(
        task=task,
        candidates=candidates,
        memory_store=memory_store,
    )
    log("archivist_transaction_committed", transaction=transaction)

    previous_population = result.final_population

    # ---------------------------------------------------------
    # C. RETENTION PROBE: measurement only
    # ---------------------------------------------------------
    before = learner_state_hash()

    for prior_task in task_stream[: k + 1]:
        retained_score = run_retention_probe(
            task=prior_task,
            memory_store=memory_store,
            retriever=retriever,
            split="test",
            read_only=True,
        )
        performance_matrix[k, prior_task.index] = retained_score

    after = learner_state_hash()
    assert before == after

    checkpoint(
        memory_store=memory_store,
        performance_matrix=performance_matrix,
        pre_learning_scores=pre_learning_scores,
    )
```

---

## 12. Concrete example: TSP20 -> TSP50 -> TSP100

### Task 1: TSP20

```text
MemoryStore = {}

Pre-learning probe:
    no memory -> Z_1 = N/A

Learning:
    P0 = fresh heuristics only
    evolution produces H11, H12, H13, ...

CandidateExtractor:
    top-3 validation candidates = H11, H12, H13

Archivist:
    H11 -> M1, protected task anchor
    H12 -> M2
    H13 -> M3

Retention:
    retrieve best TSP20 memory from M1/M2/M3
    evaluate on TSP20 test
    write A[1,1]
```

### Task 2: TSP50

```text
Pre-learning probe:
    retrieve compatible memories M1/M2/M3
    execute top retained artifact on TSP50 test
    write Z_2
    no memory update

Learning retrieval:
    M1 rank 1
    M2 rank 2
    M3 rank 3

TransferPolicy:
    M1 -> DIRECT_REUSE
    M2 -> REFINE
    M3 -> REFINE

PopulationBuilder:
    P0 = [H21 from M1, H22 child of M2, H23 child of M3, fresh...]

Evolution:
    some transferred seeds survive, some die

Archivist evidence update:
    M1 gets validation-only transfer feedback
    M2/M3 get refinement feedback

New memory:
    if child of M3 becomes elite, store it as M4 with parent_memory_ids=[M3]

Retention:
    evaluate current retained competence on TSP20 and TSP50
    write A[2,1], A[2,2]
```

### Task 3: TSP100

```text
Retriever now sees:
    M1: strong source, weak direct transfer to TSP50
    M3: strong source, good refinement on TSP50
    M4: child from TSP50, strong validation score

Likely ranking:
    M4 > M3 > M2 > M1

The system can now prefer memories that have evidence of transfer, not only
memories that were originally good.
```

This is the continual-memory loop:

```text
experience -> memory -> transfer -> evidence -> better future retrieval
```

---

## 13. Required event log vocabulary

The final implementation should emit these events when the corresponding
behavior exists:

```text
pre_learning_probe_started
pre_learning_probe_completed
memory_retrieved
memory_probe_started
memory_probe_finished
memory_transfer_planned
memory_inserted_into_population
memory_refined
memory_offspring_created
memory_survived_selection
memory_eliminated
memory_transfer_feedback
memory_candidate_extracted
memory_admitted
memory_rejected
memory_merged
memory_protected
memory_evicted
archivist_transaction_committed
retention_probe_started
retention_probe_completed
probe_read_only_audit_passed
```

Important distinctions:

```text
retrieved != included in prompt
included in prompt != inserted as seed
inserted as seed != survived evolution
survived evolution != caused improvement
```

---

## 14. Memory diagnostics

End-to-end task performance remains the primary evidence. Memory diagnostics
explain why performance changed.

Recommended diagnostics:

```text
memory_size
admission_rate
rejection_rate
duplicate_rate
merge_rate
eviction_rate
protected_count
retrieval_coverage
retrieval_hit_rate
retrieval_duplicate_rate
retrieval_to_survival_rate
retrieval_to_descendant_success_rate
positive_transfer_rate
negative_transfer_rate
archive_churn
memory_efficiency
```

Useful conceptual diagnostic:

```text
Memory Efficiency = transfer benefit / active memory count
```

This should be treated as a diagnostic, not automatically as a primary paper
metric.

---

## 15. Clean baseline story

The first clean experimental progression is:

```text
EOH cold start
HeurAgenix cold start / isolated
population carryover
naive unbounded memory
naive bounded memory
managed Archivist memory
```

For the managed-memory claim, the most important controlled comparison is:

```text
naive bounded memory vs managed Archivist
same stream
same seed
same generator
same budget
same capacity C
same retrieval top-k
```

Unbounded memory is a useful extra baseline because it answers:

```text
Is capacity pressure itself the cause of failure, or does uncurated memory
become noisy even when it is not forced to forget physically?
```

---

## 16. What is already implemented vs target architecture

As of 2026-08-29, the repository has these pieces:

```text
implemented:
    MemoryItem / MemoryStore / WorkingBuffer scaffold
    NaiveMemoryManager
    DefaultArchivist with elite admission, task-anchor protection, capacity eviction
    RetrieverV0 interface and deterministic ranking
    Stage A pre-learning probe with read-only hash check
    Stage C retention probe read-only hash check
    naive bounded and unbounded configs
    managed Archivist condition wiring
    TSP ascending/descending baseline scripts

still incomplete for full CM-HH:
    first-class CandidateExtractor module
    TransferPolicy module
    PopulationBuilder / memory-aware initializer
    explicit TransferPlan and TransferRecord schemas
    validation-only transfer feedback update path
    child-memory lineage for refined artifacts
    dedup/consolidation beyond simple current behavior
    richer event vocabulary and diagnostics
    probe cost accounting
```

Therefore, the current `archivist_managed` condition is a runnable managed
memory prototype, not yet the full CM-HH architecture described above.

---

## 17. V0 implementation target

The next full-CMHH implementation milestone should add exactly these pieces:

```text
CandidateExtractor
    top_k(final_population, by=validation_score)

TransferPolicy
    DIRECT_REUSE / REFINE / IGNORE

PopulationBuilder
    fixed memory-derived quota
    fixed fresh quota

Memory evidence
    update old memory from validation-only reuse outcomes

Knowledge evolution
    create child MemoryItem for admitted refined heuristics

Logging
    log retrieved -> planned -> inserted -> survived -> child -> admitted
```

This is the smallest version that makes the memory system scientifically
interpretable rather than just "retrieval text inside prompt".

---

## 18. Final summary

The clarified CM-HH architecture is:

```text
CandidateExtractor decides what evidence deserves inspection.
Archivist decides what survives.
Retriever decides what is accessible now.
TransferPolicy decides how recalled knowledge is used.
PopulationBuilder makes that use concrete inside evolution.
Evaluator measures what actually works.
Runner enforces that measurement never becomes hidden learning.
```

That separation is the backbone of CM-HH.
