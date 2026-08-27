# CMHH Research Specification

## 1. Research Thesis

Current LLM-based heuristic search systems are primarily designed to optimize heuristics for a fixed optimization problem, a fixed task, or a predefined task distribution. In such settings, heuristic search is typically performed as an isolated optimization process: the system searches for high-performing heuristics for the current task, but the knowledge discovered during that search is not explicitly treated as knowledge that should be preserved, reused, and managed across future tasks.

However, real-world optimization systems may operate in a non-stationary environment where optimization tasks arrive sequentially:

$$
T_1 \rightarrow T_2 \rightarrow T_3 \rightarrow \dots \rightarrow T_K
$$

Later tasks may differ from earlier ones in problem scale, instance distribution, problem family, or a combination of these shifts. In this setting, repeatedly restarting heuristic search from scratch discards potentially reusable knowledge discovered on previous tasks. Conversely, continuously carrying previous heuristic knowledge forward may introduce interference when previously useful knowledge becomes irrelevant, misleading, or competes with knowledge required by the current task.

CMHH studies this setting from a Continual Learning perspective.

The central research question is:

> **Can an LLM-based heuristic search system continuously acquire, retain, and reuse heuristic knowledge across a sequential stream of combinatorial optimization tasks while avoiding destructive interference with previously acquired capabilities?**
>
> **More specifically: can the system construct a persistent problem-solving competence such that previously learned tasks remain solvable without full re-optimization, while knowledge from earlier tasks supports efficient adaptation to new ones?**

The continual-learning problem in CMHH differs from classical parameter-based continual learning. In neural continual learning, knowledge is primarily encoded in model parameters, and catastrophic forgetting is commonly observed when parameter updates for new tasks degrade performance on previously learned tasks.

In CMHH, the LLM itself is not continually trained. Instead, learning occurs at the level of the heuristic-search system. The system discovers explicit heuristic artifacts and accumulates information about their usefulness while interacting with a sequence of optimization tasks.

**Crucially, in CMHH, evolutionary heuristic search is the learning process, while the accumulated heuristic memory, retrieval mechanisms, and decision systems constitute the learned continual system.** This resembles the relationship between training (SGD) and trained model in neural continual learning, but adapted to a domain where the LLM is frozen and learning operates on heuristic knowledge rather than model parameters.

Therefore, CMHH reframes continual learning from:

$$
\text{continual preservation of learned model parameters}
$$

to:

$$
\text{continual acquisition, retention, retrieval, and adaptation of heuristic knowledge}.
$$

Under this formulation, forgetting should not be interpreted simply as the physical deletion of a stored heuristic. A heuristic may remain present in an external memory while the overall system loses the ability to effectively retrieve, select, adapt, or reuse it. Consequently, forgetting in CMHH is fundamentally a **loss of previously acquired problem-solving capability**, which may arise from different underlying memory and search mechanisms.

We distinguish **functional forgetting** from mere storage loss:

- **Storage forgetting**: heuristic knowledge is physically removed or overwritten.
- **Functional forgetting**: despite stored knowledge remaining intact, the system cannot reliably retrieve, select, or effectively apply it to a previously learned task, resulting in degraded performance without full re-search.

A continual learning system must guard against both. The critical insight is that **stored knowledge ≠ accessible competence**; forgetting must be measured at the capability level, not merely at the storage level.

This creates a stability–plasticity problem at the heuristic-knowledge level:

- **Plasticity** is the ability of the system to discover and adapt heuristic knowledge for newly encountered tasks.
- **Stability** is the ability to preserve and reuse useful knowledge acquired from previous tasks.

A successful continual heuristic-search system must achieve both. Excessive plasticity may cause useful past knowledge to disappear or become inaccessible, while excessive stability may prevent the system from adapting to new tasks.

CMHH therefore investigates whether explicit management of heuristic knowledge can provide a better stability–plasticity trade-off than either independent heuristic search or naive forms of knowledge carryover.

---

### Continual Competence and the Three Capabilities

The goal of CMHH is to develop a continual learning system with three core capabilities:

**Retention**: After processing a task stream $\mathcal{T} = (T_1, \dots, T_K)$, if a previously learned task $T_j$ (where $j \le K$) is encountered again, the system must retain sufficient competence to solve it effectively **without performing full heuristic re-search from scratch**. This mirrors the expectation in classical continual learning that a final model should remain capable on previously learned tasks.

**Forward Transfer**: When encountering a novel task $T_{K+1}$, knowledge accumulated during prior task learning should reduce the cost of learning (fewer LLM calls, fewer evaluations, fewer generations, or faster search) or improve solution quality under a fixed computational budget, compared to learning from cold start.

**Backward Transfer**: Knowledge learned from later tasks may, though not mandatorily, improve the system's capability on earlier tasks. This is stronger than merely preserving old capabilities and represents true bidirectional learning.

To summarize CMHH's continual learning objective:

$$
\boxed{
\text{Retain previous competence} + \text{Reuse retained knowledge} + \text{Adapt to new tasks}
}
$$

---

## 2. Problem Definition

### 2.1 Sequential Combinatorial Optimization Setting

Let a continual optimization environment consist of an ordered task stream

$$
\mathcal{T} = (T_1, T_2, \dots, T_K),
$$

where each $T_k$ represents a combinatorial optimization task encountered at step $k$.

The system processes these tasks sequentially:

$$
T_1 \rightarrow T_2 \rightarrow \dots \rightarrow T_K.
$$

At task $T_k$, the heuristic-search system is allowed to search for and evaluate heuristics using information available from the current task and any knowledge legitimately retained from previous tasks.

After finishing $T_k$, the system proceeds to $T_{k+1}$ without revisiting the optimization process for earlier tasks except through explicitly defined evaluation procedures.

The key distinction from conventional heuristic search is therefore that the optimization process is not treated as a collection of independent runs. Instead, the internal state accumulated while solving previous tasks may influence how subsequent tasks are solved.

### 2.2 Definition of a Task

A task $T_k$ specifies an optimization environment under which candidate heuristics are generated, evaluated, and selected.

Conceptually, a task may be represented as

$$
T_k = (\mathcal{P}_k, \mathcal{D}_k, \mathcal{I}_k, \mathcal{E}_k),
$$

where:

- $\mathcal{P}_k$ denotes the combinatorial optimization problem definition;
- $\mathcal{D}_k$ denotes the distribution from which problem instances are generated or sampled;
- $\mathcal{I}_k$ denotes the instance-scale or structural characteristics of the task;
- $\mathcal{E}_k$ denotes the evaluation setting used to measure heuristic performance.

Two tasks may therefore belong to the same optimization problem while still differing in scale or instance distribution.

For example,

$$
T_1 = \text{TSP-20}, \qquad
T_2 = \text{TSP-50}, \qquad
T_3 = \text{TSP-100}
$$

form a task stream in which the underlying TSP formulation remains unchanged while problem scale increases.

### 2.3 Types of Task Shift

A transition

$$
T_k \rightarrow T_{k+1}
$$

may introduce one or more forms of change.

#### Scale shift

The underlying optimization problem and instance distribution remain approximately the same, while the size or complexity of the instances changes.

Example:

$$
\text{TSP-20}
\rightarrow
\text{TSP-50}
\rightarrow
\text{TSP-100}
\rightarrow
\text{TSP-200}.
$$

Scale shift tests whether heuristic knowledge discovered at one problem size remains useful as problem size changes.

#### Instance-distribution shift

The underlying optimization problem remains the same, but the distribution of problem instances changes.

For example, Euclidean TSP instances may change from uniformly distributed cities to clustered spatial distributions.

This setting tests whether the system can adapt previously acquired heuristic knowledge to a new region of the same problem space.

#### Problem-family shift

The underlying combinatorial optimization problem itself changes.

For example,

$$
\text{TSP}
\rightarrow
\text{CVRP}
\rightarrow
\text{OVRP}.
$$

Such transitions require substantially stronger knowledge transfer because objectives, constraints, state representations, or feasible-solution structures may change.

#### Composite shift

A task transition may combine multiple shifts simultaneously.

For example,

$$
\text{TSP-50, uniform}
\rightarrow
\text{CVRP-100, clustered}
$$

contains both a problem-family shift and changes in scale and instance distribution.

CMHH does not assume that all forms of shift are equally difficult or require the same type of transferable heuristic knowledge. Instead, task-shift severity is treated as an important property of the continual optimization environment.

### 2.4 Continual Heuristic Search

For each task $T_k$, let

$$
P_k
$$

denote the working population of candidate heuristics used by the evolutionary heuristic-search process.

A conventional independent-search system initializes a new population for every task:

$$
T_k \rightarrow P_k^{(0)}.
$$

No useful search state is intentionally transferred between tasks.

A continual heuristic-search system instead allows information discovered during previous tasks to influence the search process for \(T_k\).

The generic process can be represented as

$$
(T_k, P_k, M_{k-1})
\rightarrow
\text{Heuristic Search}
\rightarrow
(P_k^{*}, M_k),
$$

where:

- $P_k$ is the working heuristic population for the current task;
- $P_k^{*}$ is the population produced after search on $T_k$;
- $M_{k-1}$ denotes knowledge retained before entering $T_k$;
- $M_k$ denotes the retained knowledge state after processing $T_k$.

The exact definition and structure of $M_k$ are intentionally left open at this stage and will be specified in the **Knowledge Definition** and **Memory Definition** sections.

This distinction is important because a working population and a persistent memory need not represent the same thing.

### 2.5 Continual Competence

The goal of continual heuristic learning is not merely to accelerate search on the next task. Rather, after processing a sequence of tasks

$$
\mathcal{T} = (T_1, \dots, T_K),
$$

the system achieves a learned state that we conceptualize as a **continual problem-solving system**. This system must satisfy two complementary requirements:

#### Previously Learned Tasks

For a task $T_j$ where $j \le K$ that was previously encountered and learned, the system must retain sufficient competence to generate or select effective heuristic strategies **without re-running full evolutionary heuristic search from scratch**.

Conceptually:

$$
T_j \rightarrow \text{[Retrieve/select retained knowledge]} \rightarrow \text{Execute heuristic} \rightarrow \text{Good performance}
$$

