# CM-HH run-suite handoff guide

Tài liệu này là hướng dẫn chuẩn bàn giao quy trình chạy thực nghiệm CM-HH đa nền tảng (Windows / Linux / macOS / SLURM). Lệnh canonical duy nhất:

```powershell
uv run cmhh run-suite ...
```

---

## 1. Setup

Chạy từ thư mục `HeurAgenix`:

```powershell
cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
uv sync
uv run cmhh run-suite --help
```

---

## 2. Smoke checks

Smoke Suite hoàn toàn không dùng LLM (kiểm tra runner/dữ liệu):

```powershell
uv run cmhh run-suite --suite pilot_small_smoke --generator baseline --skip-references --no-wandb
```

Quick smoke có LLM (kiểm tra API key và pipeline LLM):

```powershell
uv run cmhh run-suite --streams tsp_size_up_small --conditions isolated --seeds 1 --mode quick-smoke --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 3. Pilot run (Small-Scale Pilot Stream Suite)

Chạy bộ 5 stream pilot (`pilot_small`):

```powershell
uv run cmhh run-suite --suite pilot_small --mode pilot --generator heuragenix --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Chạy riêng 1 stream pilot:

```powershell
uv run cmhh run-suite --streams related_pair_small --conditions isolated,managed --seeds 1 --mode pilot --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 4. Full benchmark

Full benchmark cho một stream (5 seeds):

```powershell
uv run cmhh run-suite --streams cvrp_size_descending --conditions isolated,naive-bounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Full benchmark cho tất cả streams:

```powershell
uv run cmhh run-suite --all-streams --conditions isolated,naive-bounded,managed --seeds 1,2,3,4,5 --mode full --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

Phục hồi nếu bị gián đoạn:

```powershell
uv run cmhh run-suite --suite pilot_small --mode pilot --resume --llm-config cmhh/configs/llm/llm_config.local.json --no-wandb
```

---

## 5. Danh Mục Streams & Suites

### Pilot Streams (100% Ready)
- `tsp_size_up_small`: $20 \to 50 \to 100$
- `tsp_size_down_small`: $100 \to 50 \to 20$
- `tsp_variant_revisit_small`: $50A \to \text{Clustered } 50 \to 50B$
- `related_pair_small`: $50A \to \text{CVRP } n30 \to 50B$
- `unrelated_pair_small`: $50A \to \text{JSSP } 10\times5 \to 50B$
- `tsp_stationary_small`: $50A \to 50B \to 50C$
- `tsp_n20_smoke`: Single task smoke

### Benchmark Streams (100% Ready)
- `tsp_size_ascending`, `tsp_size_descending`, `tsp_random_perm_1`, `tsp_random_perm_2`
- `cvrp_size_ascending`, `cvrp_size_descending`
- `jssp_size_ascending`, `jssp_size_descending`
- `cross_problem_tsp_cvrp_jssp`, `tsp_revisit`
- `related_pair_tsp_cvrp_tsp`, `unrelated_pair_tsp_jssp_tsp`

---

## 6. Conditions

| Condition | Ý Nghĩa |
|---|---|
| `isolated` | Cold start độc lập từng task, không chuyển giao tri thức |
| `population` | Kế thừa quần thể cuối cùng từ task trước |
| `naive-bounded` | Bộ nhớ thô tuần tự có giới hạn dung lượng |
| `naive-unbounded` | Bộ nhớ thô không giới hạn dung lượng |
| `managed` | CM-HH đầy đủ với Archivist, Retriever và Transfer Policy |

---

## 7. Kết Quả & Nghiệm Thu

Kết quả lưu tại `cmhh/results/<run_id>/`:
- `performance_matrix.csv`: Ma trận Relative Gap $R_{k,j}$.
- `transfer_diagnostics.csv`: Thống kê chuyển giao per-transition.
- `metrics.json`: $AF$, $BWT$, $FWT$.
- `events.jsonl`: Machine log khoa học (`schema_version: 1`).
- `llm_calls.jsonl`: Telemetry LLM calls.
- `resolved_config.yaml`: Snapshot cấu hình phục vụ tái lập kết quả.

