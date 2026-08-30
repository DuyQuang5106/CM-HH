# CMHH — Experiment Execution & Results Analysis Guide

**Project:** Continual Multi-Agent Hyper-Heuristics (CM-HH)  
**Target Audience:** ML Research Engineers, PhD Researchers, Authors  
**Repository Root:** `c:\Users\LENOVO\Projects\CM_HH`

---

## 1. Overview & Experimental Protocol

CM-HH evaluates continual learning in LLM-driven hyper-heuristic search across a sequential stream of combinatorial optimization tasks:

$$
T_1 \rightarrow T_2 \rightarrow T_3 \rightarrow \dots \rightarrow T_K
$$

```text
CandidateExtractor -> Archivist Gatekeeper -> MemoryStore -> Retriever Engine
    -> TransferPolicy -> PopulationBuilder -> Evolution Search -> Transfer Feedback
```

---

### 1.1 Benchmark Experimental Conditions (5 Comparison Baselines)

Every benchmark stream is evaluated across **5 conditions** to isolate the causal impact of managed memory consolidation:

1. **`isolated` (Cold-Start Baseline)**:
   - Each task $T_k$ is solved from scratch. No memory or heuristic transfer across tasks.
2. **`population_carryover` (Working Population Baseline)**:
   - The final population of heuristics from task $T_{k-1}$ is passed directly as seeds to task $T_k$. No persistent external memory store.
3. **`naive_bounded` (Uncurated Bounded Memory Baseline)**:
   - All heuristics surviving validation are written to a flat `MemoryStore` (capacity $C=20$, top-$k=5$). Naive FIFO/score eviction without anchor protection.
4. **`naive_unbounded` (Unbounded Memory Diagnostic)**:
   - Same uncurated memory policy without capacity limits. Disentangles capacity-driven forgetting from retrieval noise.
5. **`archivist_managed` (CM-HH Managed Archivist)**:
   - Working buffer candidates pass through `DefaultArchivist` with `elite_validation` admission, anchor protection for top task heuristics, invariant checks, and utility-recency eviction ranking.

---

### 1.2 The 13 Benchmark Stream Suite

| Stream ID | Problem Domain | Task Ordering & Distribution Shift |
|---|---|---|
| **`tsp_size_ascending`** | TSP | Within-domain scale transfer: $n20 \to n50 \to n100 \to n200$ (Primary Pilot) |
| **`tsp_size_descending`** | TSP | Within-domain reverse scale: $n200 \to n100 \to n50 \to n20$ |
| **`tsp_random_perm_1`** | TSP | Randomized scale ordering: $n50 \to n200 \to n20 \to n100$ |
| **`tsp_random_perm_2`** | TSP | Randomized scale ordering: $n100 \to n20 \to n200 \to n50$ |
| **`cvrp_size_ascending`** | CVRP | Vehicle routing scale transfer: $n20 \to n50 \to n100$ |
| **`cvrp_size_descending`** | CVRP | Vehicle routing reverse scale: $n100 \to n50 \to n20$ |
| **`jssp_size_ascending`** | JSSP | Job-shop scale transfer: $3\times3 \to 6\times6 \to 10\times10$ |
| **`jssp_size_descending`** | JSSP | Job-shop reverse scale: $50\times10 \to 20\times5 \to 10\times5$ |
| **`cross_problem_tsp_cvrp_jssp`** | Cross-Domain | Cross-problem transfer: $\text{TSP} \to \text{CVRP} \to \text{JSSP}$ |
| **`tsp_stationary`** | TSP | Stationary control: $n50 \times 4$ (Stability test) |
| **`tsp_revisit`** | TSP | Architecture revisit: $n50 \to n100 \to n50 \to n200$ |
| **`related_pair_tsp_cvrp_tsp`** | Cross-Domain | Related pair cycle: $\text{TSP} \to \text{CVRP} \to \text{TSP}$ |
| **`unrelated_pair_tsp_jssp_tsp`**| Cross-Domain | Unrelated pair cycle: $\text{TSP} \to \text{JSSP} \to \text{TSP}$ |