This is the **retention** guarantee: the system should not require re-learning what it has already learned.

#### Novel and Related Tasks

For a task $T_{K+1}$ not previously seen, or a task $T^{\text{novel}}$ that shares structure with earlier tasks, prior knowledge should enable faster learning or better performance under a fixed budget, compared to cold-start heuristic search.

Conceptually:

$$
T^{\text{novel}} \rightarrow \text{[Retrieve relevant prior knowledge]} \rightarrow \text{Adapt/search} \rightarrow \text{Efficient learning}
$$

This is the **forward transfer** guarantee.

---

**Important Note**: CMHH does not require a single universal heuristic that solves all tasks equally well. Rather, the continual system is conceptualized as:

$$
\text{Continual system} = \text{Heuristic repertoire} + \text{Memory} + \text{Retrieval/selection mechanism} + \text{Adaptation capability}
$$

Task diversity is handled through effective organization, retrieval, and selective reuse of domain-specific or task-aware heuristics, not through a monolithic universal strategy.

### 2.6 Baseline Forms of Knowledge Continuity

Before defining a full memory-management mechanism, CMHH distinguishes several conceptually different ways in which information may persist across tasks. Each baseline represents a different trade-off with respect to **retained competence**, the ability to re-solve previously learned tasks efficiently.

#### Independent cold-start search

Each task is solved independently with no transfer of search state or learned knowledge:

$$
T_1 \rightarrow P_0, \quad T_2 \rightarrow P_0, \quad T_3 \rightarrow P_0
$$

No heuristic population or external heuristic memory is deliberately transferred between tasks.

This condition represents the absence of continual heuristic learning. However, if the system stores the final heuristic discovered for each task (forming a task-indexed heuristic library), this becomes a conceptual baseline:

$$
\text{Task ID} \rightarrow \text{Optimized heuristic}
$$

CMHH must demonstrate advantages over such simple task-indexed storage through:

1. **Reduced re-learning cost on seen tasks** (compared to rediscovering heuristics);
2. **Improved new-task adaptation** (through cross-task transfer rather than isolated search);
3. **Compressed reusable knowledge** (shared or generalized heuristic components rather than isolated specialists);
4. **Better generalization** (to related but previously unseen tasks).

#### Population carryover

The final heuristic population obtained on one task is used to initialize the search for the next task:

$$
P_k^{*} \rightarrow P_{k+1}^{(0)}.
$$

No separate persistent memory is required. Knowledge persists only in the current working population.

This creates a minimal form of knowledge continuity. Heuristics survive across task boundaries only if they remain competitive in the evolutionary population. However, once a task is finished, if the population is discarded or fully replaced, previously useful heuristics are lost.

**In terms of retained competence**: if task $T_j$ must be re-visited after several subsequent tasks, population carryover provides no guarantee that relevant heuristics are available. The system must re-search.

#### Persistent heuristic memory

The system maintains heuristic knowledge independently of the current working population:

$$
P_k^{*} \rightarrow M_k
$$

Knowledge from $M_k$ may later be retrieved to influence search on new tasks, or to rapidly reconstruct competence on previously learned tasks.

Persistent memory allows useful knowledge to survive beyond a single task's evolutionary process. This is necessary for retained competence: even if a heuristic is no longer in the active population, it can be retrieved and reused.

**However, persistence alone is insufficient.** As memory grows with more tasks, several challenges emerge:

- Irrelevant, outdated, or conflicting heuristics may interfere with retrieval and selection;
- The retrieval mechanism may fail to identify task-appropriate heuristics;
- Memory management and computational costs may become prohibitive.

This motivates the distinction between **naive persistent memory** (mere storage of all discovered heuristics) and **managed persistent memory** (with curation, organization, retrieval, and adaptation mechanisms designed to preserve functional competence while scaling to multiple tasks). CMHH investigates mechanisms for managed persistent memory, which will be formally defined in later sections.

### 2.7 The Continual Heuristic Learning Problem

The research problem studied by CMHH can therefore be stated as follows.

Given a sequence of combinatorial optimization tasks

$$
\mathcal{T}=(T_1,\dots,T_K),
$$

design a heuristic-search system that accumulates and organizes heuristic knowledge such that the final learned continual system achieves the following:

#### On Previously Learned Tasks

For a task $T_j$ ($j \le K$) that was previously encountered, the system must retain sufficient organized knowledge to effectively re-solve the task **without performing full evolutionary heuristic re-search from scratch**.

Concretely:

$$
T_j \rightarrow \text{Retrieve relevant competence from } M_K \rightarrow \text{Execute/adapt} \rightarrow \text{Good performance}.
$$

This avoids the cost of re-discovering heuristics that have already been learned.

#### On Novel or Related Tasks

For a new task $T_{K+1}$ or a previously unseen task structurally related to tasks in $\mathcal{T}$, knowledge accumulated during prior learning should enable faster or better adaptation compared to cold-start heuristic search:

$$
T_{K+1} \rightarrow \text{Retrieve transferable prior knowledge} \rightarrow \text{Adapt/search efficiently} \rightarrow \text{Faster/better learning}.
$$

This represents forward transfer of learned competence.

#### Avoiding Destructive Interference

The system must avoid harmful interference from obsolete, irrelevant, or conflicting heuristic knowledge that could degrade performance on any task (whether previously learned or new).

#### Scalability

Memory, retrieval, selection, and adaptation mechanisms must remain computationally and practically manageable as the task stream grows.

---

**Note on Computational Resources**

Continual heuristic learning offers computational benefits primarily at the level of **search and acquisition cost**, not necessarily at the level of heuristic execution:

- **Seen-task efficiency**: Reusing discovered heuristics avoids re-running LLM-based evolutionary search, reducing LLM calls, candidate evaluations, and generations needed to re-discover known strategies.
- **New-task efficiency**: Warm-starting heuristic search with transferable knowledge may reduce the search generations, evaluations, or wall-clock time required to reach a target performance on novel tasks.

CMHH makes no claim that continual memory reduces the computational cost of **executing** a heuristic during solving. The benefits are in **learning cost reduction** through knowledge reuse and transfer.

---

### Continual Learning Objective

The continual heuristic-learning objective can be summarized as:

$$
\boxed{
\text{Retain previously learned competence} \quad + \quad \text{Transfer knowledge to new tasks} \quad - \quad \text{Destructive interference}
}
$$

The concrete definitions of **heuristic knowledge**, **memory**, **forgetting**, **transfer**, **retrieval**, and **interference** are treated as first-class components of the CMHH formulation and are defined in the subsequent sections.

---

## 3. Memory Definition

To support both **retained competence** and **cross-task transfer**, CMHH adopts a structured hybrid memory representation that combines executable heuristic artifacts with contextual, semantic, and empirical information. **[CMHH-D1]**

This design is motivated by several complementary lines of prior work.

Hu et al. formulate external memory for continual LLM agents through a ((k,v)) framework that separates **how experience is represented** from **how it is organized for retrieval**. Their sequential-task experiments further show that abstract procedural memories can transfer more reliably than detailed task-specific trajectories, while memory organization and retrieval can themselves introduce forgetting and negative transfer. **[M1]**

ExpeL demonstrates that an LLM agent can accumulate experience, extract reusable knowledge in natural language, and recall both extracted insights and previous experiences at inference without updating the underlying model parameters. **[M2]**

Voyager provides a complementary perspective: rather than storing only textual knowledge, it maintains an ever-growing library of **executable code skills** that can be retrieved and directly reused to perform complex behaviors. **[M3]**

Taken together, these works motivate—but do not directly define—the CMHH memory representation. CMHH synthesizes these ideas for continual heuristic learning: executable artifacts support retained competence, while contextual and semantic representations support selective reuse and cross-task transfer. **[CMHH-D1]**

An executable heuristic is necessary for **retained competence**: when a previously encountered task reappears, the system should be able to retrieve and execute an already acquired heuristic rather than performing the complete evolutionary search again.

However, executable code alone does not explicitly encode when the heuristic is applicable, why it is useful, or which underlying principles may generalize to related but different tasks. Supporting **cross-task transfer** therefore motivates additional contextual and semantic representations. This is a CMHH design inference grounded in the complementary evidence from executable skill libraries and abstract experience reuse. **[M1, M2, M3; CMHH-D1]**

The memory representation is consequently designed around four functional requirements:

1. preserve executable problem-solving competence;
2. support selective retrieval under changing task contexts;
3. expose transferable knowledge beyond the task on which a heuristic was discovered;
4. retain sufficient empirical evidence to support later memory-management decisions.

These requirements are specific to the CMHH problem formulation rather than being inherited as a complete architecture from any single prior work. **[CMHH-D1]**

### 3.1 Memory Representation

CMHH represents each long-term memory item as

$$
m_i = (h_i, k_i, z_i, \mu_i),
$$

where:

* $h_i$ is the **executable heuristic artifact**, preserving directly reusable problem-solving competence;
* $k_i$ is the **applicability and retrieval descriptor**, describing the task, instance, or search contexts in which the heuristic is expected to be relevant;
* $z_i$ is the **semantic or procedural abstraction**, capturing reusable principles, rationale, behavioral characteristics, or adaptation knowledge associated with the heuristic;
* $\mu_i$ is the **empirical and lifecycle metadata**, including provenance, observed performance, usage history, confidence, and other evidence that may support memory-management decisions.

The complete tuple

$$
m_i=(h_i,k_i,z_i,\mu_i)
$$

is a **CMHH-specific structured memory representation**. No cited prior work is claimed to use this exact tuple. **[CMHH-D1]**

Its components are motivated by different prior findings:

| Component                      | Primary role                                   | Research basis                                                 |
| ------------------------------ | ---------------------------------------------- | -------------------------------------------------------------- |
| Executable heuristic $h_i$     | Preserve competence without full re-search     | Executable skill libraries **[M3]**                            |
| Applicability descriptor $k_i$ | Support selective retrieval                    | Representation/retrieval separation **[M1]**                   |
| Semantic abstraction $z_i$     | Support generalization and cross-task transfer | Abstract procedural memory and extracted insights **[M1, M2]** |
| Empirical metadata $\mu_i$     | Support evidence-based memory management       | **CMHH-specific requirement [CMHH-D1]**                        |

