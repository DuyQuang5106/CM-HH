# CM-HH Archivist and Retriever — Design Specification

## 1. Purpose

This document specifies the **final conceptual design decisions** for the Archivist and Retriever components in CM-HH.

The purpose of this specification is to define:

- what the Archivist is responsible for;
- what information is stored in continual memory;
- how experience is promoted from transient search history into long-term memory;
- how the Retriever selects previously stored knowledge for a new task;
- how forgetting can occur at both the storage and retrieval levels;
- which decisions belong to the research architecture, and which are intentionally deferred to implementation or experimental ablation.

This document describes the **research-level architecture** rather than a specific software implementation.

---

## 2. Design Principles

The Archivist is designed around five principles.

1. **Memory is selective, not a complete log.**  
   CM-HH should not retain every trajectory or generated heuristic indefinitely.

2. **Long-term memory is distinct from the evolutionary working population.**  
   The current population supports search on the present task, whereas the Archivist maintains reusable competence across tasks.

3. **Stored knowledge should support both retention and transfer.**  
   Memory must help preserve competence on previously learned tasks while also providing useful knowledge for future tasks.

4. **Retrieval quality is part of continual-learning performance.**  
   A useful memory item that is never retrieved, or an irrelevant item that repeatedly interferes with search, can cause functional forgetting even when nothing has been physically deleted.

5. **The architecture should remain interpretable and experimentally isolatable.**  
   Retriever, consolidation, protection, and eviction mechanisms must be measurable independently through controlled baselines and ablations.

---

# 3. System-Level Role of the Archivist

## 3.1 Definition

The **Archivist is a selective continual-memory management mechanism**.

It is **not**:

- a raw experiment logger;
- a replay buffer containing every search trajectory;
- the evolutionary population itself;
- the Retriever itself.

Instead, the Archivist governs the lifecycle of reusable knowledge.

Conceptually:

```text
search / evolution
      |
      v
temporary experience
      |
      v
bounded working buffer
      |
      v
+----------------------+
|      Archivist       |
|----------------------|
| evaluate             |
| distill              |
| promote / reject     |
| update               |
| protect              |
| consolidate          |
| evict                |
+----------------------+
      |
      v
long-term memory
```

The Archivist therefore acts primarily as a **selective consolidation gate** between transient search experience and persistent multi-task memory.

---

## 3.2 Responsibilities

The Archivist is responsible for:

- **admission** — deciding whether an experience deserves long-term storage;
- **distillation** — extracting reusable knowledge from raw experience;
- **representation** — converting admitted experience into structured memory units;
- **update** — updating utility and empirical evidence associated with existing memories;
- **consolidation** — merging or compressing redundant knowledge;
- **protection** — preventing important competence from being overwritten or evicted;
- **capacity management** — maintaining bounded long-term memory;
- **eviction** — deliberately removing low-value memories when capacity is constrained;
- **provenance preservation** — maintaining sufficient lineage information for audit and reproducibility;
- **forgetting diagnosis support** — exposing information needed to distinguish storage loss from retrieval-side interference.

Retrieval itself is delegated to the **Retriever**, although the Archivist maintains the metadata required for retrieval.

---

# 4. Memory Lifecycle

The memory lifecycle is:

```text
generated candidate / trajectory
            |
            v
   bounded working buffer
            |
            v
     Archivist assessment
      /               \
 reject               promote
                        |
                        v
                 distill / link
                        |
                        v
                 long-term memory
                        |
                repeated evaluation
                        |
              utility / protection update
                        |
              consolidate or evict
```

A newly generated experience is therefore **not automatically a memory**.

Before promotion, the Archivist considers whether the experience contains:

- sufficient **novelty** relative to existing memory;
- sufficient **expected future utility**;
- meaningful empirical improvement;
- useful task-transfer information;
- information required to preserve important lineage or provenance.

This prevents long-term memory from degenerating into an unbounded archive of raw search history.

---

# 5. Memory Representation

## 5.1 Three-Layer Memory Architecture

The full Archivist uses three linked forms of long-term knowledge.

### 5.1.1 Episodic Archive

The episodic layer stores compressed records of important search experiences.

Examples include:

- parent heuristic;
- generated offspring;
- mutation or generation operator;
- task context;
- fitness before and after modification;
- important reasoning or trajectory fragments;
- lineage information.

Its main purpose is to preserve **how useful knowledge was discovered**.

It is not intended to retain every raw LLM interaction.

---

### 5.1.2 Semantic Knowledge

The semantic layer contains distilled, reusable principles extracted from one or more episodes.

Examples:

```text
"For larger Euclidean TSP instances, candidate selection based only on
nearest distance tends to become too myopic; incorporating local
neighborhood structure improves robustness."
```

