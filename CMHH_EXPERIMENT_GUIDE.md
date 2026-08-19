# CMHH — Experiment Execution & Results Analysis Guide

**Project:** Continual Multi-Agent Hyper-Heuristics (CMHH)  
**Target Audience:** ML Research Engineers, PhD Researchers  
**Repository Root:** `c:\Users\LENOVO\Projects\CM_HH`

---

## 1. Overview & Experimental Protocol

CMHH evaluates continual learning in LLM-based heuristic search across a sequential stream of combinatorial optimization tasks:

$$
T_1 \rightarrow T_2 \rightarrow T_3 \rightarrow \dots \rightarrow T_K
$$

### 1.1 The Four Benchmark Experimental Conditions
To isolate the contribution of persistent external memory and managed Archivist consolidation, every paper evaluation compares **4 experimental conditions**:

1. **`isolated` (Cold Start Baseline)**:
   - Each task $T_k$ is solved from scratch using cold-start seed heuristics. No knowledge carryover or memory across tasks.
2. **`population_carryover` (Working Population Baseline)**:
   - Final population of evolved heuristics from task $T_{k-1}$ is passed directly as seeds to task $T_k$. No external persistent storage or Archivist.
3. **`naive_memory_sequential` (Uncurated External Memory Baseline)**:
   - All candidate heuristics surviving validation are written to `MemoryStore` (capacity $C=20$, top-$k=5$). Naive FIFO/score eviction without distillation or anchor protection.
4. **`archivist_managed` (Full CMHH Managed Memory System)**:
   - Search candidates pass through `WorkingBuffer`. `DefaultArchivist` applies `elite_validation` admission, anchor protection for top task heuristics, capacity overflow invariant checks, and utility-recency eviction ranking.

---

## 2. Environment & LLM Configuration Setup

### 2.1 Python Environment
Ensure `PYTHONPATH` points to `HeurAgenix/src`:

```powershell
$env:PYTHONPATH="HeurAgenix/src"
```

### 2.2 LLM Configuration File (`llm_config.json`)
Create or edit your LLM configuration file (e.g. `HeurAgenix/cmhh/configs/llm/vllm_local.json` or `openai.json`):

#### Option A: OpenAI / Commercial API
```json
{
  "type": "api_model",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "api_key": "YOUR_OPENAI_API_KEY",
  "temperature": 0.0,
  "max_tokens": 2048
}
```

#### Option B: Local Model (vLLM / Ollama / Local Server)
```json
{
  "type": "api_model",
  "provider": "openai_compatible",
  "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "api_base": "http://localhost:8000/v1",
  "api_key": "none",
  "temperature": 0.0,
  "max_tokens": 2048
}
```

---

## 3. Step-by-Step Execution Guide

### Step 1: Validate Task Registry and Experiment Configuration
Verify that all task manifests and experiment configurations are intact:

```powershell
$env:PYTHONPATH="HeurAgenix/src"; python -m cmhh.cli --repo-root HeurAgenix validate-config --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml
```

*Expected output:* `Validated 12 tasks; stream has 4 tasks` (Exit code 0).

---

### Step 2: Generate TSPLIB Datasets
Generate deterministic train, validation, test, and smoke TSPLIB instance files for the task stream:

```powershell
$env:PYTHONPATH="HeurAgenix/src"; python -m cmhh.cli --repo-root HeurAgenix generate-data --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --seed 42
```

---

### Step 3: Generate & Verify Reference Exact Tour Solutions (Concorde)
To compute relative optimality gaps, generate exact ground-truth tours using the Concorde solver:

```powershell
# 1. Generate exact tours for validation and test splits
$env:PYTHONPATH="HeurAgenix/src"; python -m cmhh.cli --repo-root HeurAgenix generate-references --solver-config HeurAgenix/cmhh/configs/solvers/concorde.yaml --split test --split validation

# 2. Verify reference checksums and tour correctness
$env:PYTHONPATH="HeurAgenix/src"; python -m cmhh.cli --repo-root HeurAgenix verify-references --split test --split validation
```

---

### Step 4: Evaluate Baseline Seed Heuristics
Evaluate built-in constructive baseline heuristics across all stream tasks:

```powershell
$env:PYTHONPATH="HeurAgenix/src"; python -m cmhh.cli --repo-root HeurAgenix evaluate-baselines --split validation
$env:PYTHONPATH="HeurAgenix/src"; python -m cmhh.cli --repo-root HeurAgenix evaluate-baselines --split test
```

---