The long-term memory after processing task $T_k$ is represented as

$$
M_k = {m_i}_{i=1}^{N_k}.
$$

The representation is intentionally hybrid because no single stored form naturally satisfies all continual heuristic-learning requirements. Executable artifacts preserve acquired capabilities, whereas contextual and semantic representations make those capabilities easier to selectively reuse beyond the task on which they were originally discovered. **[M1, M2, M3; CMHH-D1]**

This representation should be interpreted as the **minimal functional memory structure used by CMHH**, rather than as a claim that it is universally optimal among possible agent-memory architectures. **[CMHH-D1]**

More complex organizations such as hierarchical, graph-based, or multi-store memory remain possible extensions. Prior work on modular continual memory explicitly argues that memory representations and organizations involve different trade-offs and that no single representation is universally suitable. **[M4]**

### 3.2 Memory Scope and Persistence

CMHH distinguishes between **working search state** and **long-term continual memory**.

This separation is consistent with modular memory formulations that distinguish transient, capacity-limited working memory from persistent long-term memory used for knowledge accumulation and later retrieval. **[M4]**

In CMHH, however, these concepts are instantiated specifically for evolutionary heuristic search:

* the **working search state** contains the current evolutionary population, retrieved knowledge, and task-local search context;
* the **long-term memory** $M_k$ stores persistent heuristic knowledge across task boundaries.

This mapping from modular memory concepts to evolutionary heuristic search is specific to CMHH. **[M4; CMHH-D2]**

Conceptually,

$$
\text{Working State}_k \neq M_k.
$$

The evolutionary population used while solving the current task is transient. Candidate heuristics may be introduced, modified, selected, or removed throughout the search.

Long-term memory $M_k$, in contrast, persists beyond the current evolutionary process.

Population carryover therefore provides a minimal form of cross-task continuity but is not equivalent to the persistent long-term memory considered by CMHH. **[CMHH-D2]**

This distinction enables two forms of reuse:

* for a **previously encountered task**, retained knowledge may be retrieved and directly reused without full evolutionary re-search;
* for a **novel task**, relevant prior knowledge may be retrieved to support initialization, reasoning, or adaptation.

**[CMHH-D2]**

### 3.3 Memory Capacity

CMHH assumes that long-term memory is **bounded**. **[CMHH-D3]**

Let $C$ denote the maximum number of persistent memory items:

$$
|M_k| = N_k \leq C.
$$

Bounded episodic memory is a standard experimental assumption in continual-learning research. Work on tiny episodic memories explicitly studies continual learning under fixed, small memory and limited-compute constraints, emphasizing that finite memory forces decisions about which past information should be retained. **[M5]**

CMHH adopts the same high-level resource principle but applies it to **heuristic knowledge items rather than training examples**. The exact item-bounded formulation above is therefore a CMHH design choice. **[M5; CMHH-D3]**

A bounded memory introduces a resource-allocation problem:

$$
\text{new knowledge}
\rightarrow
\text{finite capacity}
\rightarrow
\text{retention decisions}.
$$

As new knowledge is acquired, the system must eventually decide what deserves persistent capacity and what may be removed, replaced, or consolidated. **[CMHH-D3]**

The initial CMHH formulation uses the **number of memory items** as the primary capacity constraint. Token count, code size, or actual storage footprint may additionally be measured as efficiency metrics but are not part of the core capacity definition. **[CMHH-D3]**

#### Capacity–Retrieval Trade-off

Memory capacity and retrieval capability are not independent.

Hu et al. show that, under limited context, old and new experiences can compete during retrieval, moving part of the continual-learning bottleneck from parameter updates to memory access. They also show that finer-grained memory organization is not universally beneficial and can improve forward transfer while simultaneously increasing forgetting. **[M1]**

The modular-memory perspective similarly identifies retrieval cost and memory capacity as distinct design properties and notes that retrieval cost for slot-based memories can increase with the number of stored items. **[M4]**

These observations motivate the following CMHH hypothesis:

$$
|M_k| \uparrow
\quad\Rightarrow\quad
\begin{cases}
\text{potential retained knowledge} \uparrow,\
\text{retrieval difficulty may increase}.
\end{cases}
$$

The equation is **not a theorem imported from prior work**; it is a CMHH conceptual hypothesis motivated by the observed interaction between memory growth, context limitation, and retrieval competition. **[M1, M4; CMHH-D4]**

CMHH therefore treats memory effectiveness as a balance between **retention capacity** and **retrieval selectivity**, rather than assuming that storing more knowledge necessarily creates a better continual system. **[CMHH-D4]**

### 3.4 Retrieval Definition

Storage alone does not constitute usable memory.

Prior work on memory-based continual LLM agents demonstrates that memory representation and retrieval organization jointly affect transfer and forgetting. **[M1]**

Modular memory formulations likewise model long-term knowledge as being selectively retrieved into a transient working context. **[M4]**

CMHH formalizes this for heuristic knowledge as follows.

Let $q$ denote a retrieval query derived from the current task, instance, search state, or other available context. A retrieval mechanism $R$ maps the query and long-term memory to a selected subset:

$$
R(q,M_k)=M_k^{(q)},
$$

where

$$
M_k^{(q)}\subseteq M_k.
$$

Typically,

$$
|M_k^{(q)}| \ll |M_k|.
$$

This mathematical formulation is specific to CMHH. **[CMHH-D5]**

It separates:

$$
\text{memory capacity}
\neq
\text{retrieval set size}
\neq
\text{active context size}.
$$

A memory item may therefore remain physically stored while being functionally unavailable because it is not retrieved when relevant.

This possibility is consistent with the broader observation that external memory can relocate continual-learning failure from parameter interference to memory access and retrieval competition. **[M1]**

CMHH uses this observation to motivate the concepts of **retrieval-side interference** and potentially **functional forgetting without storage loss**. Their exact definitions and evaluation criteria are specified separately. **[M1; CMHH-D5]**

At this stage, retrieval is defined only by its functional role. The specific query representation, embedding model, similarity function, ranking algorithm, top-$k$ policy, or learned retriever remains outside the Memory Definition.

### 3.5 Memory Operations

Modular-memory literature treats persistent memory as an active component supporting operations such as retrieval, updating, forgetting, and consolidation rather than as a passive archive. **[M4]**

CMHH adopts this general principle and specializes the operation set for continual heuristic knowledge. **[CMHH-D6]**

At the conceptual level, CMHH distinguishes:

**Write**
Introduce newly acquired heuristic knowledge into persistent memory.

**Retrieve**
Select knowledge relevant to the current task or search context.

**Update**
Revise contextual, semantic, or empirical information as new evidence becomes available.

**Consolidate**
Combine or summarize overlapping or redundant knowledge.

**Protect**
Prevent knowledge judged important from being removed during later memory updates.

**Evict**
Remove knowledge when capacity must be reallocated.

Retrieval, updating, forgetting, and consolidation have clear precedents in modular-memory frameworks. **[M4]**

The exact inclusion and semantics of **Protect**, and the way these operations act on structured heuristic items, are CMHH-specific design choices. **[CMHH-D6]**

The existence of these operations does not imply a particular algorithm for performing them. Their concrete policies belong to the later memory-management/Archivist design.

### 3.6 Scope of the Memory Definition

This section defines:

* what persistent memory means in CMHH;
* what information a memory item contains;
* the distinction between working and long-term memory;
* the assumption of bounded capacity;
* the functional meaning of retrieval;
* the set of operations that a memory-management mechanism may perform.

It intentionally does **not** define the concrete retrieval, consolidation, protection, or eviction algorithms.

---

## 3.7 Research Traceability Notes

### [M1] Hu et al. — *When Continual Learning Moves to Memory*

**Used for:**

* the ((k,v)) abstraction separating representation and retrieval organization;
* evidence that abstract procedural memory may transfer more reliably than detailed trajectories;
* evidence that memory organization can affect both forward transfer and forgetting;
* the idea that limited context causes old and new experiences to compete during retrieval;
* motivation for treating retrieval-side interference as a continual-learning problem.

**Not inherited directly:**

* CMHH's $(h,k,z,\mu)$ representation;
* CMHH's bounded item capacity;
* CMHH's heuristic-specific retrieval function;
* Archivist operations.

**Status:** empirical preprint / work in progress.

### [M2] Zhao et al. — *ExpeL: LLM Agents Are Experiential Learners*

**Used for:**

* precedent for extracting reusable natural-language knowledge from accumulated agent experiences;
* reuse of extracted insights and experiences at inference without parameter updates;
* motivation for semantic/procedural knowledge $z_i$.

**Not inherited directly:**

* executable heuristic memory;
* CMHH retrieval schema;
* CMHH memory-management mechanism.

### [M3] Wang et al. — *Voyager: An Open-Ended Embodied Agent with Large Language Models*

**Used for:**

* precedent for maintaining an executable code skill library;
* direct storage and retrieval of executable competence;
* motivation for $h_i$ as an executable artifact rather than storing semantic insight alone.

**Not inherited directly:**

* CMHH's structured hybrid item;
* bounded memory;
* explicit continual retention–retrieval trade-off.

### [M4] Dorovatas et al. — *Position: Modular Memory is the Key to Continual Learning Agents*

**Used for:**

* distinction between transient working memory and persistent long-term memory;
* view of memory as actively managed rather than passive storage;
* retrieval, updating, forgetting, and consolidation as memory functions;
* multiple representational forms such as experiences, abstractions, and skills;
* capacity/retrieval/generalization as separate memory-design properties;
* motivation for treating memory design as a collection of trade-offs rather than assuming one representation is universally optimal.

**Important:** this is primarily a **position/conceptual paper**, so these points should be cited as architectural framing rather than empirical proof.

### [M5] Chaudhry et al. — *On Tiny Episodic Memories in Continual Learning*

**Used for:**

* precedent for studying continual learning under fixed, small memory budgets;
* motivation for treating finite memory as part of the continual-learning problem rather than allowing unlimited storage;
* precedent for evaluating behavior as memory size changes.

**Not inherited directly:**

* CMHH stores heuristic knowledge rather than replay examples;
* CMHH's capacity unit $C$ is a design choice.

---

