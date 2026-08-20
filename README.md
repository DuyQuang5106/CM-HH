# CMHH — Continual Multi-Agent Hyper-Heuristics

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-research--ready-success.svg)](#)

Official implementation of **CMHH (Continual Multi-Agent Hyper-Heuristics)** — a research framework for persistent, non-forgetting LLM-based heuristic search and evolutionary optimization across sequential combinatorial task streams.

---

## 📚 Documentation Index (Tài Liệu Hướng Dẫn)

| File Documentation | Mục đích & Nội dung | Đối tượng |
|---|---|---|
| 🚀 [**`CMHH_BEGINNER_WALKTHROUGH.md`**](CMHH_BEGINNER_WALKTHROUGH.md) | **Hướng dẫn từng bước cho người mới (Quickstart 5 phút)**, giải thích sơ đồ 5 phần, chạy lệnh đầu tiên và cách đọc ma trận kết quả | Người mới bắt đầu / Sinh viên / ML Engineer |
| 📌 [**`CMHH_STEP_BY_STEP_EXECUTION_GUIDE.md`**](CMHH_STEP_BY_STEP_EXECUTION_GUIDE.md) | **Lộ trình chạy từng bước có đánh số (từ 1 đến 8)** kèm các câu lệnh PowerShell copy-paste trực tiếp | Người trực tiếp chạy thí nghiệm |
| 📊 [**`CMHH_EXPERIMENT_GUIDE.md`**](CMHH_EXPERIMENT_GUIDE.md) | **Hướng dẫn thử nghiệm chuyên sâu & đọc chỉ số**, giải thích chi tiết $R_{k,j}$, $AF$, $BWT$, $FWT$, `diagnostics.json` và `eviction_lineage` | PhD / ML Research Engineers |
| 🛠️ [**`CMHH_ENGINEERING_HANDOFF_REVIEW.md`**](CMHH_ENGINEERING_HANDOFF_REVIEW.md) | **Báo cáo kiểm định kiến trúc & lịch sử tái cấu trúc hệ thống**, phân tích 5 giai đoạn hoàn thiện codebase | Core Maintainers / Code Auditors |
| 📄 [**`IDEA/Idea/CMHH_Research_Specification.md`**](IDEA/Idea/CMHH_Research_Specification.md) | **Tài liệu đặc tả bài báo nghiên cứu (Research Specs)** | Scientific Research Team |

---

## ⚡ Quickstart (Khởi Động Nhanh Trong 5 Phút)

### 1. Đặt biến môi trường `PYTHONPATH`
```powershell
$env:PYTHONPATH="HeurAgenix/src"
```

### 2. Kiểm tra tính hợp lệ của hệ thống (Sanity Check)
```powershell
python -m cmhh.cli --repo-root HeurAgenix validate-config
```

### 3. Sinh dữ liệu benchmark & nghiệm tối ưu chuẩn
```powershell
# Sinh dữ liệu bài toán TSPLIB
python -m cmhh.cli --repo-root HeurAgenix generate-data --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --seed 42

# Sinh nghiệm tối ưu tuyệt đối bằng Concorde exact solver
python -m cmhh.cli --repo-root HeurAgenix generate-references --solver-config HeurAgenix/cmhh/configs/solvers/concorde.yaml --split validation --split test
```

### 4. Chạy luồng học liên tục (Continual Stream Run)
```powershell
python -m cmhh.cli --repo-root HeurAgenix run-stream --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --generator heuragenix --llm-config HeurAgenix/cmhh/configs/llm/openai.json --seed 42 --run-id my_cmhh_run
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

## 🔬 4 Điều Kiện Thử Nghiệm Baseline (Experimental Conditions)

Để đánh giá hiệu quả của hệ thống bộ nhớ CMHH trong bài báo, bạn chạy so sánh **4 điều kiện**:

1. **`isolated`**: Cold-start từng task độc lập (không chuyển giao tri thức).
2. **`population_carryover`**: Chuyển giao quần thể sinh ra từ task trước (không có bộ nhớ dài hạn).
3. **`naive_memory_sequential`**: Bộ nhớ thô FIFO/Score (không có Archivist quản lý).
4. **`archivist_managed`**: Hệ thống CMHH hoàn chỉnh (Có WorkingBuffer & Archivist).

---

## 🧪 Automated Testing (Chạy Kiểm Thử Tự Động)

Chạy toàn bộ 30 unit & integration tests trong hệ thống:

```powershell
$env:PYTHONPATH="HeurAgenix/src"; python -m unittest discover -s HeurAgenix/tests/cmhh -p "test_*.py"
```

---

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