### Step 5: Run Continual Streams Across Experimental Conditions

Execute the stream runner for your target experimental run:

```powershell
# Run Managed Archivist Condition
$env:PYTHONPATH="HeurAgenix/src"; python -m cmhh.cli --repo-root HeurAgenix run-stream --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --generator heuragenix --llm-config HeurAgenix/cmhh/configs/llm/vllm_local.json --seed 42 --run-id run_archivist_seed42
```

To run baseline conditions, specify the experiment YAML config corresponding to the desired condition:
- `isolated_tsp.yaml` (`condition: isolated`)
- `population_carryover_tsp.yaml` (`condition: population_carryover`)
- `naive_memory_tsp.yaml` (`condition: naive_memory_sequential`)
- `archivist_tsp.yaml` (`condition: archivist_managed`)

---

### Step 6: Resume Interrupted Runs
If a run is interrupted by hardware failure or API timeout, resume seamlessly from the latest checkpoint:

```powershell
$env:PYTHONPATH="HeurAgenix/src"; python -m cmhh.cli --repo-root HeurAgenix run-stream --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --run-id run_archivist_seed42 --resume --generator heuragenix --llm-config HeurAgenix/cmhh/configs/llm/vllm_local.json
```

---

### Step 7: Audit Run Directory Integrity
Verify that the run output directory passes all scientific audit checks:

```powershell
$env:PYTHONPATH="HeurAgenix/src"; python -m cmhh.cli --repo-root HeurAgenix audit-run --run-id run_archivist_seed42
```

---

## 4. Detailed Results Inspection & Analysis Guide

Each run output directory is stored under `HeurAgenix/cmhh/results/<run_id>/` (or configured `output_root`).

### Directory Layout:
```text
HeurAgenix/cmhh/results/<run_id>/
├── manifest.json                  # Environment, seeds, code checksums, config snapshots
├── events.jsonl                   # Full event-sourced audit log (schema_version = 1)
├── performance_matrix.csv         # Performance matrix R_{k,j} (relative gap)
├── metrics.json                   # Aggregated continual metrics (AF, BWT, FWT)
├── checkpoints/
│   └── latest.json                # Resumable run state & selected artifacts
├── memory/
│   ├── memory.jsonl               # Persistent long-term memory store (3-layer MemoryItem records)
│   └── diagnostics.json           # Memory retrieval, coverage, eviction lineage, failure labels
└── evaluations/
    ├── after_0/                   # Post-task 0 test probe evaluations
    ├── after_1/                   # Post-task 1 test probe evaluations
    └── ...
```

---

### 4.1 How to Read `performance_matrix.csv`

The performance matrix $R \in \mathbb{R}^{K \times K}$ stores the relative gap to optimal performance achieved on task $j$ (column) after completing learning on task $k$ (row).

$$\text{Score Convention: } \text{score} = - \text{relative\_gap} = - \frac{\text{heuristic\_objective} - \text{optimal\_objective}}{\text{optimal\_objective}}$$

*(Higher score is better; $0.0$ represents exact certified optimal performance).*

#### Example `performance_matrix.csv`:
```csv
after_task,tsp_20,tsp_50,tsp_100,tsp_200
tsp_20,-0.012,,
tsp_50,-0.015,-0.035,,
tsp_100,-0.018,-0.038,-0.062,
tsp_200,-0.021,-0.040,-0.065,-0.098
```

#### How to Interpret the Matrix Regions:
1. **Main Diagonal ($R_{k,k}$)**: Immediate performance on task $k$ right after learning $T_k$.
2. **Lower Triangle ($R_{k,j}$ where $k > j$)**: Retained competence on prior task $T_j$ after subsequent task learning up to $T_k$.
3. **Vertical Column Drift ($R_{1,j} \to R_{K,j}$)**: Competence trajectory on task $T_j$ over time:
   - Constant values $\implies$ Perfect competence retention (zero forgetting).
   - Decreasing values $\implies$ Functional forgetting or memory interference.
   - Increasing values $\implies$ Positive Backward Transfer ($BWT$).

---

### 4.2 How to Read `metrics.json`

`metrics.json` contains aggregated paper metrics computed across the stream:

```json
{
  "average_final_performance": -0.056,
  "backward_transfer": -0.007,
  "forward_transfer": 0.042,
  "score_convention": "higher_is_better; score=-relative_gap"
}
```

#### Metric Definitions & Formulas:
1. **Average Final Performance ($AF$)**:
   $$AF = \frac{1}{K} \sum_{j=1}^K R_{K,j}$$
   Measures final system capability across all stream tasks at the end of the stream.