## 3.8 CMHH Design Decisions

### [CMHH-D1] Structured hybrid heuristic memory

$$
m_i=(h_i,k_i,z_i,\mu_i)
$$

This is a CMHH synthesis motivated by complementary requirements and prior work; it is not copied from one existing architecture.

### [CMHH-D2] Population vs persistent memory

The evolutionary population is treated as working search state, while $M_k$ represents persistent continual knowledge.

### [CMHH-D3] Item-bounded memory

$$
|M_k|\le C
$$

CMHH initially measures capacity by the number of structured memory items.

### [CMHH-D4] Capacity–retrieval trade-off

Increasing persistent capacity may improve potential retention but may also increase retrieval difficulty.

This is currently a **research hypothesis/design motivation**, not an established law.

### [CMHH-D5] Heuristic retrieval abstraction

$$
R(q,M_k)=M_k^{(q)}
$$

defines retrieval functionally without committing to a particular retrieval algorithm.

### [CMHH-D6] Heuristic-memory operation set

CMHH specializes general memory-management ideas into:

$$
{\text{write, retrieve, update, consolidate, protect, evict}}.
$$

Concrete policies remain open.

---

## References

**[M1]** Hu, Q., Long, Q., & Wang, W. (2026). *When Continual Learning Moves to Memory: A Study of Experience Reuse in LLM Agents*. arXiv:2604.27003.

**[M2]** Zhao, A., Huang, D., Xu, Q., Lin, M., Liu, Y.-J., & Huang, G. (2024). *ExpeL: LLM Agents Are Experiential Learners*. Proceedings of the AAAI Conference on Artificial Intelligence. arXiv:2308.10144.

**[M3]** Wang, G., Xie, Y., Jiang, Y., Mandlekar, A., Xiao, C., Zhu, Y., Fan, L., & Anandkumar, A. (2023). *Voyager: An Open-Ended Embodied Agent with Large Language Models*. arXiv:2305.16291.

**[M4]** Dorovatas, V., Schwerin, M., Bagdanov, A. D., et al. (2026). *Position: Modular Memory is the Key to Continual Learning Agents*. ICML 2026 Position Track. arXiv:2603.01761.

**[M5]** Chaudhry, A., Rohrbach, M., Elhoseiny, M., Ajanthan, T., Dokania, P. K., Torr, P. H. S., & Ranzato, M. (2019). *On Tiny Episodic Memories in Continual Learning*. arXiv:1902.10486.


# Research Questions and Hypotheses

## Primary Research Question

**RQ:** Can an LLM-based continual heuristic-search system acquire, retain, and reuse heuristic knowledge across a sequential stream of combinatorial optimization tasks, while avoiding destructive interference and remaining capable of efficient adaptation to new tasks?

This question concerns the continual competence of the overall heuristic-search system rather than continual adaptation of the underlying LLM parameters. In particular, CMHH investigates whether persistent heuristic knowledge can support both **retention of previously acquired capabilities** and **transfer to future tasks** under a non-stationary task stream.

## RQ1 — Does continual heuristic search exhibit functional forgetting?

When heuristic knowledge is carried across tasks without explicit protection or management, does retained competence on previously learned tasks degrade as the task stream progresses?

**H1:** Sequential knowledge-continuity baselines, such as population carryover or naive persistent memory, will exhibit measurable functional forgetting and/or harmful interference as the task stream grows.

Such degradation may arise through multiple mechanisms:

- previously useful heuristic knowledge may be physically removed or replaced;
- useful knowledge may remain stored but become difficult to retrieve;
- irrelevant or conflicting memories may interfere with selection or adaptation;
- the active search population may progressively lose competence required by earlier tasks.

The hypothesis therefore concerns **loss of accessible problem-solving capability**, rather than storage loss alone.

---

## RQ2 — Can managed persistent memory improve the stability–plasticity trade-off?

Does explicitly managed heuristic memory preserve previously acquired competence more effectively than naive knowledge persistence while maintaining the ability to adapt to new tasks?

**H2:** A managed persistent-memory mechanism that selectively stores, organizes, retrieves, updates, protects, consolidates, and evicts heuristic knowledge will reduce functional forgetting and retrieval-side interference relative to naive persistent memory under comparable memory and search budgets.

This improvement should not come at the cost of substantially reduced performance or adaptation efficiency on newly encountered tasks.

The proposed **Archivist** is CMHH's implementation of this managed-memory mechanism rather than part of the research question itself.

---

## RQ3 — When does previously acquired heuristic knowledge enable forward transfer?

To what extent can heuristic knowledge learned from earlier tasks improve adaptation to later tasks, and how does this effect depend on the type and severity of task shift?

CMHH considers transfer across:

- increasing problem scale;
- changes in instance distribution;
- changes in optimization problem family;
- combinations of these shifts.

**H3:** Prior heuristic knowledge will provide positive forward transfer when successive tasks share sufficiently reusable structure, yielding either better solution quality under a fixed search budget or lower search cost required to reach a comparable level of performance.

The magnitude of transfer is expected to decrease as structural distance between tasks increases, although this is an empirical question rather than an assumption of the framework.

---

## Secondary RQ — How does task ordering affect continual heuristic learning?

Holding the memory mechanism and computational budget fixed, does the ordering of tasks affect retention, interference, and forward transfer?

**H4:** Task streams that introduce structurally related tasks in a coherent order, such as increasing problem size or adjacent related problem families, will exhibit stronger forward transfer and/or less destructive interference than randomly ordered streams.

This hypothesis treats curriculum as a property of the continual environment rather than as a requirement of the core CMHH mechanism.

---

These hypotheses are deliberately falsifiable. CMHH does not require that functional forgetting, positive transfer, or curriculum effects must occur.

For example, if naive persistent heuristic memory exhibits little or no functional forgetting, this would indicate that explicit symbolic heuristic knowledge may possess substantially different continual-learning properties from parameter-based neural representations. Likewise, if managed memory provides no advantage over simple persistence, or if task ordering has negligible effect, these outcomes remain informative results rather than failures of the experimental framework.


## 5. Evaluation Framework

### 5.1 Evaluation Objectives

The evaluation of CMHH is designed to determine whether a continual LLM-based heuristic-search system can:

1. retain previously acquired problem-solving competence;
2. avoid functional forgetting and destructive interference as the task stream grows;
3. reuse previously acquired heuristic knowledge to improve adaptation to future tasks;
4. benefit from explicit memory management under bounded capacity;
5. remain robust to task ordering and different forms of task shift;
6. achieve these properties without relying on unconstrained memory or substantially greater computational resources.

The evaluation therefore combines three complementary perspectives:

$$
\boxed{
\text{End-to-End Continual Competence}
+
\text{Transfer and Learning Efficiency}
+
\text{Memory/Retrieval Diagnostics}
}
$$

End-to-end problem-solving performance is treated as the **primary evidence**. Memory and retrieval metrics are used as **diagnostic evidence** to explain why competence is retained, transferred, or lost.

This distinction is important because successful storage or retrieval does not necessarily imply successful problem solving. Conversely, a performance degradation cannot automatically be attributed to memory deletion without determining whether the relevant knowledge remains stored but inaccessible.

The evaluation framework is informed by continual-learning evaluation protocols introduced by GEM and A-GEM, broader continual-learning evaluation criteria, long-term LLM-memory benchmarks, and quality–efficiency evaluation practices in LLM-based automatic heuristic design [R1–R9].

---

### 5.2 Evaluation Principles

All experiments should follow the following principles.

#### 5.2.1 Sequential integrity

Tasks are processed strictly in the order defined by the task stream:

$$
\mathcal{T}=(T_1,T_2,\dots,T_K).
$$

When processing $T_k$, the learning system may access only:

* the current task;
* the current search state;
* knowledge legitimately retained from $T_1,\dots,T_{k-1}$.

Knowledge derived from future tasks must never influence learning at $T_k$.

Evaluation code may evaluate the current system on held-out tasks for measurement purposes, but these evaluation results must not be exposed to the learner or used to update memory.

---

#### 5.2.2 No full re-search during retention evaluation

A previously learned task must be evaluated using the system's **current retained competence**, rather than by rerunning the complete evolutionary heuristic-search procedure.

For an earlier task $T_j$, where $j < k$, retention evaluation should follow:

```text
T_j
 ↓
retrieve/select retained knowledge
 ↓
execute retained heuristic or permitted lightweight deployment procedure
 ↓
evaluate
```

and not:

```text
T_j
 ↓
restart evolutionary heuristic search
 ↓
rediscover a heuristic
 ↓
evaluate
```

Otherwise, the experiment would measure **relearning ability** rather than **retained competence**.

Unless explicitly stated as a separate experiment, retention probes must therefore:

* disable evolutionary search;
* disable generation of new heuristic candidates;
* disable memory writes and updates;
* use the same retrieval and selection policy available to the deployed continual system.

---

#### 5.2.3 Matched resource budgets

Comparisons between methods must use comparable computational budgets.

At minimum, experiments should control or report:

* number of expensive candidate evaluations;
* number of LLM calls;
* total input tokens;
* total output tokens;
* number of evolutionary generations;
* wall-clock runtime.

The **candidate-evaluation budget** is the preferred primary search-budget axis because it directly controls the amount of empirical optimization performed.

LLM token consumption must additionally be reported because memory-augmented methods may require longer prompts even when the number of LLM calls remains unchanged.

Where possible, two complementary comparisons should be reported:

1. **matched evaluator budget**, where methods receive the same number of candidate evaluations;
2. **cost-aware comparison**, where token usage and wall-clock time are measured alongside final quality.

This follows the general quality–efficiency perspective used in LLM-based automatic heuristic design, including EoH and HMACE [R7, R9].

---

#### 5.2.4 Bounded memory

The primary continual-memory experiments assume a maximum memory capacity:

$$
|M_k| \leq C.
$$

The default capacity unit is the **number of persistent memory items**, consistent with the CMHH memory definition.

Because different memory items may have different sizes, the following should additionally be logged:

* total stored tokens;
* serialized memory size;
* number of executable heuristic artifacts;
* active retrieval-context size.

Memory capacity $C$, retrieval size $k_r$, and active context budget must be reported separately.

---

