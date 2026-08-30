# CMHH — Continual Multi-Agent Hyper-Heuristics

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-research--ready-success.svg)](#)

Official implementation of **CMHH (Continual Multi-Agent Hyper-Heuristics)** — a research framework for persistent, non-forgetting LLM-based heuristic search and evolutionary optimization across sequential combinatorial task streams.

---

## 2026-08-29 Architecture Status

CM-HH memory is now documented as a full transfer pipeline:

```text
CandidateExtractor -> Archivist -> MemoryStore -> Retriever
    -> TransferPolicy -> PopulationBuilder -> evolution -> transfer feedback
```

The current `archivist_managed` experiment is a runnable managed-memory
prototype. Treat it as "full CM-HH" only after `CandidateExtractor`,
`TransferPolicy`, `PopulationBuilder`, validation-only transfer feedback, and
child-memory lineage are implemented and audited.

See `IDEA/source_of_truth/CMHH_Archivist_Retriever_Design_Specification.md`
for the authoritative architecture and pseudocode.

---

## 📚 Documentation Index (Tài Liệu Hướng Dẫn)

| File Documentation | Mục đích & Nội dung | Đối tượng |
|---|---|---|
| 🚀 [**`CMHH_BEGINNER_WALKTHROUGH.md`**](CMHH_BEGINNER_WALKTHROUGH.md) | **Hướng dẫn từng bước cho người mới (Quickstart 5 phút)**, giải thích sơ đồ 5 phần, chạy lệnh đầu tiên và cách đọc ma trận kết quả | Người mới bắt đầu / Sinh viên / ML Engineer |
| 📌 [**`CMHH_STEP_BY_STEP_EXECUTION_GUIDE.md`**](CMHH_STEP_BY_STEP_EXECUTION_GUIDE.md) | **Lộ trình chạy từng bước có đánh số (từ 1 đến 8)** kèm các câu lệnh PowerShell copy-paste trực tiếp | Người trực tiếp chạy thí nghiệm |
| 📊 [**`CMHH_EXPERIMENT_GUIDE.md`**](CMHH_EXPERIMENT_GUIDE.md) | **Hướng dẫn thử nghiệm chuyên sâu & đọc chỉ số**, giải thích chi tiết $R_{k,j}$, $AF$, $BWT$, $FWT$, `diagnostics.json` và `eviction_lineage` | PhD / ML Research Engineers |
| 🛠️ [**`CMHH_ENGINEERING_HANDOFF_REVIEW.md`**](CMHH_ENGINEERING_HANDOFF_REVIEW.md) | **Báo cáo kiểm định kiến trúc & lịch sử tái cấu trúc hệ thống**, phân tích 5 giai đoạn hoàn thiện codebase | Core Maintainers / Code Auditors |
| 📄 [**`IDEA/source_of_truth/CMHH_Research_Specification.md`**](IDEA/source_of_truth/CMHH_Research_Specification.md) | **Tài liệu đặc tả bài báo nghiên cứu (Research Specs)** | Scientific Research Team |

---

## ⚡ Setup & Quickstart với `uv`

### 1. Cài đặt môi trường với `uv`
Repo sử dụng `pyproject.toml` và `uv` để quản lý dependencies nhanh và ổn định:

```powershell
# Cài đặt toàn bộ dependencies vào virtual environment .venv
uv sync
```

### 2. Chạy thử nghiệm qua `uv` (Console Script hoặc Module)
```powershell
# Kiểm tra cấu hình hệ thống
uv run cmhh --repo-root HeurAgenix validate-config

# Hoặc dùng python module:
uv run python -m cmhh.cli --repo-root HeurAgenix validate-config
```

### 3. Sinh dữ liệu benchmark & nghiệm tối ưu chuẩn
```powershell
# Sinh dữ liệu bài toán TSPLIB
uv run cmhh --repo-root HeurAgenix generate-data --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --seed 42

# Sinh nghiệm tối ưu tuyệt đối bằng Concorde exact solver
uv run cmhh --repo-root HeurAgenix generate-references --solver-config HeurAgenix/cmhh/configs/solvers/concorde.yaml --split validation --split test
```

### 4. Chạy luồng học liên tục (Continual Stream Run)
```powershell
uv run cmhh --repo-root HeurAgenix run-stream `
  --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml `
  --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml `
  --generator heuragenix `
  --llm-config HeurAgenix/data/llm_config/cmhh_phase1.json `
  --seed 42 `
  --run-id my_cmhh_run
```

---

## 📈 Experiment Tracking with Weights & Biases (`wandb`)

CM-HH tích hợp W&B dưới dạng **lớp tracking/visualization bổ sung**.

> **Quan trọng**: Local experiment artifacts (`cmhh/results/<run_id>/`) luôn là **canonical source of truth**. W&B hoàn toàn tùy chọn (mặc định tắt) và không bao giờ làm gián đoạn experiment nếu mạng lỗi hay chưa đăng nhập.

### 1. Đăng nhập W&B (Chỉ cần làm 1 lần)
```powershell
wandb login
# hoặc set biến môi trường:
# $env:WANDB_API_KEY="your_api_key"
```

### 2. Bật W&B qua Experiment YAML Config
Trong file cấu hình experiment (ví dụ `cmhh/configs/experiments/archivist_managed.yaml`):
```yaml
tracking:
  wandb:
    enabled: true
    project: cmhh
    entity: null          # hoặc team entity
    mode: online          # online | offline | disabled
    tags: [pilot, tsp_scale]
```

### 3. Bật/Tắt và Chuyển Chế Độ trực tiếp từ CLI
Bạn có thể bật nhanh hoặc ghi đè từ dòng lệnh:

```powershell
# Chạy với W&B online
uv run cmhh --repo-root HeurAgenix run-stream --experiment HeurAgenix/cmhh/configs/experiments/archivist_managed.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_20_50_100.yaml --wandb --run-id run_wandb_online

# Chạy với W&B offline (không cần internet, lưu telemetry cục bộ)
uv run cmhh --repo-root HeurAgenix run-stream --experiment HeurAgenix/cmhh/configs/experiments/archivist_managed.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_20_50_100.yaml --wandb --wandb-mode offline --run-id run_wandb_offline

# Đồng bộ dữ liệu offline lên W&B sau khi có mạng:
wandb sync wandb/offline-run-...
```

---

## 🏗️ Architecture Overview (Bức Tranh Tổng Thể)

CMHH bao gồm 5 thành phần chính hoạt động phối hợp:

```text
  [ Task Stream: T_1 -> T_2 -> T_3 ]
                 │
  ┌──────────────┴──────────────┐
  ▼                             ▼
[ Pre-learning Probe (A) ]   [ Search & Generator (LLM) ]
(Thi thử zero-shot)             (Sinh & Tiến hóa Heuristics)
                                │
                                ▼
                       [ WorkingBuffer ] (Bộ đệm ngắn hạn)
                                │
                                ▼
                       [ Archivist Gatekeeper ] (Trọng tài bộ nhớ)
                       - Admission: Lọc ứng viên elite
                       - Protection: Bảo vệ anchor heuristic tốt nhất
                       - Eviction: Loại bỏ tri thức cũ yếu
                                │
                                ▼
                       [ Long-Term MemoryStore ] (Bộ nhớ 3-Layer)
                                ▲
                                │
                       [ Retriever Engine ] (Động cơ truy xuất)
```

---

## 🔬 Baseline / Prototype Experimental Conditions

Để đánh giá hiệu quả của hệ thống bộ nhớ CMHH trong pilot, bạn chạy so sánh các điều kiện:

1. **`isolated`**: Cold-start từng task độc lập (không chuyển giao tri thức).
2. **`population_carryover`**: Chuyển giao quần thể sinh ra từ task trước (không có bộ nhớ dài hạn).
3. **`naive_memory_sequential`**: Bộ nhớ thô FIFO/Score (không có Archivist quản lý).
4. **`naive_memory_unbounded` / `h1_naive_unbounded`**: Bộ nhớ thô không giới hạn dung lượng, dùng làm capacity/noise diagnostic.
5. **`archivist_managed`**: Managed Archivist prototype (Có WorkingBuffer & Archivist). Chỉ gọi là full CM-HH sau khi có `CandidateExtractor`, `TransferPolicy`, `PopulationBuilder`, validation-only transfer feedback, và child-memory lineage.
6. **`eoh_cold_start`**: Official EOH cold-start baseline.

---

## 🧪 Automated Testing (Chạy Kiểm Thử Tự Động)

Chạy toàn bộ 40 unit & integration tests trong hệ thống:

```powershell
uv run pytest
# Hoặc:
uv run python -m unittest discover -s HeurAgenix/tests/cmhh -p "test_*.py"
```

---

## 📊 Vị Trí Lưu Trữ Kết Quả

Sau mỗi lượt chạy, kết quả cục bộ được lưu đầy đủ tại: `HeurAgenix/cmhh/results/<run_id>/`:
1. `performance_matrix.csv`: Ma trận hiệu năng chuyển giao $R_{k,j}$.
2. `metrics.json`: Các chỉ số tổng hợp $AF$, $BWT$, $FWT$.
3. `events.jsonl`: Toàn bộ nhật ký sự kiện audit (pre-learning, candidate selection, memory transaction).
4. `memory/diagnostics.json`: Lineage bộ nhớ và lịch sử đào thải tri thức.
5. `manifest.json`: Mã băm SHA-256 của configs, mã nguồn và môi trường để tái lập kết quả.


## 📁 Thư Mục Dự Án (Project Structure)

```text
CM_HH/
├── README.md                           <-- File hướng dẫn tổng quan chính này
├── CMHH_BEGINNER_WALKTHROUGH.md        <-- Hướng dẫn chi tiết dành cho người mới
├── CMHH_EXPERIMENT_GUIDE.md            <-- Hướng dẫn chạy thí nghiệm & phân tích chỉ số
├── CMHH_ENGINEERING_HANDOFF_REVIEW.md  <-- Báo cáo nghiệm thu & kiến trúc codebase
├── HeurAgenix/
│   ├── src/cmhh/                       <-- Mã nguồn chính (archivist, retrieval, memory, runner, cli)
│   ├── tests/cmhh/                     <-- Bộ 30 unit & integration test suites
│   └── cmhh/configs/                   <-- Cấu hình experiments, streams, tasks, llm
└── IDEA/                               <-- Hồ sơ đặc tả nghiên cứu (Specifications)
```
