# CM-HH Phase 1 experiment guide

Phase 1 dung de so sanh cac condition hoc lien tuc tren cac stream TSP/CVRP/JSSP. Cach chay canonical hien nay la:

```powershell
uv run cmhh run-suite ...
```

Khong can tu viet vong lap PowerShell hoac goi tung subcommand cap thap cho tung condition nua. `run-suite` se xu ly stream, seed, condition, run id, prepare reference/data va ghi `resolved_config.yaml`.

---

## 1. Setup

Chay tu thu muc `HeurAgenix`:

```powershell
cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
uv sync
uv run cmhh --help
uv run cmhh run-suite --help
```

Neu chay voi LLM, cau hinh:

```text
cmhh/configs/llm/llm_config.local.json
```

---

## 2. Kiem tra config/data/reference

Prepare-only cho mot stream:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending --conditions isolated --seeds 1 --mode smoke --prepare-only --skip-references --no-wandb
```

Neu muon validate/generate/verify references, bo `--skip-references`:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending --conditions isolated --seeds 1 --mode smoke --prepare-only --no-wandb
```

---

## 3. Smoke run

Smoke nho nhat:

```powershell
uv run cmhh run-suite --streams tsp_n20_smoke --conditions isolated --seeds 1 --mode smoke --skip-references --no-wandb
```

Smoke cho stream Phase 1:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending --conditions isolated,population,managed --seeds 1 --mode smoke --skip-references --no-wandb
```

---

## 4. Pilot run

Pilot voi LLM tren mot stream:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending --conditions isolated,population,managed --seeds 1,2,3 --mode pilot --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Pilot tren tap stream mac dinh:

```powershell
uv run cmhh run-suite --mode pilot --seeds 1,2,3 --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 5. Full Phase 1 benchmark

Full cho TSP ascending:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Full cho nhieu stream Phase 1:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending,tsp_size_descending,cvrp_size_ascending,cvrp_size_descending,jssp_size_ascending,jssp_size_descending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Resume neu bi gian doan:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --resume --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 6. Conditions trong Phase 1

| Condition | Y nghia |
|---|---|
| `isolated` | Cold start doc lap tung task |
| `population` | Population carryover |
| `naive-bounded` | Naive memory co gioi han |
| `naive-unbounded` | Naive memory khong gioi han |
| `managed` | CM-HH Archivist managed |

---

## 7. File ket qua can xem

Moi run nam trong:

```text
cmhh/results/<run_id>/
```

Cac file chinh:

```text
resolved_config.yaml
manifest.json
metrics.json
performance_matrix.csv
events.jsonl
cold_start_scores.json
memory/
```

`resolved_config.yaml` la file nen dinh kem hoac luu lai khi tai lap thuc nghiem, vi no ghi cau hinh sau khi da ap dung mode, seed va override runtime.

---

## 8. Lenh cap thap chi dung khi debug

Van co the dung cac subcommand cap thap neu can debug rieng tung buoc:

```powershell
uv run cmhh validate-config --experiment cmhh/configs/experiments/h1_isolated.yaml
uv run cmhh generate-data --experiment cmhh/configs/experiments/h1_isolated.yaml --seed 42
uv run cmhh generate-references --experiment cmhh/configs/experiments/h1_isolated.yaml --split validation --split test --pilot-count 5
uv run cmhh verify-references --experiment cmhh/configs/experiments/h1_isolated.yaml --split validation --split test
```

Cho experiment thong thuong, uu tien `run-suite` thay vi ghep nhieu lenh debug thu cong.