#### 5.2.5 Test-set isolation

Each task should use fixed data partitions with distinct purposes.

```text
Train
  ↓
heuristic search / candidate generation

Validation
  ↓
candidate selection
hyperparameter selection
memory-policy configuration
retrieval-threshold configuration

Test
  ↓
final continual evaluation only
```

The test split must not be used for:

* heuristic generation;
* evolutionary fitness optimization;
* hyperparameter tuning;
* choosing memory capacity;
* choosing retrieval top-$k$;
* defining retrieval relevance labels;
* determining curriculum order.

A-GEM explicitly separates hyperparameter-selection tasks from the final lifelong-learning evaluation stream to avoid repeatedly tuning on the final evaluation experience [R2]. CMHH adopts the same principle at the task and instance level.

---

### 5.3 Optimization Performance Representation

Continual-learning metrics such as BWT and FWT require all task-performance values to have a consistent direction:

$$
\text{higher score} = \text{better performance}.
$$

Raw combinatorial-optimization objectives may differ substantially across tasks and problem families, and therefore should not be directly averaged.

#### 5.3.1 Relative reference gap

For a minimization problem:

$$
g(h,T) = \frac{f(h,T) - f^{\text{ref}}(T)}{\max(|f^{\text{ref}}(T)|, \epsilon)}.
$$

For a maximization problem:

$$
g(h,T) = \frac{f^{\text{ref}}(T) - f(h,T)}{\max(|f^{\text{ref}}(T)|, \epsilon)}.
$$

Lower gap is better.

The corresponding continual-learning performance score is defined as:

$$
S(h,T) = -g(h,T).
$$

Therefore:

$$
S \uparrow \quad\Longleftrightarrow\quad \text{better optimization performance}.
$$

The original gap should still be reported in percentage form because it remains the most interpretable optimization-quality measure.

If $f^{\text{ref}}$ is proven optimal, the quantity may be described as an **optimality gap**.

If $f^{\text{ref}}$ is only the best-known solution, it must instead be described as a **reference gap** or **best-known gap**, and no optimality claim should be made.

---

### 5.4 Core Continual Evaluation Protocol

For every task $T_k$, CMHH performs three conceptually separate stages.

```text
             ┌───────────────────────┐
             │ State after T_{k-1}   │
             │      M_{k-1}          │
             └──────────┬────────────┘
                        │
                        ▼
              A. Pre-learning Probe
                        │
                        ▼
              B. Learn/Search T_k
                        │
                        ▼
                   M_k
                        │
                        ▼
              C. Retention Probe
                 on T_1 ... T_k
```

These stages separate:

* competence available **before learning the new task**;
* learning and adaptation on the current task;
* competence retained on previously encountered tasks.

---

### 5.4.1 Stage A — Pre-learning Transfer Probe

Before performing evolutionary search on $T_k$, the current continual state $M_{k-1}$ is queried using the new task.

```text
T_k
 ↓
current continual state M_{k-1}
 ↓
retrieve/select
 ↓
execute directly applicable retained competence
 ↓
pre-learning performance Z_k
```

No new evolutionary search is allowed.

No memory update is allowed.

No heuristic discovered using information from $T_k$ may be added before the probe is completed.

Let

$$
Z_k
$$

denote the pre-learning performance score on $T_k$.

This probe measures **zero-shot forward transfer** when previously retained competence can be directly executed on the new task.

##### Applicability limitation

Direct zero-shot evaluation is meaningful only when retained heuristic artifacts are executable under the new task interface.

This is naturally applicable to transitions such as:

* TSP-20 $\rightarrow$ TSP-50;
* uniform TSP $\rightarrow$ clustered TSP;
* other scale or distribution shifts preserving the heuristic interface.

For problem-family transitions where executable interfaces differ substantially, such as:

$$
\text{TSP} \rightarrow \text{CVRP},
$$

direct execution may be undefined.

CMHH must **not artificially force a zero-shot score in such cases**.

Instead, forward transfer for incompatible problem-family shifts should primarily be evaluated through **adaptation efficiency under a matched search budget**, as defined in Section 5.7.

---

### 5.4.2 Stage B — Current-task Learning

After the pre-learning probe, the system performs its normal heuristic-search procedure on $T_k$.

Conceptually:

$$
(T_k, M_{k-1}) \rightarrow \text{heuristic search} \rightarrow M_k.
$$

During this stage, the experiment records the best available performance as a function of search budget:

$$
S_k(b),
$$

where $b$ denotes the consumed search budget.

Typical checkpoints may correspond to:

* candidate evaluations;
* generations;
* LLM calls;
* cumulative tokens.

The primary budget axis should remain fixed across methods within a given experiment.

These search trajectories are later used to measure adaptation speed and forward transfer.

---

### 5.4.3 Stage C — Retention Probe

After learning $T_k$, the current continual system is evaluated on every previously encountered task:

$$
T_1, \dots, T_k.
$$

For each $T_j$, the system must solve the task using its current retained state $M_k$, without full evolutionary re-search.

This produces a continual performance matrix.

---

### 5.5 Continual Performance Matrix

Let:

$$
A_{k,j}
$$

denote the test performance score on task $T_j$ after the system has processed tasks:

$$
T_1, \dots, T_k.
$$

For already encountered tasks:

$$
j \leq k.
$$

The matrix is therefore:

$$
A = \begin{bmatrix}
A_{1,1} & & & & \\
A_{2,1} & A_{2,2} & & & \\
A_{3,1} & A_{3,2} & A_{3,3} & & \\
\vdots & \vdots & \vdots & \ddots & \\
A_{K,1} & A_{K,2} & A_{K,3} & \dots & A_{K,K}
\end{bmatrix}.
$$

For example:

$$
A_{4,1}
$$

answers:

> After learning $T_1, T_2, T_3, T_4$, how well can the current continual system still solve $T_1$ without full heuristic re-search?

This matrix is the primary sufficient statistic for evaluating retained continual competence.

The formulation is adapted from the task-performance matrix introduced by GEM [R1], but the interpretation changes from neural-model prediction accuracy to **system-level heuristic problem-solving competence**.

---

### 5.5.1 Final Average Performance

After the complete task stream:

$$
\text{AP}_K = \frac{1}{K} \sum_{j=1}^{K} A_{K,j}.
$$

This measures the average final competence of the continual system across all encountered tasks.

Higher is better.

AP should not be interpreted as a forgetting metric by itself. Two systems may achieve similar AP while exhibiting very different retention and transfer behavior.

---

## 5.6 Evaluation of RQ1 — Functional Forgetting

### RQ1

> Does continual heuristic search exhibit functional forgetting?

The evaluation of RQ1 must determine both:

1. **whether previously acquired competence degrades**;
2. **why that degradation occurs**.

The first question is answered using end-to-end continual metrics.

The second is investigated using memory and retrieval diagnostics.

---

### 5.6.1 Backward Transfer

Following the GEM formulation [R1], final backward transfer is:

$$
\text{BWT}_K = \frac{1}{K-1} \sum_{j=1}^{K-1} (A_{K,j} - A_{j,j}).
$$

Interpretation:

$$
\text{BWT}_K > 0
$$

indicates positive backward transfer;

$$
\text{BWT}_K \approx 0
$$

indicates approximate preservation;

$$
\text{BWT}_K < 0
$$

indicates negative backward transfer.

A negative BWT provides evidence that learning later tasks has degraded competence on previously learned tasks.

However, BWT compares final performance primarily against performance immediately after each task was learned. It therefore does not fully capture situations where a task improves temporarily and is forgotten later.

Average Forgetting is included for that purpose.

---

### 5.6.2 Average Forgetting

For an earlier task $T_j$, define its best post-learning performance before the final state as:

$$
A^{\text{best}}_{j,K} = \max_{l \in \{j, \dots, K-1\}} A_{l,j}.
$$

Task-specific forgetting is:

$$
F_j^{(K)} = A^{\text{best}}_{j,K} - A_{K,j}.
$$

Average forgetting is:

$$
F_K = \frac{1}{K-1} \sum_{j=1}^{K-1} F_j^{(K)}.
$$

Lower is better.

This formulation is adapted from the forgetting measure used in A-GEM [R2], with the CMHH-specific restriction that the historical maximum is considered after task $T_j$ has actually been encountered.

This avoids treating pre-learning zero-shot competence as the task's learned reference point.

---

### 5.6.3 Worst-case Forgetting

Average forgetting may hide severe degradation on a small subset of tasks.

Therefore CMHH additionally reports:

$$
F^{\text{worst}}_K = \max_{j < K} F_j^{(K)}.
$$

This metric answers:

> What is the largest loss of previously acquired competence experienced anywhere in the stream?

---

### 5.6.4 Retention Trajectories

For important tasks, particularly early tasks, the complete trajectory should also be reported:

$$
A_{j,j}, A_{j+1,j}, \dots, A_{K,j}.
$$

For example:

```text
Performance on T_1
↑
│ ●
│   ●
│      ●
│          ●
│             ●
└────────────────────→ tasks learned
  T1  T2  T3  T4  T5
```

This makes it possible to distinguish:

* gradual forgetting;
* abrupt interference;
* temporary degradation followed by recovery;
* positive backward transfer.

---

### 5.6.5 Diagnosing Storage vs Retrieval Failure

A decrease in $A_{k,j}$ is evidence of **functional forgetting**, but does not by itself reveal the mechanism.

CMHH therefore distinguishes:

```text
previous competence degraded
          │
          ▼
is useful knowledge still stored?
     /                  \
   no                    yes
   │                      │
   ▼                      ▼
storage loss       was it retrieved?
                        /      \
                      no        yes
                      │          │
                      ▼          ▼
                 retrieval      downstream
                 failure        selection/use failure
```

The following diagnostics may be used.

#### Memory competence coverage

For each previously encountered task $T_j$, determine whether the current memory still contains at least one memory item whose validation-set utility exceeds a predefined threshold.

This produces a task-level competence-coverage indicator:

$$
\text{Coverage}_{k,j} \in \{0,1\}.
$$

The threshold must be chosen on validation data and fixed before test evaluation.

---

### 5.6.6 Retrieval Relevance

