# CM-HH 4-Stream Pilot Suite Specification

This document specifies the scientific taxonomy, mathematical formulations, paired dataset guarantees, and transfer semantics for the canonical CM-HH 4-Stream Pilot Suite.

---

## 1. Experimental Matrix

The pilot suite evaluates **4 streams** across all **5 canonical conditions** for initial seeds `[1, 2, 3]`:

$$\text{Total Runs} = 4 \text{ streams} \times 5 \text{ conditions} \times 3 \text{ seeds} = 60 \text{ stream runs}$$

### Conditions
1. **`isolated`**: Cold start baseline with no memory and no carryover.
2. **`population`**: Carryover of final population knowledge from the immediately preceding task.
3. **`naive-bounded`**: Sequential FIFO archive of capacity $C = 20$.
4. **`naive-unbounded`**: Sequential unbounded archive ($C = \infty$).
5. **`managed`**: Archivist-managed 3-layer memory with structured admission, protection, and eviction.

---

## 2. Stream Taxonomy

| ID | Stream | Problem Sequence | Shift Category | Scientific Objective |
| :--- | :--- | :--- | :--- | :--- |
| **S1** | `s1_tsp_scale` | $\text{TSP20} \to \text{TSP50} \to \text{TSP100}$ | Scale Shift | Measure knowledge transfer across increasing instance scale within the same domain. |
| **S2** | `s2_cvrp_constraint` | $\text{CVRP50-Loose} \to \text{Medium} \to \text{Tight}$ | Constraint Shift | Measure transfer across tightening feasible regions on identical underlying instances. |
| **S3** | `s3_related_cross_problem` | $\text{TSP50-A} \to \text{CVRP50-Medium} \to \text{TSP50-B}$ | Related Transfer | Measure cross-problem transfer across structurally related routing domains. |
| **S4** | `s4_unrelated_cross_problem` | $\text{TSP50-A} \to \text{JSSP10x5} \to \text{TSP50-B}$ | Unrelated Transfer | Control against negative transfer and interference across unrelated combinatorial domains. |

---

## 3. Mathematical CVRP Constraint Regimes (S2)

For each base instance, customer coordinates, customer demands $\{d_i\}_{i=1}^n$, depot location, and fleet size $K$ are generated once and held **strictly identical** across all three regimes.

Vehicle capacity $Q$ is derived from target tightness $\rho_{\text{target}} \in \{0.55, 0.75, 0.90\}$:

$$Q = \left\lceil \frac{\sum_{i=1}^n d_i}{K \cdot \rho_{\text{target}}} \right\rceil$$

Actual recorded tightness:

$$\rho_{\text{actual}} = \frac{\sum_{i=1}^n d_i}{K \cdot Q}$$

### Strict Invariants
1. $Q_{\text{loose}} > Q_{\text{medium}} > Q_{\text{tight}}$
2. $\rho_{\text{actual}}^{\text{loose}} < \rho_{\text{actual}}^{\text{medium}} < \rho_{\text{actual}}^{\text{tight}}$
3. $\max(d_i) \le Q$ and $\sum_{i=1}^n d_i \le K \cdot Q$
4. All three variants share the same `base_instance_id`, `coordinate_hash`, and `demand_hash`.

---

## 4. S3/S4 Matched Anchor Datasets

Tasks `tsp_uniform_n50_a` and `tsp_uniform_n50_b` are independent random samples drawn from the same uniform Euclidean distribution:
- $\text{TSP50-A} \neq \text{TSP50-B}$ (distinct coordinates and manifest hashes).
- $\text{SHA256}(S3.\text{TSP50-A}) == \text{SHA256}(S4.\text{TSP50-A})$
- $\text{SHA256}(S3.\text{TSP50-B}) == \text{SHA256}(S4.\text{TSP50-B})$

This isolates the middle task ($\text{CVRP50}$ vs $\text{JSSP10x5}$) as the single independent variable.

---

## 5. Cross-Problem Transfer & Validation Pipeline

1. **Direct Execution Prohibition**: Source code from one problem domain (e.g. TSP) is **never** executed directly on a different target domain (e.g. CVRP/JSSP).
2. **TransferableKnowledge Normalization**: Prior memory items normalize into a canonical `TransferableKnowledge` structure containing algorithmic principles, design descriptions, and performance metadata.
3. **Shared CrossProblemAdapter**: All continual conditions use the same adapter to translate algorithmic principles into target prompt instructions (`<TRANSFERRED_KNOWLEDGE>`).
4. **TargetContractValidator**: Performs static AST validation of entrypoint, argument names/count, and syntax before sandbox execution.
5. **Zero-Shot Probe Semantics**: Incompatible cross-domain probe evaluations emit `status: "not_applicable", score: null` without penalty.
