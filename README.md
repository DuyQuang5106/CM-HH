# CMHH — Continual Multi-Agent Hyper-Heuristics

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Package Manager](https://img.shields.io/badge/uv-managed-purple.svg)](https://docs.astral.sh/uv/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-research--ready-success.svg)](#)

Official implementation of **CM-HH (Continual Multi-Agent Hyper-Heuristics)** — a research framework for persistent, non-forgetting LLM-based heuristic search and evolutionary optimization across sequential combinatorial task streams.

---

## 📚 Documentation Index (Tài Liệu Hướng Dẫn)

| Tài Liệu | Mục Đích & Nội Dung | Đối Tượng |
|---|---|---|
| 🚀 [**`CMHH_BEGINNER_WALKTHROUGH.md`**](CMHH_BEGINNER_WALKTHROUGH.md) | **Hướng dẫn toàn diện cho người mới**: Cài đặt với `uv`, kiến trúc 3 lớp, reference solvers, chạy song song 4 tab qua đêm. | Newcomers / Engineers |
| 🧪 [**`CMHH_EXPERIMENT_GUIDE.md`**](CMHH_EXPERIMENT_GUIDE.md) | **Hướng dẫn thử nghiệm & phân tích chỉ số**: Giao thức thí nghiệm, các stream active, $AF$, $BWT$, $FWT$, ma trận chuyển giao. | ML / PhD Researchers |
| 📌 [**`CMHH_STEP_BY_STEP_EXECUTION_GUIDE.md`**](CMHH_STEP_BY_STEP_EXECUTION_GUIDE.md) | **Lộ trình thực thi chi tiết**: Lệnh chạy từng stream, multi-condition (isolated, population, naive-bounded, managed). | Experiment Operators |
| 🛠️ [**`CMHH_ENGINEERING_HANDOFF_REVIEW.md`**](CMHH_ENGINEERING_HANDOFF_REVIEW.md) | **Báo cáo kiến trúc hệ thống**: Lịch sử tái cấu trúc, safety invariants, memory lifecycle, 3-layer runtime guard. | Core Maintainers |

---

## ⚡ Cài Đặt Môi Trường (Setup trong 30 Giây)

Dự án được quản lý tiêu chuẩn bằng [`uv`](https://docs.astral.sh/uv/):

```powershell
# Chuyển vào thư mục HeurAgenix và đồng bộ môi trường
cd HeurAgenix
uv sync

# Kiểm tra CLI
uv run cmhh --help
uv run cmhh run-suite --help
```

*Lưu ý: Bộ giải nghiệm tối ưu/SOTA Concorde (cho TSP), PyVRP (cho VRP/OVRP/VRPTW/OVRPTW) và OR-Tools CP-SAT (cho JSSP) đã được tích hợp sẵn trong repository.*

---

## 🔬 Hướng Dẫn Chạy Thực Nghiệm (Canonical UV CLI)

### 1. Kiểm Tra Nhanh (Smoke Test — Không Tốn Token LLM)
```powershell
# Chạy Smoke Suite (kiểm tra solver, pipeline, dữ liệu)
uv run cmhh run-suite --suite pilot_small_smoke --generator baseline --skip-references --no-wandb
```

### 2. Chuẩn Bị Dữ Liệu & Cache Reference Solvers
```powershell
# Chuẩn bị dữ liệu và tính trước nghiệm tham chiếu cho stream
uv run cmhh run-suite --streams s3_related_cross_problem --seeds 1 --mode full --prepare-only --no-wandb
```

---

### 3. Danh Mục Các Stream Chuẩn Đang Hoạt Động (Active Streams)

#### A. Nhóm 4 Pilot Streams (`cmhh/configs/streams/pilot/`)

| Stream ID | Phân Loại / Mục Đích | Chuỗi Chuyển Giao | Lệnh Chạy (1 Seed) |
|---|---|---|---|
| `s1_tsp_scale` | Scale Shift ($N=20 \to 50 \to 100$) | $\text{TSP}_{n20\text{-A}} \to \text{TSP}_{n50\text{-A}} \to \text{TSP}_{n100\text{-A}} \to \text{TSP}_{n20\text{-B}}$ | `uv run cmhh run-suite --streams s1_tsp_scale --seeds 1 --mode full --wandb --resume` |
| `s2_cvrp_constraint` | Constraint Shift (VRP Variant) | $\text{CVRP}_{n50} \to \text{OVRP}_{n50} \to \text{VRPTW}_{n50} \to \text{CVRP}_{n50\text{-Anchor}}$ | `uv run cmhh run-suite --streams s2_cvrp_constraint --seeds 1 --mode full --wandb --resume` |
| `s3_related_cross_problem` | Related Cross-Domain | $\text{TSP}_{n50\text{-A}} \to \text{CVRP}_{n50\text{-Med}} \to \text{TSP}_{n50\text{-B}}$ | `uv run cmhh run-suite --streams s3_related_cross_problem --seeds 1 --mode full --wandb --resume` |
| `s4_unrelated_cross_problem` | Unrelated Negative Transfer | $\text{TSP}_{n50\text{-A}} \to \text{JSSP}_{10\times5} \to \text{TSP}_{n50\text{-B}}$ | `uv run cmhh run-suite --streams s4_unrelated_cross_problem --seeds 1 --mode full --wandb --resume` |
| `s5_vrp_variant` | VRP Constraint Variant Shift | $\text{CVRP} \to \text{OVRP} \to \text{OVRPTW} \to \text{VRPTW}$ | `uv run cmhh run-suite --streams s5_vrp_variant --seeds 1 --mode full --wandb --resume` |

#### B. Nhóm VRP Constraint Graycode Streams (`cmhh/configs/streams/`)

| Stream ID | Chuỗi Chuyển Giao Biến Đổi Ràng Buộc 1-Bit | Lệnh Chạy (1 Seed) |
|---|---|---|
| `vrp_constraint_graycode` | $\text{CVRP} \longrightarrow \text{OVRP} \longrightarrow \text{VRPTW} \longrightarrow \text{OVRPTW}$ | `uv run cmhh run-suite --streams vrp_constraint_graycode --seeds 1 --mode full --wandb --resume` |
| `vrp_constraint_graycode_reverse` | $\text{OVRPTW} \longrightarrow \text{VRPTW} \longrightarrow \text{OVRP} \longrightarrow \text{CVRP}$ | `uv run cmhh run-suite --streams vrp_constraint_graycode_reverse --seeds 1 --mode full --wandb --resume` |

---

### 4. Chạy Song Song 4 Tab PowerShell Cho 4 Điều Kiện (Cắm Máy Qua Đêm)

Mở 4 tab PowerShell tại thư mục `HeurAgenix`:

* **Tab 1 (`isolated` + `population`)**:
  ```powershell
  uv run cmhh run-suite --streams s3_related_cross_problem --conditions isolated,population --seeds 1 --mode full --run-prefix s3_full --wandb --resume
  ```
* **Tab 2 (`naive-bounded`)**:
  ```powershell
  uv run cmhh run-suite --streams s3_related_cross_problem --conditions naive-bounded --seeds 1 --mode full --run-prefix s3_full --wandb --resume
  ```
* **Tab 3 (`naive-unbounded`)**:
  ```powershell
  uv run cmhh run-suite --streams s3_related_cross_problem --conditions naive-unbounded --seeds 1 --mode full --run-prefix s3_full --wandb --resume
  ```
* **Tab 4 (`managed`)**:
  ```powershell
  uv run cmhh run-suite --streams s3_related_cross_problem --conditions managed --seeds 1 --mode full --run-prefix s3_full --wandb --resume
  ```

---

## 📊 Cấu Trúc Kết Quả

Sau mỗi lượt chạy, toàn bộ dữ liệu thực nghiệm được lưu tự động tại `cmhh/results/<run_id>/`:
1. `performance_matrix.csv`: Ma trận hiệu năng chuyển giao $R_{k,j}$ (Relative Gap).
2. `transfer_diagnostics.csv`: Bảng chẩn đoán chi tiết hành vi chuyển giao per-transition.
3. `metrics.json`: Các chỉ số tổng hợp $AF$ (Average Final Performance), $BWT$ (Backward Transfer), $FWT$ (Forward Transfer).
4. `events.jsonl`: Toàn bộ nhật ký sự kiện khoa học (`schema_version: 1`, ISO-8601 UTC).
5. `llm_calls.jsonl`: Telemetry chi tiết từng lượt gọi LLM (model, prompt tokens, latency, status).
6. `memory/`: Snapshot bộ nhớ tri thức, vector embeddings và lineage đào thải.
7. `resolved_config.yaml`: Cấu hình hoàn chỉnh đã resolve để phục vụ tái lập 100% kết quả.