Unlike QA memory benchmarks, CMHH does not naturally provide human-annotated labels saying which memory item is relevant to each optimization task.

Retrieval relevance must therefore be defined empirically and **without using test data**.

For a memory item $m_i$ and task $T_j$, define a validation-based relevance value:

$$
r_{i,j} = \text{Utility}(m_i, T_j; \mathcal{D}^{\text{val}}_j).
$$

Depending on the memory representation, this utility may be derived from:

* performance of the executable heuristic $h_i$;
* performance after a fixed, predefined lightweight adaptation operator;
* another validation-only empirical measure defined before final evaluation.

The test set must never be used to construct $r_{i,j}$.

Given these relevance labels, CMHH may report:

#### Recall@$k_r$

The fraction of empirically relevant memory items appearing in the retrieved top-$k_r$.

#### NDCG@$k_r$

A ranking-sensitive metric that rewards placing high-utility memory items near the top of the retrieved set.

LongMemEval similarly separates intermediate memory retrieval from downstream task outcome and reports Recall@$k$ and NDCG@$k$ when relevance annotations are available [R4].

These metrics are **diagnostic**, not substitutes for end-to-end optimization performance.

---

### 5.6.7 Validation-Oracle Retrieval

To separate retrieval failure from absence of useful knowledge, CMHH should include a diagnostic oracle where feasible.

The oracle selects memory items using **validation-set relevance only**:

$$
M^{\text{oracle}}_j = \text{TopK}_{m_i \in M_k} r_{i,j}.
$$

Both the actual retrieval result and validation-oracle retrieval result are then evaluated on the same test instances.

Define retrieval regret:

$$
RR_{k,j} = A^{\text{oracle}}_{k,j} - A^{\text{actual}}_{k,j}.
$$

Interpretation:

* large $RR$: useful knowledge exists, but retrieval/selection fails to access it;
* small $RR$ combined with poor performance: the required competence may no longer exist in memory, or the stored knowledge itself is insufficient.

The oracle must never choose items using test performance.

It is an **analysis tool**, not a deployable baseline.

---

### 5.6.8 Controlled Memory-Pollution Experiment

A targeted experiment should isolate retrieval-side interference from physical memory deletion.

Procedure:

1. select a task $T_j$ with known useful retained knowledge;
2. ensure the useful memory item remains permanently stored;
3. progressively add unrelated or competing memory items;
4. keep retrieval top-$k_r$ and active context size fixed;
5. repeatedly query the original task;
6. measure retrieval quality and downstream performance.

Conceptually:

```text
useful H_j remains stored
        +
increasing distractor memories
        ↓
retrieve for T_j
        ↓
Recall@k / NDCG@k
        ↓
end-to-end performance
```

The main independent variable is memory load:

$$
|M|.
$$

The experiment examines:

$$
|M| \rightarrow \text{Recall}@k_r
$$

and:

$$
|M| \rightarrow A(T_j).
$$

If the useful artifact remains stored while retrieval quality and task performance degrade, this provides direct evidence of **retrieval-side functional interference** rather than storage forgetting.

An unbounded append-only memory condition is particularly useful for this diagnostic because it removes eviction as an alternative explanation.

---

## 5.7 Evaluation of RQ2 — Managed Persistent Memory

### RQ2

> Can managed persistent memory improve the stability–plasticity trade-off?

The primary comparison is:

```text
Naive bounded persistent memory
                vs
Managed persistent memory / Archivist
```

The comparison must isolate memory management as closely as possible.

---

### 5.7.1 Matched Experimental Conditions

The following should be identical unless they are themselves the mechanism being tested:

* task stream;
* task instances;
* LLM;
* heuristic-search algorithm;
* random seeds;
* search budget;
* memory capacity ($C$);
* retrieval set size ($k_r$);
* evaluation instances;
* maximum active context budget.

Any additional LLM calls or tokens consumed by memory management must be logged rather than treated as free computation.

---

### 5.7.2 Stability

Stability is measured primarily through:

$$
F_K, \qquad \text{BWT}_K, \qquad \text{AP}_K.
$$

Managed memory supports H2 if it reduces forgetting and/or improves retained competence relative to naive memory under matched resource conditions.

---

### 5.7.3 Plasticity

Memory protection is not useful if it prevents the system from adapting to new tasks.

Plasticity should therefore be measured using current-task performance:

$$
P_{\text{new}} = \frac{1}{K} \sum_{k=1}^{K} A_{k,k},
$$

together with the adaptation-efficiency metrics defined in Section 5.8.

The stability–plasticity result should preferably be reported as two dimensions rather than collapsed immediately into a single scalar.

Conceptually:

```text
Plasticity ↑
           │
           │              ● desirable
           │
           │     ●
           │
           └────────────────────→ Stability
```

A method is preferable when it moves the operating point toward high retention and strong new-task adaptation simultaneously.

---

### 5.7.4 Non-inferiority on New-task Performance

H2 states not only that managed memory reduces forgetting, but that it does so **without meaningfully harming new-task performance**.

A failure to find a statistically significant difference is not sufficient evidence for this claim.

Instead, a non-inferiority margin should be defined before final test evaluation:

$$
\delta_{\text{new}} > 0.
$$

Let:

$$
\Delta_{\text{new}} = P^{\text{managed}}_{\text{new}} - P^{\text{naive}}_{\text{new}}.
$$

Managed memory is considered non-inferior when the uncertainty interval for $\Delta_{\text{new}}$ remains above:

$$
-\delta_{\text{new}}.
$$

The value of $\delta_{\text{new}}$ must be chosen using domain meaning and/or validation experiments, not after observing final test results.

---

### 5.7.5 Memory-capacity Sweep

Managed memory is expected to matter most when capacity creates genuine resource pressure.

Therefore RQ2 should not be tested under only one memory capacity.

Evaluate:

$$
C_{\text{small}}, \qquad C_{\text{medium}}, \qquad C_{\text{large}}.
$$

Exact values should be selected during validation.

The chosen range should include:

* a clearly constrained regime;
* a moderate regime;
* a regime where memory pressure becomes relatively weak.

Report relationships such as:

$$
C \rightarrow F_K,
$$

$$
C \rightarrow \text{FWT},
$$

and:

$$
C \rightarrow \text{AP}_K.
$$

A result where managed memory strongly outperforms naive memory only under tight capacity remains scientifically meaningful:

> memory management is primarily valuable under resource pressure.

---

### 5.7.6 Archivist Ablation

If the full Archivist outperforms naive memory, ablation experiments should determine which mechanisms contribute to the result.

Only mechanisms that actually appear in the final Archivist implementation should be ablated.

Possible examples include:

* protection;
* utility-aware eviction;
* consolidation;
* semantic/procedural abstraction;
* retrieval ranking;
* lifecycle metadata;
* relevance-aware memory updates.

The preferred design is **one controlled modification at a time**, while holding the rest of the system fixed.

For example:

```text
Full Archivist
vs
Archivist - protection

Full Archivist
vs
Archivist - consolidation

Full Archivist
vs
Archivist + random retrieval
```

This prevents improvements from being incorrectly attributed to the entire architecture when they may arise from a single component.

HMACE similarly uses controlled ablations that replace individual retrieval or screening mechanisms while retaining the remainder of the pipeline [R9].

---

## 5.8 Evaluation of RQ3 — Forward Transfer

### RQ3

> When does previously acquired heuristic knowledge enable forward transfer?

Forward transfer in CMHH can occur in two different forms:

1. prior knowledge provides useful competence **before learning begins**;
2. prior knowledge enables the system to **learn the new task faster**.

These must be evaluated separately.

---

### 5.8.1 Zero-shot Forward Transfer

For a new task $T_k$, let:

$$
Z_k
$$

be the pre-learning performance of the continual system.

Let:

$$
B_k
$$

be the corresponding pre-learning performance of the cold-start baseline under the same task and evaluation instances.

CMHH zero-shot forward transfer is:

$$
\text{FWT}_0 = \frac{1}{K-1} \sum_{k=2}^{K} (Z_k - B_k).
$$

Interpretation:

$$
\text{FWT}_0 > 0
$$

indicates that previously acquired knowledge improves performance before new-task search begins.

This is an adaptation of the FWT concept introduced by GEM, which compares performance on future tasks before they are learned against an initial baseline [R1].

For problem-family shifts where direct execution is undefined, $\text{FWT}_0$ should be marked **not applicable** rather than assigned an artificial value.

---

### 5.8.2 Adaptation Curves

For each new task $T_k$, record the best performance achieved after budget $b$:

$$
S_k(b).
$$

Compare:

$$
S^{\text{continual}}_k(b)
$$

against:

$$
S^{\text{cold}}_k(b).
$$

A positive transfer effect may appear even when:

$$
S^{\text{continual}}_k(0) \approx S^{\text{cold}}_k(0),
$$

if prior knowledge allows the continual system to improve more rapidly after search begins.

---

### 5.8.3 Adaptation Curve Area

A-GEM introduces Learning Curve Area to distinguish systems that eventually reach similar performance but learn at different rates [R2].

CMHH adapts this idea from minibatch-based learning to heuristic-search budget.

For task $T_k$:

$$
\text{ACA}_k(B) = \frac{1}{B} \int_0^B S_k(b) \, db,
$$

where $B$ is the maximum search budget.

In implementation, the integral is estimated from fixed budget checkpoints.

Higher ACA is better.

Define transfer gain:

$$
\Delta \text{ACA}_k = \text{ACA}^{\text{continual}}_k - \text{ACA}^{\text{cold}}_k.
$$

Aggregate forward adaptation gain is:

$$
\Delta \text{ACA} = \frac{1}{K-1} \sum_{k=2}^{K} \Delta \text{ACA}_k.
$$

This quantity should be referred to as **Adaptation Curve Area (ACA)** rather than presented as the original A-GEM metric, because the independent variable has been changed from observed training minibatches to heuristic-search budget.

---

### 5.8.4 Fixed-budget Gain

At a predefined search budget $B$:

$$
\text{FBG}_k(B) = S^{\text{continual}}_k(B) - S^{\text{cold}}_k(B).
$$

This answers:

> Given exactly the same search budget, how much better does accumulated knowledge allow the system to perform?

The aggregate metric is:

