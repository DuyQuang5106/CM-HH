# CMHH - Step-by-step execution guide

Day la quy trinh chay thuc nghiem theo cach moi. Lenh canonical dung duoc tren Windows, macOS, Linux va server la:

```powershell
uv run cmhh run-suite ...
```

PowerShell scripts trong `HeurAgenix/scripts/` chi la wrapper tuong thich nguoc cho Windows.

---

## 0. Roadmap

```text
Setup
  -> cd HeurAgenix
  -> uv sync
  -> uv run cmhh --help

Smoke
  -> uv run cmhh run-suite --mode smoke ...

Quick smoke co LLM
  -> uv run cmhh run-suite --mode quick-smoke ...

Pilot
  -> uv run cmhh run-suite --mode pilot --seeds 1,2,3 ...

Full benchmark
  -> uv run cmhh run-suite --mode full --seeds 1,2,3,4,5 ...

Results
  -> cmhh/results/<run_id>/
```

---

## 1. Setup

Chay tu thu muc `HeurAgenix`:

```powershell
cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
uv sync
```

Kiem tra CLI:

```powershell
uv run cmhh --help
uv run cmhh run-suite --help
uv run cmhh run-stream --help
```

---

## 2. Cau hinh LLM

Neu chay `quick-smoke`, `pilot`, hoac `full`, can file LLM config:

```text
cmhh/configs/llm/llm_config.local.json
```

Vi du:

```json
{
  "type": "api_model",
  "name": "nvidia-gpt-oss-120b",
  "url": "https://integrate.api.nvidia.com/v1/chat/completions",
  "api_key": "dien-key-cua-ban",
  "model": "openai/gpt-oss-120b",
  "temperature": 1,
  "max_tokens": 4096,
  "max_attempts": 5,
  "seed": 42
}
```

---

## 3. Smoke check

Smoke nho nhat, khong dung LLM:

```powershell
uv run cmhh run-suite --streams tsp_n20_smoke --conditions isolated --seeds 1 --mode smoke --skip-references --no-wandb
```

Smoke cho stream CVRP descending:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated --seeds 1 --mode smoke --skip-references --no-wandb
```

Prepare-only, chi kiem tra setup/config/reference:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated --seeds 1 --mode smoke --prepare-only --skip-references --no-wandb
```

---

## 4. Quick smoke co LLM

Dung de kiem tra API key va pipeline LLM voi budget nho:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated --seeds 1 --mode quick-smoke --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 5. Chay tung stream

Cu phap chung:

```powershell
uv run cmhh run-suite --streams <stream_id> --conditions <conditions> --seeds <seeds> --mode <mode>
```

Bang lenh cho 13 stream:

| STT | Stream | Lenh full 5 seeds |
|---:|---|---|
| 1 | `tsp_size_ascending` | `uv run cmhh run-suite --streams tsp_size_ascending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 2 | `tsp_size_descending` | `uv run cmhh run-suite --streams tsp_size_descending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 3 | `tsp_random_perm_1` | `uv run cmhh run-suite --streams tsp_random_perm_1 --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 4 | `tsp_random_perm_2` | `uv run cmhh run-suite --streams tsp_random_perm_2 --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 5 | `cvrp_size_ascending` | `uv run cmhh run-suite --streams cvrp_size_ascending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 6 | `cvrp_size_descending` | `uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 7 | `jssp_size_ascending` | `uv run cmhh run-suite --streams jssp_size_ascending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 8 | `jssp_size_descending` | `uv run cmhh run-suite --streams jssp_size_descending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 9 | `cross_problem_tsp_cvrp_jssp` | `uv run cmhh run-suite --streams cross_problem_tsp_cvrp_jssp --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 10 | `tsp_stationary` | `uv run cmhh run-suite --streams tsp_stationary --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 11 | `tsp_revisit` | `uv run cmhh run-suite --streams tsp_revisit --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 12 | `related_pair_tsp_cvrp_tsp` | `uv run cmhh run-suite --streams related_pair_tsp_cvrp_tsp --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |
| 13 | `unrelated_pair_tsp_jssp_tsp` | `uv run cmhh run-suite --streams unrelated_pair_tsp_jssp_tsp --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb` |

---

## 6. Chay nhieu stream

Pilot cho vai stream dai dien:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending,cvrp_size_ascending,jssp_size_ascending --conditions isolated,population,managed --seeds 1,2,3 --mode pilot --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Full cho tat ca stream:

```powershell
uv run cmhh run-suite --all-streams --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Resume:

```powershell
uv run cmhh run-suite --all-streams --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --resume --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 7. Xem ket qua

Ket qua nam trong:

```text
cmhh/results/<run_id>/
```

File quan trong:

```text
resolved_config.yaml
manifest.json
metrics.json
performance_matrix.csv
events.jsonl
memory/
```

`resolved_config.yaml` giup tai lap run vi no ghi lai mode, seed, generator va budget sau khi resolve.

---

## 8. Audit run

Neu can audit rieng mot run:

```powershell
uv run cmhh audit-run --run-id <run_id>
```

---

## 9. Ghi chu ve PowerShell

Lenh `.ps1` cu chi dung tren Windows va chi nen dung khi can tuong thich nguoc. Tren macOS/Linux/server/SLURM, dung `uv run cmhh run-suite`.