Semantic knowledge is intended to capture information that can transfer beyond one exact heuristic implementation.

Its main purpose is **generalization and cross-task reuse**.

---

### 5.1.3 Procedural Skill Library

The procedural layer stores executable heuristic artifacts.

Examples include:

- heuristic functions;
- constructive rules;
- local-search operators;
- reusable code fragments;
- parameterized heuristic templates.

Its main purpose is to preserve **directly executable competence**.

---

## 5.2 Logical Memory Unit

A useful abstract representation is:

\[
m_i = (h_i, k_i, z_i, \mu_i)
\]

where:

- \(h_i\): executable heuristic or procedural artifact;
- \(k_i\): applicability / retrieval descriptor;
- \(z_i\): semantic or procedural abstraction associated with the artifact;
- \(\mu_i\): empirical and lifecycle metadata.

The exact serialized schema may vary in implementation, but these logical roles must remain identifiable.

---

## 5.3 Applicability Descriptor \(k_i\)

The applicability descriptor should contain observable task characteristics useful for retrieval.

Initial fields may include:

```yaml
problem_family: TSP
problem_size: 100
distribution: euclidean_uniform
construction_type: constructive
objective: minimize
```

Additional structural descriptors may later be added when justified empirically.

The key principle is:

> Retrieval should initially rely on observable and interpretable task information rather than hidden task identifiers.

---

## 5.4 Metadata \(\mu_i\)

Metadata may include:

```yaml
origin_task:
origin_generation:
parent_id:
operator:
fitness:
fitness_delta:
validation_performance:
transfer_history:
retrieval_count:
successful_reuse_count:
last_used:
utility:
novelty:
protection_status:
provenance:
```

These fields support:

- utility estimation;
- protection;
- retrieval;
- eviction;
- lineage analysis;
- reproducibility;
- continual-learning diagnostics.

---

# 6. Working Buffer vs Long-Term Memory

CM-HH explicitly separates two storage timescales.

## Working buffer

Short-lived and bounded.

Contains:

- recent trajectories;
- current evolutionary evidence;
- candidate heuristics not yet admitted;
- temporary context needed for consolidation.

It may contain noisy or redundant information.

## Long-term Archivist memory

Persistent across tasks.

Contains only selected and structured knowledge judged sufficiently useful for future reuse.

This separation is important because:

```text
working buffer = "what just happened"

long-term memory = "what is worth remembering"
```

The evolutionary population is also distinct from both.

---

# 7. Retriever

## 7.1 Role

The Retriever answers:

> Given the current task and current search context, which stored memories are most likely to be useful now?

Formally:

\[
R(q_t, \mathcal{M}_t, B) \rightarrow S_t
\]

where:

- \(q_t\) is the current retrieval query;
- \(\mathcal{M}_t\) is the current long-term memory;
- \(B\) is the retrieval budget;
- \(S_t\) is the selected subset of memory.

The Retriever does **not** modify memory.

Its responsibility is selection and ranking.

---

# 8. Retriever Design Decision

## 8.1 Full Target Architecture

The final target Retriever is a **hybrid symbolic + semantic retriever**.

The retrieval pipeline is:

```text
current task / search context
          |
          v
   structured query
          |
          v
metadata / constraint filtering
          |
          v
candidate memory subset
          |
          v
semantic similarity
          |
          v
utility-aware reranking
          |
          v
Top-k memories
```

The important design decision is the ordering:

> **filter structurally first, then perform semantic ranking.**

This prevents semantic similarity alone from retrieving memories that are linguistically similar but operationally incompatible with the current task.

---

## 8.2 Stage 1 — Symbolic / Structural Filtering

The first stage uses explicit metadata and applicability constraints.

Possible fields include:

- problem family;
- task formulation;
- instance size or size range;
- distribution;
- heuristic type;
- solver interface;
- operator compatibility;
- other task constraints.

Example:

```text
Query:
TSP / constructive / size=100 / Euclidean

Memory pool:
10,000 items
        |
        v
structural filter
        |
        v
850 compatible candidates
```

This stage is intentionally interpretable.

---

## 8.3 Stage 2 — Semantic Similarity

After structural filtering, semantic representations may be used to estimate whether the knowledge encoded in a memory item matches the current context.

Semantic retrieval is primarily associated with \(z_i\), the reusable abstraction attached to a memory item.

This allows retrieval to recognize relations that are not captured by exact symbolic fields.

For example, two heuristics may originate from different task sizes but encode the same useful principle.

---

## 8.4 Stage 3 — Utility-Aware Reranking

Semantic relevance alone is insufficient.

A memory may look relevant but historically perform poorly.

Therefore final ranking should consider both:

- estimated relevance;
- empirical utility.

