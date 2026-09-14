# CM-HH: Hướng Dẫn Thực Nghiệm & Đánh Giá Học Liên Tục

**Dự án:** Continual Multi-Agent Hyper-Heuristics (CM-HH)  
**Tài liệu:** Giao thức thực nghiệm chuẩn, cấu hình luồng dữ liệu, đánh giá độ chuyển giao và phân tích kết quả.

---

## 1. Giao Thức Đánh Giá Học Liên Tục (Continual Protocol)

CM-HH đánh giá khả năng tích lũy, chuyển giao và bảo toàn tri thức của agent qua một chuỗi các bài toán tối ưu tổ hợp rời rạc:

$$\mathcal{T}_1 \longrightarrow \mathcal{T}_2 \longrightarrow \mathcal{T}_3 \longrightarrow \dots \longrightarrow \mathcal{T}_K$$

Mỗi stream được chạy qua $3 - 5$ seed ngẫu nhiên độc lập. Kết quả trên các bảng báo cáo khoa học thể hiện dạng $\text{Mean} \pm \text{Std}$ cho 3 chỉ số cốt lõi:

* **Average Final Performance ($AF$)**: Chất lượng giải trung bình trên toàn bộ các task sau khi kết thúc stream.
* **Backward Transfer ($BWT$)**: Đánh giá khả năng chống quên thảm họa (Catastrophic Forgetting) đối với các task trước đó.
* **Forward Transfer ($FWT$)**: Đánh giá khả năng thích ứng nhanh (Zero-shot / Few-shot) trên task mới nhờ tri thức chuyển giao.

---

## 2. Kiến Trúc Cấu Hình 4 Lớp (Configuration Hierarchy)

CM-HH sử dụng cơ chế cấu hình 4 lớp không trùng lặp (DRY):

```text
Lớp 1: cmhh/configs/experiments/defaults.yaml (Tham số chung: search budget, splits, tracking)
   +
Lớp 2: cmhh/configs/conditions.yaml           (Chính sách bộ nhớ: isolated, population, managed)
   +
Lớp 3: cmhh/configs/suites/*.yaml             (Danh sách streams, điều kiện, seeds)
   +
Lớp 4: CLI Flags & Runtime Overrides          (--mode, --seeds, --conditions, --resume)
   =
Cấu Hình Cuối Cùng Được Giải Mã (Resolved Configuration)
```

### Bảng 5 Điều Kiện So Sánh (Continual Conditions)

| Điều Kiện (Condition) | Ý Nghĩa Thực Nghiệm | Chính Sách Bộ Nhớ | Dung Lượng ($K$) |
| :--- | :--- | :--- | :--- |
| `isolated` | Cold-start độc lập từng bài toán | `none` | $0$ |
| `population` | Kế thừa quần thể nghiệm cuối cùng | `population_carryover` | $20$ |
| `naive-bounded` | Bộ nhớ ngoài FIFO có giới hạn | `naive_overwrite` | $20$ |
| `naive-unbounded` | Bộ nhớ ngoài không giới hạn | `naive_overwrite` | Không giới hạn |
| `managed` | Framework CM-HH đầy đủ (Archivist) | `archivist_managed` | $20$ |

---

## 3. Danh Mục Các Stream Thực Nghiệm Hoạt Động (Active Streams)

### A. Nhóm 4 Pilot Streams (`cmhh/configs/streams/pilot/`)
Nhóm stream đánh giá các giả thuyết chuyển giao nền tảng:

| Stream ID | Mục Đích Đánh Giá | Chuỗi Bài Toán |
| :--- | :--- | :--- |
| `s1_tsp_scale` | **Quy mô $N$** ($20 \to 50 \to 100 \to 20\text{-anchor}$) | `tsp_uniform_n20_a` $\to$ `tsp_uniform_n50_a` $\to$ `tsp_uniform_n100_a` $\to$ `tsp_uniform_n20_b` |
| `s2_cvrp_constraint` | **Ràng buộc VRP** (Closed $\to$ Open $\to$ Time-Windows) | `cvrp_uniform_n50_medium` $\to$ `ovrp_uniform_n50_medium` $\to$ `vrptw_uniform_n50_medium` $\to$ `cvrp_uniform_n50_medium_anchor` |
| `s3_related_cross_problem` | **Chuyển giao liên miền gần** (TSP $\to$ CVRP $\to$ TSP) | `tsp_uniform_n50_a` $\to$ `cvrp_uniform_n50_medium` $\to$ `tsp_uniform_n50_b` |
| `s4_unrelated_cross_problem` | **Chuyển giao liên miền xa** (TSP $\to$ JSSP $\to$ TSP) | `tsp_uniform_n50_a` $\to$ `jssp_10x5_easy` $\to$ `tsp_uniform_n50_b` |
| `s5_vrp_variant` | **Chuyển giao biến thể VRP** (CVRP $\to$ OVRP $\to$ OVRPTW $\to$ VRPTW) | `cvrp_uniform_n50_medium` $\to$ `ovrp_uniform_n50_medium` $\to$ `ovrptw_uniform_n50_medium` $\to$ `vrptw_uniform_n50_medium` |

