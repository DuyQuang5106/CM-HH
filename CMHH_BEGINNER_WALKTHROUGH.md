# CMHH - Huong dan walkthrough va chay thuc nghiem

**Du an:** Continual Multi-Agent Hyper-Heuristics (CM-HH)

File nay giup nguoi moi cai moi truong, chay smoke test, chay pilot/full benchmark va doc ket qua. Cach chay chinh hien nay la Python CLI:

```powershell
uv run cmhh ...
```

PowerShell scripts trong `HeurAgenix/scripts/` chi con la wrapper tuong thich nguoc. Khi viet lenh moi, khi chay tren Linux/server/SLURM, hoac khi ghi vao paper protocol, hay dung `uv run cmhh`.

---

## 1. CM-HH la gi?

CM-HH huan luyen agent/LLM sinh va tien hoa heuristic qua mot chuoi bai toan toi uu to hop:

```text
T1 -> T2 -> T3 -> ... -> TK
```

Muc tieu la vua hoc tot task hien tai, vua tan dung tri thuc tu task truoc, dong thoi han che quen tri thuc cu.

Luong xu ly chinh:

```text
Task hoan thanh
  -> CandidateExtractor
  -> Archivist Gatekeeper
  -> MemoryStore
  -> Retriever Engine
  -> TransferPolicy
  -> PopulationBuilder
  -> Evolution
  -> Transfer Feedback
```

---

## 2. Setup moi truong

Mo terminal tai thu muc project:

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

Neu dung LLM, tao hoac sua file:

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

## 3. Cac mode chay

| Mode | Muc dich | Generator mac dinh | Ghi chu |
|---|---|---|---|
| `smoke` | Kiem tra nhanh, khong ton token LLM | `baseline` | Nen chay dau tien |
| `quick-smoke` | Kiem tra pipeline LLM ngan | `heuragenix` | Budget rat nho |
| `pilot` | Chay thu nghiem nghiem tuc hon | `heuragenix` | Phu hop truoc khi full |
| `full` | Benchmark chinh thuc | `heuragenix` | Dung budget trong config |

`smoke` va `quick-smoke` duoc tach rieng: `smoke` de kiem tra du lieu/runner khong can LLM, con `quick-smoke` de kiem tra pipeline co LLM voi ngan sach nho.

---

## 4. Chay nhanh nhat de kiem tra

Smoke test nho nhat:

```powershell
uv run cmhh run-suite --streams tsp_n20_smoke --conditions isolated --seeds 1 --mode smoke --skip-references --no-wandb
```

Chay stream dang quan tam, vi du `cvrp_size_descending`:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated --seeds 1 --mode smoke --skip-references --no-wandb
```

Chay prepare-only de kiem tra config/data/reference ma chua tien hoa:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated --seeds 1 --mode smoke --prepare-only --skip-references --no-wandb
```

---

## 5. Chay tung stream

Cu phap chung:

```powershell
uv run cmhh run-suite --streams <stream_id> --conditions <conditions> --seeds <seeds> --mode <mode>
```

Danh sach stream chinh:

| Stream id | Mo ta |
|---|---|
| `tsp_size_ascending` | TSP tang dan kich thuoc |
| `tsp_size_descending` | TSP giam dan kich thuoc |
| `tsp_random_perm_1` | TSP thu tu ngau nhien 1 |
| `tsp_random_perm_2` | TSP thu tu ngau nhien 2 |
| `cvrp_size_ascending` | CVRP tang dan kich thuoc |
| `cvrp_size_descending` | CVRP giam dan kich thuoc |
| `jssp_size_ascending` | JSSP tang dan kich thuoc |
| `jssp_size_descending` | JSSP giam dan kich thuoc |
| `cross_problem_tsp_cvrp_jssp` | Chuyen giao TSP -> CVRP -> JSSP |
| `tsp_stationary` | TSP mien tinh |
| `tsp_revisit` | TSP co task quay lai |
| `related_pair_tsp_cvrp_tsp` | Cap mien lien quan |
| `unrelated_pair_tsp_jssp_tsp` | Cap mien it lien quan |

Vi du chay pilot cho CVRP descending:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated,population,managed --seeds 1,2,3 --mode pilot --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Vi du chay full benchmark cho CVRP descending:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 6. Chay nhieu stream hoac toan bo suite

Chay mot tap stream:

```powershell
uv run cmhh run-suite --streams tsp_size_ascending,cvrp_size_ascending,jssp_size_ascending --conditions isolated,population,managed --seeds 1,2,3 --mode pilot --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Chay toan bo stream mac dinh:

```powershell
uv run cmhh run-suite --all-streams --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Resume khi bi gian doan:

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated,population,managed --seeds 1,2,3 --mode pilot --resume --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 7. Cac condition hop le

| Condition | Y nghia |
|---|---|
| `isolated` | Cold start doc lap tung task |
| `population` | Ke thua population tu task truoc |
| `naive-bounded` | Bo nho tho co gioi han |
| `naive-unbounded` | Bo nho tho khong gioi han |
| `managed` | CM-HH day du voi Archivist/Retriever/Transfer Policy |

Alias cu van duoc CLI chap nhan trong nhieu truong hop, nhung nen dung ten canonical trong bang tren.

---

## 8. Khi nao dung `run-stream`?

Thong thuong hay dung `run-suite`, vi no tu lo multi-seed, multi-condition, run id va resolved config.

Dung `run-stream` khi muon chi dinh truc tiep mot experiment YAML:

```powershell
uv run cmhh run-stream --experiment cmhh/configs/experiments/h1_population_carryover.yaml --stream cvrp_size_descending --seeds 1,2,3 --mode pilot --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 9. Ghi chu ve PowerShell wrapper

Mot so file PowerShell cu van ton tai trong `HeurAgenix/scripts/` de tuong thich voi Windows. Khong dung chung lam huong dan chinh vi macOS/Linux/server se khong chay truc tiep duoc. Khi viet tai lieu moi, automation, server script, hoac SLURM job, hay dung:

```powershell
uv run cmhh run-suite ...
```

---

## 10. Giam sat va doc ket qua

Ket qua nam trong:

```text
cmhh/results/<run_id>/
```

Cac file quan trong:

```text
resolved_config.yaml       Cau hinh da resolve thuc su dung cho run
manifest.json              Metadata cua run
metrics.json               AF, BWT, FWT va cac chi so tong hop
performance_matrix.csv     Ma tran hieu nang qua cac task
events.jsonl               Nhat ky su kien
cold_start_scores.json     Diem cold-start cho isolated
memory/                    Bo nho va diagnostics neu condition co memory
```

Tren macOS/Linux/server, co the xem log bang:

```bash
tail -f cmhh/results/<run_id>/events.jsonl
```

Tren Windows, co the mo truc tiep cac file `metrics.json`, `performance_matrix.csv`, `events.jsonl` trong thu muc ket qua.

---

## 11. Protocol khuyen nghi cho paper

1. Chay `smoke` voi `--skip-references` de kiem tra pipeline.
2. Chay `quick-smoke` voi LLM config de kiem tra API/token.
3. Chay `pilot` tren 1-3 streams va 1-3 seeds.
4. Chay `full` tren 3-5 seeds cho moi stream/condition.
5. Bao cao ket qua theo mean +/- std qua cac seed.

Lenh full mau:

```powershell
uv run cmhh run-suite --all-streams --conditions isolated,population,naive-bounded,naive-unbounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```
