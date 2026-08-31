# CM-HH run-suite handoff guide

Tai lieu nay thay the huong dan cu dua tren `run_all_streams_no_eoh.ps1`. Duong chay canonical hien nay la:

```powershell
uv run cmhh run-suite ...
```

PowerShell scripts trong `scripts/` van ton tai de tuong thich nguoc, nhung chi nen xem la wrapper mong.

---

## 1. Setup

Chay tu thu muc `HeurAgenix`:

```powershell
cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
uv sync
uv run cmhh run-suite --help
```

---

## 2. Smoke checks

Smoke nho nhat, khong dung LLM:

```powershell
uv run cmhh run-suite --streams tsp_n20_smoke --conditions isolated --seeds 1 --mode smoke --skip-references --no-wandb
```

Smoke cho mot stream that:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated --seeds 1 --mode smoke --skip-references --no-wandb
```

Quick smoke co LLM:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated --seeds 1 --mode quick-smoke --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 3. Pilot run

Pilot cho 3 stream dai dien:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending,cvrp_size_ascending,jssp_size_ascending --conditions isolated,population,managed --seeds 1,2,3 --mode pilot --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Pilot cho tap stream pilot mac dinh:

```powershell
uv run cmhh run-suite --mode pilot --seeds 1,2,3 --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 4. Full benchmark

Full benchmark cho mot stream:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Full benchmark cho tat ca streams:

```powershell
uv run cmhh run-suite --all-streams --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Resume neu bi gian doan:

```powershell
uv run cmhh run-suite --all-streams --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --resume --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 5. Streams

| Stream id | Noi dung |
|---|---|
| `tsp_size_ascending` | TSP tang dan |
| `tsp_size_descending` | TSP giam dan |
| `tsp_random_perm_1` | TSP thu tu ngau nhien 1 |
| `tsp_random_perm_2` | TSP thu tu ngau nhien 2 |
| `cvrp_size_ascending` | CVRP tang dan |
| `cvrp_size_descending` | CVRP giam dan |
| `jssp_size_ascending` | JSSP tang dan |
| `jssp_size_descending` | JSSP giam dan |
| `cross_problem_tsp_cvrp_jssp` | TSP -> CVRP -> JSSP |
| `tsp_stationary` | TSP stationary |
| `tsp_revisit` | TSP revisit |
| `related_pair_tsp_cvrp_tsp` | Related pair |
| `unrelated_pair_tsp_jssp_tsp` | Unrelated pair |

---

## 6. Conditions

| Condition | Experiment config |
|---|---|
| `isolated` | `cmhh/configs/experiments/h1_isolated.yaml` |
| `population` | `cmhh/configs/experiments/h1_population_carryover.yaml` |
| `naive-bounded` | `cmhh/configs/experiments/h1_naive_sequential.yaml` |
| `naive-unbounded` | `cmhh/configs/experiments/h1_naive_unbounded.yaml` |
| `managed` | `cmhh/configs/experiments/archivist_managed.yaml` |

---

## 7. Ket qua

Ket qua nam trong:

```text
cmhh/results/<run_id>/
```

Moi run nen co:

```text
resolved_config.yaml
manifest.json
metrics.json
performance_matrix.csv
events.jsonl
```

`resolved_config.yaml` la file quan trong de tai lap thuc nghiem, vi no ghi lai config sau khi mode, seed, generator va budget override da duoc resolve.

---

## 8. Wrapper PowerShell cu

Lenh cu van dung duoc tren Windows:

```powershell
.\scripts\run_all_streams_no_eoh.ps1 -Pilot -Seeds 1,2,3
.\scripts\run_stream_8_cvrp_descending.ps1 -Seed 1
```

Nhung khi ban viet lenh moi, hay chuyen thanh:

```powershell
uv run cmhh run-suite --mode pilot --seeds 1,2,3
uv run cmhh run-suite --streams cvrp_size_descending --seeds 1 --mode quick-smoke
```