2. **Backward Transfer ($BWT$)**:
   $$BWT = \frac{1}{K-1} \sum_{j=1}^{K-1} \left( R_{K,j} - R_{j,j} \right)$$
   Measures how learning subsequent tasks affects performance on earlier tasks.
   - $BWT = 0 \implies$ No forgetting.
   - $BWT < 0 \implies$ Catastrophic/functional forgetting.
   - $BWT > 0 \implies$ Bidirectional positive learning.

3. **Forward Transfer ($FWT$)**:
   $$FWT = \frac{1}{K-1} \sum_{k=2}^K \left( R_{k-1,k}^{\text{probe}} - R_k^{\text{cold\_start}} \right)$$
   Measures zero-shot transfer performance on new task $T_k$ using knowledge accumulated up to $M_{k-1}$, compared to cold-start learning.

---

### 4.3 How to Read `memory/diagnostics.json`

`diagnostics.json` provides scientific instrumentation for analyzing memory behavior:

```json
{
  "schema_version": 1,
  "retrieval_events": 8,
  "retrieval_events_with_results": 8,
  "memory_units_written": 12,
  "memory_units_retrieved": 5,
  "retrieval_coverage": 0.416,
  "total_retrieved_units": 20,
  "top_k_concentration": 0.45,
  "duplicate_key_rate_mean": 0.0,
  "post_reuse_validation_delta_mean": 0.038,
  "eviction_lineage": [
    {
      "memory_id": "mem_a1b2c3d4",
      "task_id": "tsp_100",
      "timestamp": "2026-08-20T00:15:30.123456+00:00"
    }
  ],
  "failure_mode_labels": []
}
```

#### Key Diagnostic Metrics:
- **`retrieval_coverage`**: Proportion of written long-term memory items that were actually retrieved at least once. Low coverage ($< 0.25$) signals **memory dilution**.
- **`duplicate_key_rate_mean`**: Proportion of retrieved memory items with identical structural applicability keys. High duplicate rates ($\ge 0.5$) signal **retrieval pollution**.
- **`post_reuse_validation_delta_mean`**: Average performance gain on validation split resulting from memory reuse. Negative delta ($< 0$) signals **harmful reuse**.
- **`eviction_lineage`**: Audit trail of every evicted memory item, recording memory ID, task where eviction occurred, and timestamp.
- **`failure_mode_labels`**: Diagnostic labels automatically flagged by the system (e.g., `harmful_reuse`, `retrieval_pollution`, `context_competition`, `retrieval_diversity_collapse`).

---

### 4.4 How to Read `events.jsonl` Audit Log

`events.jsonl` records append-only JSON event lines with `schema_version = 1`.

#### Key Event Types to Audit:
- **`pre_learning_probe_started` / `pre_learning_probe_completed`**:
  Verifies zero-shot probe execution before task learning (`read_only: true`).
- **`candidate_generated` / `candidate_selected`**:
  Tracks generated heuristics and selection of the best candidate per generation/task.
- **`memory_written` / `memory_protected` / `memory_evicted`**:
  Tracks Archivist lifecycle decisions. `memory_protected` logs items assigned anchor protection status.
- **`retrieval_event`**:
  Logs query parameters, retrieved memory IDs, ranks, and similarity scores.
- **`retention_probe_started` / `retention_probe_completed`**:
  Verifies READ-ONLY evaluation of retained competence on prior tasks using current memory $M_k$.

---

## 5. Troubleshooting & FAQs

### Q1: What happens if LLM API rate limits or budget is exceeded during evolution?
`BudgetedLLMClient` catches provider errors and enforces `max_llm_calls`. If the search budget is exhausted, `StreamRunner` saves a valid checkpoint at `checkpoints/latest.json`. You can resolve the provider issue and run with `--resume`.

### Q2: Why did `DefaultArchivist` raise `CapacityOverflowError`?
If `CapacityOverflowError` is raised, the cumulative number of protected task anchor heuristics across completed tasks has exceeded maximum memory capacity $C=20$. This invariant prevents silent eviction of protected anchors. Adjust capacity $C$ in config or check stream length.

### Q3: How do I verify that test evaluation did not leak into memory admission or retrieval tuning?
Run `audit-run`:
```powershell
python -m cmhh.cli --repo-root HeurAgenix audit-run --run-id <run_id>
```
`audit_run()` inspects prompt artifacts, generation logs, and event sequences to verify that no test split paths or test performance numbers were passed to the generator or Archivist.