$$
\text{FBG}(B) = \frac{1}{K-1} \sum_{k=2}^{K} \text{FBG}_k(B).
$$

---

### 5.8.5 Budget-to-Target

Let:

$$
\tau_k
$$

denote a target performance threshold for task $T_k$.

Define:

$$
\text{BTT}_k = \min \{ b \mid S_k(b) \geq \tau_k \}.
$$

This measures how much search is required to reach a useful performance level.

Targets must be defined before final test evaluation, for example using:

* a predefined reference-gap threshold;
* validation-set results;
* a fixed fraction of a reference solution quality.

If a method fails to reach $\tau_k$ within the allowed budget, the observation should be treated as **censored**, rather than assigning an arbitrary infinite value.

The report should therefore include:

* target-reaching success rate;
* budget-to-target among successful runs;
* explicit indication of censored runs.

---

### 5.8.6 Forward Transfer by Task-shift Type

RQ3 asks not merely whether transfer exists, but **when** it exists.

Results must therefore be stratified by transition type:

| Shift type           |     $\text{FWT}_0$     | $\Delta \text{ACA}$ | Fixed-budget gain | Budget-to-target |
| -------------------- | :--------------------: | :-----------------: | :---------------: | :--------------: |
| Scale shift          |                        |                     |                   |                  |
| Distribution shift   |                        |                     |                   |                  |
| Problem-family shift | N/A where incompatible |                     |                   |                  |
| Composite shift      |   context-dependent    |                     |                   |                  |

This makes it possible to identify results such as:

$$
\text{Transfer}_{\text{scale}} > 0
$$

while:

$$
\text{Transfer}_{\text{problem-family}} \approx 0,
$$

rather than hiding fundamentally different behaviors inside one average transfer score.

---

## 5.9 Evaluation of RQ4 — Task Ordering and Curriculum

### Secondary RQ

> How does task ordering affect continual heuristic learning?

Task-order experiments must use the **same multiset of tasks** while changing only their ordering.

For a scale stream, possible conditions include:

```text
Ascending:
20 → 50 → 100 → 200

Descending:
200 → 100 → 50 → 20

Random permutation 1:
50 → 200 → 20 → 100

Random permutation 2:
100 → 20 → 200 → 50

...
```

A single random permutation is insufficient because it may be accidentally easy or difficult.

Multiple random permutations should therefore be evaluated.

Evo-Memory provides a related precedent for evaluating memory systems on sequential task streams under controlled retrieval settings [R6].

---

### 5.9.1 Curriculum Definition

A curriculum must be defined **before observing test performance**.

For example:

* increasing problem size;
* decreasing problem size;
* adjacency based on known task-family metadata;
* adjacency based on a predefined structural-distance function.

Task order must not be optimized using final test results.

---

### 5.9.2 Metrics

RQ4 reuses the same continual metrics rather than inventing a separate performance definition:

$$
\text{AP}_K, \qquad \text{BWT}_K, \qquad F_K, \qquad \text{FWT}_0, \qquad \Delta \text{ACA}.
$$

---

### 5.9.3 Curriculum Gain

For any metric $M$ where higher is better:

$$
\text{CG}_M = M_{\text{curriculum}} - \mathbb{E}_{\pi \sim \text{Random}}[M_{\pi}].
$$

For metrics where lower is better, such as forgetting, the sign should be reversed or clearly interpreted.

Curriculum gain measures whether a deliberate task order improves continual learning relative to random ordering.

---

### 5.9.4 Order Sensitivity

Let $\Pi$ denote the evaluated set of task permutations.

Define:

$$
\text{OS}_M = \text{Std}_{\pi \in \Pi}[M_{\pi}].
$$

A large value indicates that the continual system is highly sensitive to task ordering.

A robust continual learner should ideally achieve:

$$
\text{OS}_M \downarrow.
$$

---

## 5.10 Baselines and Diagnostic Controls

The main experimental suite should distinguish different forms of knowledge continuity.

### Primary baselines

| Condition                       | Persistent memory | Cross-task continuity | Memory management | Purpose                              |
| ------------------------------- | ----------------: | --------------------: | ----------------: | ------------------------------------ |
| Independent cold start          |                No |                    No |                No | No-continual-learning reference      |
| Population carryover            |                No |                   Yes |                No | Minimal sequential continuity        |
| Task-indexed heuristic library  |               Yes |               Limited |   Simple indexing | Strong simple retention baseline     |
| Naive bounded persistent memory |               Yes |                   Yes |          No/naive | Tests persistence without management |
| Managed memory / Archivist      |               Yes |                   Yes |               Yes | Proposed continual-memory mechanism  |

#### Independent cold start

Every task begins without knowledge transferred from previous tasks.

This provides the main reference for measuring forward transfer and learning-efficiency gains.

#### Population carryover

The final search population from $T_k$ initializes search on $T_{k+1}$, but no independent persistent memory is maintained.

This tests whether simple evolutionary continuity is sufficient.

#### Task-indexed heuristic library

The best heuristic found for each previous task is stored under a task identifier and returned when the same task is encountered again.

This is an important baseline because simple storage may already provide excellent seen-task retention when task identity is known.

CMHH must therefore demonstrate advantages beyond merely remembering an old specialist, particularly through:

* bounded-memory behavior;
* cross-task transfer;
* reuse on related unseen tasks;
* knowledge compression or consolidation;
* resilience to retrieval competition.

#### Naive bounded persistent memory

Heuristic knowledge is persistently stored but managed using a simple non-semantic policy such as FIFO or naive overwrite.

This is the direct baseline for evaluating the value of managed memory.

---

### Diagnostic controls

The following are not necessarily primary deployment baselines.

#### Unbounded append-only memory

All discovered memories are retained.

Purpose:

* remove storage eviction as a source of forgetting;
* isolate retrieval competition and memory pollution.

This condition should not be presented as a scalable solution.

#### Validation-oracle retrieval

Relevant items are selected using validation-defined utility.

Purpose:

* estimate how well the system could perform if retrieval were near-optimal;
* isolate retrieval error from memory-content failure.

#### Random retrieval

Retrieve the same number of memory items as the normal system, but select them randomly.

Purpose:

* determine whether retrieval quality itself contributes beyond simply providing additional historical context.

---

## 5.11 Resource-efficiency Metrics

Continual memory may improve optimization quality while increasing computational cost.

Both sides must therefore be reported.

### LLM cost

$$
N_{\text{calls}}
$$

Number of LLM API invocations.

$$
\text{Tokens}_{\text{in}}, \qquad \text{Tokens}_{\text{out}}, \qquad \text{Tokens}_{\text{total}}.
$$

Total token consumption should include memory-management calls as well as heuristic-generation calls.

---

### Search cost

$$
N_{\text{eval}}
$$

Number of expensive heuristic evaluations.

$$
N_{\text{gen}}
$$

Number of evolutionary generations.

---

### Runtime

$$
T_{\text{wall}}
$$

Wall-clock runtime.

Where parallel evaluation is used, configuration such as number of workers must be fixed or explicitly reported.

---

### Memory cost

Report at least:

$$
|M_k|,
$$

and preferably:

$$
\text{Tokens}(M_k),
$$

throughout the task stream.

The final result should distinguish:

```text
persistent storage size
        ≠
retrieval set size
        ≠
active prompt/context size
```

These quantities represent different computational constraints.

Broader continual-learning evaluation work argues that memory and computational efficiency should be considered alongside forgetting and transfer rather than treating task accuracy as the sole criterion [R3]. LLM-based heuristic-design systems such as HMACE similarly report objective quality together with runtime, token use, and API-query counts [R9].

---

## 5.12 Statistical Evaluation Protocol

### 5.12.1 Repeated runs

LLM-based evolutionary heuristic search is stochastic.

Main experimental comparisons should therefore be repeated across independent random seeds.

A practical initial target is:

$$
n \geq 5
$$

independent runs for primary comparisons when computationally feasible.

If a smaller number is used because of LLM cost, the limitation must be reported explicitly and conclusions should be correspondingly conservative.

Every compared method should use matched:

* task instances;
* task ordering;
* random seeds where applicable;
* search budgets;
* reference solutions.

---

### 5.12.2 Paired comparisons

Whenever possible, comparisons should be paired.

For example:

```text
Seed 1:
Naive Memory  vs  Archivist
same stream, same instances

Seed 2:
Naive Memory  vs  Archivist
same stream, same instances
```

This reduces variance caused by differences in task instances or stream difficulty.

---

### 5.12.3 Report effect sizes and uncertainty

For every primary metric, report:

* mean;
* standard deviation;
* paired difference between methods;
* confidence interval for the difference.

Statistical significance alone should not determine the conclusion.

The magnitude and uncertainty of the effect should remain visible.

Where instance-level and run-level stochasticity both contribute, a hierarchical bootstrap over runs and evaluation instances may be used to estimate uncertainty.

---

### 5.12.4 Predefine primary metrics

Each RQ should have a small set of **primary metrics** defined before final evaluation.

Secondary metrics should be treated as diagnostics.

This prevents the final claim from being selected after observing whichever metric happens to produce the most favorable result.

---

### 5.12.5 Multiple comparisons

If multiple statistical hypothesis tests are performed within the same claim family, a correction such as Holm's procedure should be considered.

Exploratory analyses and ablations should be clearly distinguished from primary confirmatory comparisons.

---

### 5.12.6 Reproducibility

Every experimental run should log sufficient information to reconstruct the result, including:

* task-stream definition;
* task order;
* dataset manifest and checksums;
* random seeds;
* LLM model identifier/version;
* temperature and sampling settings;
* prompts;
* memory capacity;
* retrieval configuration;
* search budget;
* stopping conditions;
* generated heuristic code;
* intermediate memory states;
* raw candidate evaluations;
* token usage;
* timestamps and runtime;
* final performance matrix.

---

## 5.13 RQ-to-Evaluation Mapping

The final experimental design should maintain an explicit mapping from each research question to the evidence used to answer it.