---

### 1.3 Statistical Protocol: 3 to 5 Independent Seeds Required

> [!IMPORTANT]
> **Mandatory Statistical Reporting:**
> To account for LLM stochasticity and evolutionary variance, every stream must be evaluated across **3 to 5 independent runs (Seeds: 1, 2, 3, 4, 5)**.
> All paper tables report **$\text{Mean} \pm \text{Std}$** across seeds for $AF$, $BWT$, and $FWT$.

---

### 1.4 Production Search Budget

```yaml
search:
  generations: 100
  candidates_per_generation: 5
  max_llm_calls: 500
evaluation:
  instance_timeout_seconds: 30
  batch_timeout_seconds: 900
```

---

## 2. Environment & Quickstart Setup

### 2.1 Dependencies Installation
```powershell
pip install -e .
```

### 2.2 LLM Configuration (`HeurAgenix/cmhh/configs/llm/llm_config.local.json`)
```json
{
  "type": "api_model",
  "name": "nvidia-gpt-oss-120b",
  "url": "https://integrate.api.nvidia.com/v1/chat/completions",
  "api_key": "nvapi-your-api-key-here",
  "model": "openai/gpt-oss-120b",
  "temperature": 1,
  "max_tokens": 4096,
  "max_attempts": 5,
  "seed": 42
}
```

---

## 3. Execution Commands

### 3.1 Interactive Stream Runner (Recommended)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_menu.ps1
```

### 3.2 Running Individual Streams with 3–5 Seeds
```powershell
# TSP Ascending (5 seeds):
powershell -ExecutionPolicy Bypass -File scripts\run_stream_1_tsp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5

# CVRP Ascending (5 seeds):
powershell -ExecutionPolicy Bypass -File scripts\run_stream_3_cvrp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5

# JSSP Ascending (5 seeds):
powershell -ExecutionPolicy Bypass -File scripts\run_stream_4_jssp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5

# Cross-Problem Transfer (5 seeds):
powershell -ExecutionPolicy Bypass -File scripts\run_stream_5_cross_domain.ps1 -FullBenchmark -Seeds 1,2,3,4,5
```

### 3.3 Automated Full-Suite Multi-Seed Execution
```powershell
# 3 Seeds on all 13 streams:
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3 -LlmConfig cmhh/configs/llm/llm_config.local.json

# 5 Seeds on all 13 streams:
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3,4,5 -LlmConfig cmhh/configs/llm/llm_config.local.json
```

### 3.4 Resuming an Interrupted Benchmark
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3,4,5 -Resume
```

---

## 4. Live Monitoring & Metrics Inspection

### 4.1 Real-Time Watcher
```powershell
powershell -ExecutionPolicy Bypass -File scripts\watch_phase1_tsp_run.ps1
```

### 4.2 Reading Output Reports
Output directories are structured under: `HeurAgenix/cmhh/results/<stream_id>_<timestamp>_<condition>_seed<seed>/`

1. **`performance_matrix.csv`**: Contains relative gap matrix $R_{k,j} = -\frac{\text{Heuristic} - \text{Optimal}}{\text{Optimal}}$.
2. **`metrics.json`**:
   - $AF = \frac{1}{K} \sum_{j=1}^K R_{K, j}$
   - $BWT = \frac{1}{K-1} \sum_{j=1}^{K-1} (R_{K, j} - R_{j, j})$
   - $FWT = \frac{1}{K-1} \sum_{j=2}^K (R_{j-1, j}^{\text{probe}} - R_{\text{isolated}, j})$
3. **`memory/diagnostics.json`**: Retrieval coverage, admission/eviction lineage, reuse delta, and failure mode labels.
4. **`events.jsonl`**: Complete chronological audit log.