A general form is:

\[
score(q,m_i)
=
\alpha \cdot similarity(q,m_i)
+
\beta \cdot utility(m_i)
\]

The precise utility function and coefficients are implementation/evaluation decisions.

Utility may later incorporate:

- validation performance;
- transfer success;
- successful retrieval history;
- robustness across tasks;
- recency;
- redundancy;
- computational cost.

---

# 9. Retriever v0 for Initial Experiments

The **full Retriever architecture** above is the target system.

However, the initial experimental implementation should remain deliberately simpler so that retrieval effects can be isolated.

Retriever v0 is:

- task-level;
- bounded-memory;
- interpretable;
- based primarily on structured task similarity and empirical utility;
- implemented with a simple scan over memory followed by Top-\(k\) selection.

Conceptually:

\[
score(q,m_i)
=
\alpha \cdot structural\_similarity(q,k_i)
+
\beta \cdot utility(\mu_i)
\]

Retriever v0 intentionally does **not require**:

- a learned retriever;
- ANN indexing;
- a vector database;
- an LLM reranker;
- a complex embedding pipeline.

This is an experimental simplification, **not a change to the target Archivist architecture**.

The purpose is to establish whether retrieval itself is useful before adding additional semantic machinery.

---

# 10. Retrieval Outputs

Retrieved memory does not need to have a single fixed form.

Depending on the downstream consumer, retrieval may return:

### Insight

A distilled principle from semantic memory.

```text
"Prefer diversity-preserving candidate selection when the current
population begins converging prematurely."
```

### Skill

An executable heuristic or code artifact.

```text
heuristic_27.py
```

### Evolution Seed

A previously successful heuristic used to initialize or bias the next evolutionary search.

Thus:

```text
Retriever
   |
   +--> semantic insight
   |
   +--> executable skill
   |
   +--> evolutionary seed
```

---

# 11. Model Allocation

## 11.1 Archivist Model

The default Archivist should use a **small local model** when an LLM-based operation is required.

The motivation is:

- lower cost;
- offline operation;
- reproducibility;
- stable latency;
- frequent invocation without dominating the experimental budget.

A larger model is reserved only as a fallback for cases such as:

- difficult consolidation;
- ambiguous distillation;
- low-confidence decisions.

The research claim should therefore concern the **memory mechanism**, not depend on continuously using the strongest available model.

---

## 11.2 Retriever Model

The Retriever should not require an LLM for every query.

Structured filtering and deterministic ranking remain valid retrieval operations.

Semantic representations may be introduced as part of the full Retriever, but the retrieval mechanism should remain separable from the language model used by the Generator or other agents.

---

# 12. Forgetting

CM-HH defines forgetting more broadly than physical deletion.

There are at least two important forms.

---

## 12.1 Storage Forgetting

A useful memory is:

- overwritten;
- evicted;
- incorrectly consolidated;
- corrupted;
- reduced beyond usefulness.

Example:

```text
useful skill H_old
      |
      v
memory pressure
      |
      v
evicted
      |
      v
old-task competence decreases
```

This is the most direct analogue of losing stored knowledge.

---

## 12.2 Retrieval-Induced / Functional Forgetting

The useful knowledge may still exist in memory but fail to influence behavior.

Example:

```text
memory:
H1  H2  H3  ...  H5000

correct old-task skill = H17

Retriever:
returns H903, H1102, H2411
but not H17
```

Nothing has been deleted.

Nevertheless, the system behaves as though it has forgotten.

Functional forgetting can arise from:

- retrieval pollution;
- retrieval dilution;
- poor ranking;
- misleading similarity;
- memory growth;
- stale utility estimates;
- interference from newer memories.

Therefore:

> Retention must be evaluated through the current memory and Retriever, not only by checking whether an old artifact still exists in storage.

---

# 13. Eviction and Protection

Long-term memory is bounded.

When capacity becomes constrained, the Archivist should apply deliberate eviction rather than uncontrolled overwrite.

The intended policy combines:

- **utility**;
- **recency**;
- **redundancy**;
- **protection status**.

Conceptually:

\[
eviction\_priority(m_i)
=
f(
low\ utility,
low\ recency,
high\ redundancy,
protection
)
\]

High-value or currently active memories may be protected.

Examples include:

- skills responsible for retained competence on earlier tasks;
- knowledge repeatedly useful across tasks;
- rare memories with unique coverage;
- memories currently supporting active tasks.

The exact eviction formula is intentionally left to implementation and ablation.

---

# 14. Provenance Preservation

Even when an episode or heuristic is compressed or evicted, CM-HH should preserve the minimum provenance required for auditability.

Useful provenance includes:

