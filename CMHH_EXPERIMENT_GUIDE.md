# CMHH - Experiment execution and results analysis guide

**Project:** Continual Multi-Agent Hyper-Heuristics (CM-HH)

This guide documents the current cross-platform way to run experiments. The canonical command path is:

```powershell
uv run cmhh run-suite ...
```

This works on Windows, macOS, Linux, remote servers, and SLURM jobs after `uv sync`. PowerShell scripts are Windows-only compatibility wrappers and are not the recommended execution path.

---

## 1. Experimental protocol

CM-HH evaluates continual learning across streams of combinatorial optimization tasks:

```text
T1 -> T2 -> T3 -> ... -> TK
```

Each benchmark stream should be evaluated across 3-5 independent seeds. Paper tables should report mean +/- std across seeds for:

- `AF`: average final performance.
- `BWT`: backward transfer / forgetting.
- `FWT`: forward transfer.

---

## 2. Conditions

| Condition | Meaning |
|---|---|
| `isolated` | Cold-start baseline, no transfer |
| `population` | Final population carries over to next task |
| `naive-bounded` | Naive external memory with bounded capacity |
| `naive-unbounded` | Naive external memory without capacity pressure |
| `managed` | CM-HH managed memory with Archivist/Retriever/Transfer Policy |

---

## 3. Streams

| Stream ID | Problem domain |
|---|---|
| `tsp_size_ascending` | TSP size ascending |
| `tsp_size_descending` | TSP size descending |
| `tsp_random_perm_1` | TSP randomized ordering 1 |
| `tsp_random_perm_2` | TSP randomized ordering 2 |
| `cvrp_size_ascending` | CVRP size ascending |
| `cvrp_size_descending` | CVRP size descending |
| `jssp_size_ascending` | JSSP size ascending |
| `jssp_size_descending` | JSSP size descending |
| `cross_problem_tsp_cvrp_jssp` | TSP -> CVRP -> JSSP |
| `tsp_stationary` | TSP stationary control |
| `tsp_revisit` | TSP revisit stream |
| `related_pair_tsp_cvrp_tsp` | Related cross-domain pair |
| `unrelated_pair_tsp_jssp_tsp` | Unrelated cross-domain pair |

---

## 4. Setup

Run from the `HeurAgenix` directory:

```powershell
cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
uv sync
uv run cmhh --help
uv run cmhh run-suite --help
```

LLM runs need:

```text
cmhh/configs/llm/llm_config.local.json
```

Example:

```json
{
  "type": "api_model",
  "name": "nvidia-gpt-oss-120b",
  "url": "https://integrate.api.nvidia.com/v1/chat/completions",
  "api_key": "your-api-key-here",
  "model": "openai/gpt-oss-120b",
  "temperature": 1,
  "max_tokens": 4096,
  "max_attempts": 5,
  "seed": 42
}
```

---

## 5. Execution commands

Smoke test without LLM:

```powershell
uv run cmhh run-suite --streams tsp_n20_smoke --conditions isolated --seeds 1 --mode smoke --skip-references --no-wandb
```

Quick LLM smoke:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending --conditions isolated --seeds 1 --mode quick-smoke --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Pilot run:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending,cvrp_size_ascending,jssp_size_ascending --conditions isolated,population,managed --seeds 1,2,3 --mode pilot --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Full benchmark for one stream:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Full benchmark for all streams:

```powershell
uv run cmhh run-suite --all-streams --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Resume:

```powershell
uv run cmhh run-suite --all-streams --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --resume --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 6. Server or SLURM example

On a server, the command is the same. Example using one seed from an array job:

```bash
cd /path/to/CM_HH/HeurAgenix
uv sync
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated,population,managed --seeds "$SLURM_ARRAY_TASK_ID" --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 7. Outputs

Results are stored under:

```text
cmhh/results/<run_id>/
```

Important files:

```text
resolved_config.yaml
manifest.json
metrics.json
performance_matrix.csv
events.jsonl
cold_start_scores.json
memory/
```

`resolved_config.yaml` records the exact resolved run settings after applying mode, seed, generator, stream, and budget overrides.

---

## 8. Debug commands

Most experiments should use `run-suite`. These lower-level commands are only for debugging:

```powershell
uv run cmhh validate-config --experiment cmhh/configs/experiments/h1_isolated.yaml
uv run cmhh generate-data --experiment cmhh/configs/experiments/h1_isolated.yaml --seed 42
uv run cmhh generate-references --experiment cmhh/configs/experiments/h1_isolated.yaml --split validation --split test --pilot-count 5
uv run cmhh verify-references --experiment cmhh/configs/experiments/h1_isolated.yaml --split validation --split test
uv run cmhh audit-run --run-id <run_id>
```

---

## 9. Windows compatibility wrappers

These still work on Windows:

```powershell
.\scripts\run_all_streams_no_eoh.ps1 -Pilot -Seeds 1,2,3
.\scripts\run_stream_8_cvrp_descending.ps1 -Seed 1
```

Do not use them in cross-platform documentation, server scripts, or SLURM jobs.