### B. Nhóm VRP Constraint Graycode Streams (`cmhh/configs/streams/`)
Nhóm stream chuyển giao biến đổi ràng buộc 1-bit Graycode:

| Stream ID | Chuỗi Chuyển Giao |
| :--- | :--- |
| `vrp_constraint_graycode` | $\text{CVRP} \longrightarrow \text{OVRP} \longrightarrow \text{VRPTW} \longrightarrow \text{OVRPTW}$ |
| `vrp_constraint_graycode_reverse` | $\text{OVRPTW} \longrightarrow \text{VRPTW} \longrightarrow \text{OVRP} \longrightarrow \text{CVRP}$ |

---

## 4. Hệ Thống Reference Solvers Chuẩn Khoa Học

Để tính toán điểm số **Relative Gap**:

$$\text{Score} = -\text{Relative Gap} = -\frac{\text{Objective}_{\text{heuristic}} - \text{Objective}_{\text{reference}}}{\text{Objective}_{\text{reference}}}$$

Hệ thống sử dụng 3 bộ giải chính xác và SOTA:
1. **TSP**: **Concorde Exact Solver** (Exact branch-and-cut).
2. **VRP Family (CVRP, OVRP, VRPTW, OVRPTW)**: **PyVRP** (SOTA Hybrid Genetic Search).
3. **JSSP**: **OR-Tools CP-SAT** (Constraint Programming).

Tất cả nghiệm tham chiếu được tự động tính và lưu trữ tại `cmhh/data/references/` để tái sử dụng tức thì giữa các thí nghiệm.

---

## 5. Các Lệnh Thực Nghiệm Chuẩn

### 5.1. Khởi Tạo & Kiểm Tra Nhanh
```powershell
# Chạy trong thư mục HeurAgenix
cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix

# 1. Cài đặt môi trường
uv sync

# 2. Smoke test 0 token
uv run cmhh run-suite --suite pilot_small_smoke --generator baseline --skip-references --no-wandb

# 3. Chuẩn bị dữ liệu và tính trước reference
uv run cmhh run-suite --streams s3_related_cross_problem --seeds 1 --mode full --prepare-only --no-wandb
```

### 5.2. Chạy Thí Nghiệm Đầy Đủ
```powershell
# Chạy 1 stream đầy đủ cho 1 seed:
uv run cmhh run-suite --streams s3_related_cross_problem --seeds 1 --mode full --run-prefix s3_full --wandb --resume

# Chạy song song 4 tab cho 4 điều kiện của 1 seed (Cách chạy nhanh nhất qua đêm):
# Tab 1: uv run cmhh run-suite --streams s3_related_cross_problem --conditions isolated,population --seeds 1 --mode full --run-prefix s3_full --wandb --resume
# Tab 2: uv run cmhh run-suite --streams s3_related_cross_problem --conditions naive-bounded --seeds 1 --mode full --run-prefix s3_full --wandb --resume
# Tab 3: uv run cmhh run-suite --streams s3_related_cross_problem --conditions naive-unbounded --seeds 1 --mode full --run-prefix s3_full --wandb --resume
# Tab 4: uv run cmhh run-suite --streams s3_related_cross_problem --conditions managed --seeds 1 --mode full --run-prefix s3_full --wandb --resume
```

---

## 6. Cấu Trúc Kết Quả Đầu Ra

Tất cả dữ liệu chạy được lưu trữ độc lập tại `cmhh/results/<run_id>/`:

```text
cmhh/results/<run_id>/
├── resolved_config.yaml         # Snapshot cấu hình thực tế
├── manifest.json                # SHA-256 hash của code, cấu hình và môi trường
├── performance_matrix.csv       # Ma trận Relative Gap giữa các cặp task
├── metrics.json                 # Chỉ số AF, BWT, FWT
├── pre_learning_scores.json     # Điểm probe trước khi học task mới
├── transfer_diagnostics.csv     # Phân tích chi tiết chuyển giao từng bước
├── events.jsonl                 # Toàn bộ nhật ký sự kiện khoa học
├── llm_calls.jsonl              # Telemetry cuộc gọi LLM (tokens, latency, status)
├── memory/                      # Dữ liệu lưu trữ tri thức và chẩn đoán bộ nhớ
└── termination_metadata.json    # Báo cáo tổng kết vòng đời và lý do kết thúc
```