| Research Question               | Primary comparison                                              | Primary evidence                            | Diagnostic evidence                                                                                                                   |
| ------------------------------- | --------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **RQ1 — Functional forgetting** | sequential baselines across stream                              | Average Forgetting, BWT                     | AP, worst-case forgetting, retention trajectories, competence coverage, Recall@$k$, NDCG@$k$, retrieval regret, memory-pollution test |
| **RQ2 — Managed memory**        | managed vs naive bounded memory under matched capacity          | Forgetting + BWT + new-task non-inferiority | capacity sweep, retrieval quality, memory footprint, Archivist ablations                                                              |
| **RQ3 — Forward transfer**      | continual state vs cold start                                   | $\text{FWT}_0$, $\Delta \text{ACA}$          | fixed-budget gain, budget-to-target, LLM/evaluation cost, breakdown by task-shift type                                                |
| **RQ4 — Task ordering**         | curriculum/ascending/descending vs multiple random permutations | difference in BWT, forgetting, FWT and ACA  | curriculum gain, order sensitivity                                                                                                    |
| **Primary RQ**                  | synthesis of RQ1–RQ3 and secondary RQ4                          | retained competence + transfer + adaptation | resource efficiency and mechanism diagnostics                                                                                         |

The primary research question therefore does not require a separate artificial aggregate score.

It is answered by the combined evidence from the constituent research questions.

---

## 5.14 Interpretation Rules

The evaluation should distinguish conclusions carefully.

### Case 1 — No functional forgetting

If naive sequential systems maintain performance on old tasks:

$$
F_K \approx 0
$$

and:

$$
\text{BWT}_K \approx 0,
$$

then H1 is not supported.

This is not an experimental failure.

It would indicate that explicit symbolic heuristic knowledge behaves differently from parameter-based representations with respect to catastrophic forgetting.

---

### Case 2 — Functional forgetting without storage loss

If:

$$
A_{K,j} \downarrow
$$

while empirically useful memory remains physically stored, and retrieval quality simultaneously decreases, the result supports **retrieval-side functional forgetting**.

---

### Case 3 — Managed memory improves retention but harms plasticity

If Archivist reduces:

$$
F_K
$$

but significantly degrades current-task acquisition or adaptation speed, then the method improves stability but does not solve the full stability–plasticity problem.

H2 would therefore be only partially supported.

---

### Case 4 — Managed memory improves retention without meaningful new-task loss

If managed memory reduces forgetting while satisfying the predefined new-task non-inferiority criterion, this supports H2.

---

### Case 5 — Positive zero-shot transfer

If:

$$
\text{FWT}_0 > 0,
$$

prior knowledge provides immediately executable competence on future compatible tasks.

---

### Case 6 — No zero-shot gain but faster adaptation

If:

$$
\text{FWT}_0 \approx 0
$$

but:

$$
\Delta \text{ACA} > 0
$$

or budget-to-target decreases, prior knowledge still provides meaningful **learning-efficiency forward transfer**.

This distinction is particularly important for CMHH because the goal is not necessarily to retrieve a universal heuristic that already solves every new task.

---

### Case 7 — Negative forward transfer

If continual initialization or memory reuse performs worse than cold start:

$$
\text{FWT}_0 < 0
$$

or:

$$
\Delta \text{ACA} < 0,
$$

the accumulated knowledge is producing negative transfer.

This is direct evidence of destructive cross-task interference.

---

### Case 8 — Transfer depends on task shift

If positive transfer appears for scale or distribution shifts but disappears under problem-family shifts, the correct conclusion is not simply that "CMHH transfers knowledge."

The result should instead characterize the **transfer boundary**:

> which types of structural relatedness permit useful heuristic reuse.

---

### Case 9 — Curriculum has no measurable effect

If deliberate ordering performs similarly to the distribution of random permutations, H4 is not supported.

Curriculum should then remain a negative or secondary finding rather than being forced into the main contribution.

---

## 5.15 Recommended Main Result Artifacts

The final paper should ideally contain the following result views.

### Continual performance matrix

A heatmap or table of:

$$
A_{k,j}.
$$

Purpose:

* visualize retention across the complete stream.

### Retention curves

Plot:

$$
A_{k,j}
$$

for selected early tasks as $k$ increases.

Purpose:

* visualize forgetting trajectories.

### Adaptation curves

Plot:

$$
S^{\text{continual}}_k(b) \quad\text{vs}\quad S^{\text{cold}}_k(b).
$$

Purpose:

* visualize forward-transfer learning efficiency.

### Stability–plasticity comparison

Plot retention against new-task adaptation.

Purpose:

* determine whether memory management improves one objective by sacrificing the other.

### Memory-capacity curves

Plot:

$$
C \rightarrow F_K, \qquad C \rightarrow \text{AP}_K, \qquad C \rightarrow \text{FWT}.
$$

Purpose:

* determine when memory management becomes useful.

### Controlled memory-pollution curves

Plot:

$$
|M| \rightarrow \text{Recall}@k
$$

and:

$$
|M| \rightarrow A(T_j).
$$

Purpose:

* isolate retrieval-side interference.

### Quality–cost curves

Plot optimization performance against:

* candidate evaluations;
* LLM tokens;
* wall-clock time.

Purpose:

* show whether continual knowledge actually reduces the cost of heuristic acquisition.

---

## 5.16 Literature Provenance

The evaluation framework combines established metrics with CMHH-specific adaptations. The provenance of each major component should remain explicit.

| Evaluation component                                                      | Status in CMHH                                                         | Main literature basis                                                   |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Task-performance matrix                                                   | Adapted                                                                | GEM [R1]                                                                |
| Average performance                                                       | Adapted                                                                | GEM [R1]                                                                |
| Backward transfer                                                         | Adapted                                                                | GEM [R1]                                                                |
| Zero-shot forward transfer                                                | Adapted                                                                | GEM [R1]                                                                |
| Average forgetting                                                        | Adapted                                                                | A-GEM / continual forgetting literature [R2]                            |
| Learning/adaptation curve area                                            | **CMHH adaptation** of LCA from minibatches to heuristic-search budget | A-GEM [R2]                                                              |
| Memory + compute as evaluation dimensions                                 | Adopted principle                                                      | Díaz-Rodríguez et al. [R3]                                              |
| Recall@$k$, NDCG@$k$ for intermediate retrieval                           | Adopted diagnostic where relevance labels can be defined               | LongMemEval [R4]                                                        |
| Separating memory capability dimensions                                   | Adopted principle                                                      | MemoryAgentBench [R5]                                                   |
| Sequential evolving-memory evaluation                                     | Related precedent                                                      | Evo-Memory [R6]                                                         |
| LLM-query budget in heuristic search                                      | Related precedent                                                      | EoH [R7]                                                                |
| CO optimality/reference-gap evaluation                                    | Related precedent                                                      | HeurAgenix [R8]                                                         |
| Tokens, API calls, runtime, matched evaluator budget, controlled ablation | Related precedent                                                      | HMACE [R9]                                                              |
| Controlled memory-pollution test                                          | **CMHH-specific diagnostic**                                           | Motivated by functional-forgetting formulation and retrieval literature |
| Validation-oracle retrieval regret                                        | **CMHH-specific diagnostic**                                           | Motivated by retrieval-vs-downstream separation                         |
| Stability–plasticity evaluation under bounded heuristic memory            | **CMHH-specific application**                                          | Continual-learning principle adapted to heuristic memory                |
| Budget-to-target                                                          | **CMHH operational metric**                                            | Motivated by learning-efficiency and anytime-search evaluation          |

The distinction between **adopted**, **adapted**, and **CMHH-specific** metrics should be retained when the final paper is written so that standard continual-learning methodology is not incorrectly presented as a novel contribution.

---

## References for Evaluation Design

**[R1]** Lopez-Paz, D., & Ranzato, M. *Gradient Episodic Memory for Continual Learning.* arXiv:1706.08840.
Used for: continual task-performance matrix, average performance, backward transfer, forward transfer, and bounded episodic-memory framing.

**[R2]** Chaudhry, A., Ranzato, M., Rohrbach, M., & Elhoseiny, M. *Efficient Lifelong Learning with A-GEM.* ICLR 2019. arXiv:1812.00420.
Used for: average forgetting, learning-speed evaluation through Learning Curve Area, efficiency-aware continual evaluation, and separation of hyperparameter-selection tasks from the final evaluation stream.

**[R3]** Díaz-Rodríguez, N., Lomonaco, V., Filliat, D., & Maltoni, D. *Don't Forget, There Is More than Forgetting: New Metrics for Continual Learning.* arXiv:1810.13166.
Used for: evaluating continual systems beyond final accuracy, including transfer, memory overhead, computational efficiency, and performance over time.

**[R4]** Wu, D., et al. *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory.* arXiv:2410.10813.
Used for: separating end-to-end task performance from intermediate memory retrieval and using Recall@(k) and NDCG@(k) as retrieval diagnostics.

**[R5]** Hu, Y., Wang, Y., & McAuley, J. *Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions (MemoryAgentBench).* arXiv:2507.05257.
Used for: treating retrieval, test-time learning, long-range memory use, and memory conflict as distinct capabilities rather than reducing memory evaluation to a single score.

**[R6]** Wei, T., et al. *Evo-Memory: Benchmarking LLM Agent Test-time Learning with Self-Evolving Memory.* arXiv:2511.20857.
Used for: precedent for evaluating memory systems over sequential task streams with continuously evolving memory and controlled retrieval settings.

**[R7]** Liu, F., et al. *Evolution of Heuristics: Towards Efficient Automatic Algorithm Design Using Large Language Model.* arXiv:2401.02051.
Used for: LLM-query budget as an important computational dimension in automatic heuristic design.

**[R8]** Yang, X., Zhang, L., Qian, H., Song, L., & Bian, J. *HeurAgenix: Leveraging LLMs for Solving Complex Combinatorial Optimization Challenges.* arXiv:2506.15196.
Used for: LLM-based hyper-heuristic evaluation and optimization-quality comparison across combinatorial-optimization settings.

**[R9]** Yan, Y., Han, J., Ming, F., Li, Y., & Jin, Y. *HMACE: Heterogeneous Multi-Agent Collaborative Evolution for Combinatorial Optimization.* arXiv:2605.07214.
Used for: relative suboptimality, token and API-query accounting, wall-clock evaluation, matched evaluator-budget analysis, search trajectories, and controlled component ablations.
