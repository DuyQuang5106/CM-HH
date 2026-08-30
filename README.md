# CMHH — Continual Multi-Agent Hyper-Heuristics

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-research--ready-success.svg)](#)

Official implementation of **CM-HH (Continual Multi-Agent Hyper-Heuristics)** — a research framework for persistent, non-forgetting LLM-based heuristic search and evolutionary optimization across sequential combinatorial task streams.

---

## 📚 Documentation Index (Tài Liệu Hướng Dẫn)

| File Documentation | Mục đích & Nội dung | Đối tượng |
|---|---|---|
| 🌟 [**`HeurAgenix/docs/CMHH_RUN_ALL_STREAMS_HANDOFF_GUIDE.md`**](HeurAgenix/docs/CMHH_RUN_ALL_STREAMS_HANDOFF_GUIDE.md) | **Tài liệu hướng dẫn bàn giao thực nghiệm**, chạy kiểm tra nhanh (Smoke) và chạy Benchmark toàn bộ 13 Stream | Người bàn giao & Người nhận bàn giao |
| 🚀 [**`CMHH_BEGINNER_WALKTHROUGH.md`**](CMHH_BEGINNER_WALKTHROUGH.md) | **Hướng dẫn toàn diện cho người mới**, giải thích kiến trúc 3 lớp, thiết lập môi trường và quy trình chạy 3–5 seeds | Người mới bắt đầu / Sinh viên / ML Engineer |
| 📌 [**`CMHH_STEP_BY_STEP_EXECUTION_GUIDE.md`**](CMHH_STEP_BY_STEP_EXECUTION_GUIDE.md) | **Lộ trình chạy từng bước cho 13 Stream**, yêu cầu lặp 3–5 seeds độc lập và lệnh copy-paste trực tiếp | Người trực tiếp chạy thí nghiệm |
| 📊 [**`CMHH_EXPERIMENT_GUIDE.md`**](CMHH_EXPERIMENT_GUIDE.md) | **Hướng dẫn thử nghiệm chuyên sâu & đọc chỉ số**, giải thích chi tiết $R_{k,j}$, $AF$, $BWT$, $FWT$, `diagnostics.json` và `eviction_lineage` | PhD / ML Research Engineers |
| 🛠️ [**`CMHH_ENGINEERING_HANDOFF_REVIEW.md`**](CMHH_ENGINEERING_HANDOFF_REVIEW.md) | **Báo cáo kiểm định kiến trúc & lịch sử tái cấu trúc hệ thống**, phân tích các giai đoạn hoàn thiện codebase | Core Maintainers / Code Auditors |

---

## ⚡ Cài Đặt Môi Trường (Setup trong 2 Phút)

```powershell
# Cài đặt toàn bộ dependencies (PyVRP, OR-Tools, TSPLIB95, SciPy, OpenAI...)
pip install -e .
```

*Lưu ý: File thực thi Concorde solver (`concorde.exe` và `cygwin1.dll`) cùng toàn bộ dữ liệu nghiệm chuẩn đã được đính kèm sẵn trong repo tại `HeurAgenix/tools/concorde/` và `HeurAgenix/cmhh/data/`.*

---

## 🔬 Hướng Dẫn Chạy Thực Nghiệm (Execution)

### 1. Menu Tương Tác Chọn Stream (Khuyên dùng — Dễ nhất)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_menu.ps1
```

---

### 2. Chạy Từng Stream Riêng Lẻ (Mỗi Stream 1 Script Định Sẵn)

| File Script | Tên Stream | Lệnh Test Nhanh (~2–5 phút) | Lệnh Chạy Chuẩn 3–5 Seeds (Full Benchmark) |
|---|---|---|---|
| `scripts\run_stream_1_tsp_ascending.ps1` | `tsp_size_ascending` | `.\scripts\run_stream_1_tsp_ascending.ps1` | `.\scripts\run_stream_1_tsp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_2_tsp_descending.ps1` | `tsp_size_descending` | `.\scripts\run_stream_2_tsp_descending.ps1` | `.\scripts\run_stream_2_tsp_descending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_3_cvrp_ascending.ps1` | `cvrp_size_ascending` | `.\scripts\run_stream_3_cvrp_ascending.ps1` | `.\scripts\run_stream_3_cvrp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_4_jssp_ascending.ps1` | `jssp_size_ascending` | `.\scripts\run_stream_4_jssp_ascending.ps1` | `.\scripts\run_stream_4_jssp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_5_cross_domain.ps1` | `cross_problem_tsp_cvrp_jssp` | `.\scripts\run_stream_5_cross_domain.ps1` | `.\scripts\run_stream_5_cross_domain.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_6_tsp_stationary.ps1` | `tsp_stationary` | `.\scripts\run_stream_6_tsp_stationary.ps1` | `.\scripts\run_stream_6_tsp_stationary.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_7_tsp_revisit.ps1` | `tsp_revisit` | `.\scripts\run_stream_7_tsp_revisit.ps1` | `.\scripts\run_stream_7_tsp_revisit.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_8_cvrp_descending.ps1` | `cvrp_size_descending` | `.\scripts\run_stream_8_cvrp_descending.ps1` | `.\scripts\run_stream_8_cvrp_descending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_9_jssp_descending.ps1` | `jssp_size_descending` | `.\scripts\run_stream_9_jssp_descending.ps1` | `.\scripts\run_stream_9_jssp_descending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |

---

### 3. Chạy Tự Động Toàn Bộ 13 Stream (Multi-Seed Benchmark)

```powershell
# Chạy kiểm tra nhanh toàn bộ 13 stream trước khi bàn giao:
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -QuickSmoke

# Chạy Benchmark chính thức lặp 3 seeds (Seeds 1, 2, 3):
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3 -LlmConfig cmhh/configs/llm/llm_config.local.json

# Chạy Benchmark chính thức lặp đầy đủ 5 seeds (Seeds 1, 2, 3, 4, 5):
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3,4,5 -LlmConfig cmhh/configs/llm/llm_config.local.json

# Phục hồi nếu bị gián đoạn mạng (-Resume):
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3,4,5 -Resume
```

---

### 4. Giám Sát Thời Gian Thực (Watcher)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\watch_phase1_tsp_run.ps1
```

---

## 📊 Cấu Trúc Kết Quả

Sau mỗi lượt chạy, kết quả được lưu tại `HeurAgenix/cmhh/results/<run_id>/`:
1. `performance_matrix.csv`: Ma trận hiệu năng chuyển giao $R_{k,j}$ (Relative Gap).
2. `metrics.json`: Các chỉ số tổng hợp $AF$ (Average Final Performance), $BWT$ (Backward Transfer), $FWT$ (Forward Transfer).
3. `events.jsonl`: Toàn bộ nhật ký sự kiện audit khoa học (pre-learning probe, candidate selection, memory transaction).
4. `memory/diagnostics.json`: Lineage bộ nhớ và lịch sử đào thải tri thức.
5. `manifest.json`: Mã băm SHA-256 của configs, mã nguồn và môi trường để tái lập kết quả.