- memory identifier;
- origin task;
- parent;
- operator;
- creation time / stage;
- key performance evidence;
- lineage relation;
- consolidation source.

This enables later analysis of questions such as:

```text
Where did this skill come from?

Which earlier heuristic produced it?

Why was it promoted?

Why was another memory evicted?

Which retrieved memory caused an observed transfer gain or failure?
```

Provenance is therefore part of the scientific instrumentation of CM-HH, not merely debugging metadata.

---

# 15. Separation of Responsibilities

The final architecture should maintain the following conceptual boundaries.

| Component | Primary responsibility |
|---|---|
| Evolutionary population | Search on the current task |
| Working buffer | Temporarily hold recent experience |
| Archivist | Decide what becomes persistent knowledge and manage its lifecycle |
| Long-term memory | Store reusable multi-task competence |
| Retriever | Select relevant stored knowledge for the current context |
| Generator / evolutionary agents | Produce new heuristic candidates |
| Evaluator | Measure candidate performance |

The most important distinction is:

```text
Archivist decides what the system remembers.

Retriever decides what remembered knowledge is used now.
```

---

# 16. Research-Level Decisions vs Implementation Decisions

## Fixed by this specification

The following are research-level design decisions:

- Archivist is a **selective consolidation gate**, not a logger.
- Working experience is buffered before long-term admission.
- Long-term memory is distinct from the evolutionary population.
- Memory contains linked episodic, semantic, and procedural knowledge.
- Stored items preserve applicability, empirical utility, and provenance.
- Retrieval is conceptually hybrid:
  - structural filtering;
  - semantic matching;
  - utility-aware reranking.
- Retriever v0 may intentionally use only structural similarity + utility.
- Memory is bounded.
- Forgetting includes both storage loss and retrieval-induced functional forgetting.
- Important memories may be protected.
- Eviction is deliberate rather than uncontrolled overwrite.
- Archivist operations should preferentially use a small local model when an LLM is needed.
- Provenance required for scientific audit should not be discarded.

## Deferred to implementation / experiments

The following should **not** be fixed prematurely in the conceptual specification:

- exact embedding model;
- exact small local LLM;
- embedding dimensionality;
- exact utility function;
- exact novelty threshold;
- exact promotion threshold;
- exact memory capacity;
- exact Top-\(k\);
- exact \(\alpha,\beta\) weighting;
- exact eviction equation;
- ANN / vector-database implementation;
- semantic clustering algorithm;
- compression method;
- confidence threshold for large-model fallback.

These should be selected through implementation constraints, validation experiments, or ablation studies.

---

# 17. Minimal Formalization

Let the long-term memory after task \(t\) be:

\[
\mathcal{M}_t = \{m_1,m_2,\ldots,m_N\}
\]

with:

\[
m_i=(h_i,k_i,z_i,\mu_i)
\]

The Retriever is:

\[
R(q_t,\mathcal{M}_t,B)\rightarrow S_t
\]

where \(S_t\subseteq\mathcal{M}_t\) and \(|S_t|\le B\).

The Archivist consolidation process can be represented as:

\[
C(\mathcal{M}_t,E_t)\rightarrow\mathcal{M}_{t+1}
\]

where \(E_t\) denotes newly observed experience.

The complete continual-memory loop is therefore:

\[
\boxed{
E_t
\xrightarrow{\text{Archivist}}
\mathcal{M}_{t+1}
\xrightarrow{\text{Retriever}}
S_{t+1}
\xrightarrow{\text{search/use}}
E_{t+1}
}
\]

This loop makes memory an active component of continual heuristic discovery rather than passive storage.

---

# 18. Final Design Summary

The finalized CM-HH memory architecture can be summarized as:

```text
                    CURRENT TASK
                         |
                         v
                 +----------------+
                 |   RETRIEVER    |
                 |----------------|
                 | filter         |
                 | match          |
                 | rerank         |
                 +----------------+
                         ^
                         |
                LONG-TERM MEMORY
       +----------------------------------+
       | Episodic | Semantic | Procedural |
       +----------------------------------+
                         ^
                         |
                 +----------------+
                 |   ARCHIVIST    |
                 |----------------|
                 | admit/reject   |
                 | distill        |
                 | consolidate    |
                 | protect        |
                 | evict          |
                 +----------------+
                         ^
                         |
                 WORKING BUFFER
                         ^
                         |
                 SEARCH / EVOLUTION
```

The core design principle is:

> **The Archivist controls what deserves to survive across tasks; the Retriever controls which surviving knowledge becomes behaviorally accessible for the current task.**

Under this view, continual forgetting in CM-HH is not limited to deleting old heuristics. It can occur whenever previously useful competence becomes unavailable, inaccessible, or harmful under the current memory-management and retrieval process.
