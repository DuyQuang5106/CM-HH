# CM-HH: Hướng Dẫn Thực Thi Từng Bước (Step-by-Step Execution Guide)

**Dự án:** Continual Multi-Agent Hyper-Heuristics (CM-HH)  
**Quy trình chuẩn:** Chạy thực nghiệm trên mọi nền tảng (Windows, macOS, Linux, Server, SLURM Cluster) thông qua `uv run cmhh`.

---

## 0. Quy Trình Tổng Quan 6 Bước

```text
1. Clone repo & Cài đặt môi trường
   -> cd HeurAgenix
   -> uv sync

2. Cấu hình LLM
   -> cmhh/configs/llm/llm_config.local.json

3. Smoke Test (0 token - kiểm tra solver & pipeline)
   -> uv run cmhh run-suite --suite pilot_small_smoke --generator baseline --skip-references --no-wandb

4. Chuẩn bị dữ liệu & Reference Solvers
   -> uv run cmhh run-suite --streams <stream_id> --seeds 1 --mode full --prepare-only --no-wandb

5. Chạy thực nghiệm (Đơn lẻ hoặc Song song 4 tab)
   -> uv run cmhh run-suite --streams <stream_id> --conditions <conditions> --seeds <seeds> --mode full --wandb --resume

6. Đọc kết quả & Kiểm tra
   -> cmhh/results/<run_id>/ (metrics.json, performance_matrix.csv, transfer_diagnostics.csv)
```

---

## 1. Cài Đặt Môi Trường Từ Đầu

Mở terminal và thực hiện:

```powershell
# 1. Clone repository
git clone https://github.com/DuyQuang5106/CM-HH.git
cd CM-HH/HeurAgenix

# 2. Đồng bộ môi trường bằng uv
uv sync

# 3. Kiểm tra CLI
uv run cmhh --help
uv run cmhh run-suite --help
```

---

## 2. Cấu Hình LLM API

Tạo hoặc chỉnh sửa file `cmhh/configs/llm/llm_config.local.json`:

```json
{
  "type": "api_model",
  "name": "nvidia-nemotron-3-super-120b",
  "url": "https://integrate.api.nvidia.com/v1/chat/completions",
  "api_key": "YOUR_NVIDIA_OR_OPENAI_API_KEY",
  "model": "nvidia/nemotron-3-super-120b-a12b",
  "temperature": 0.8,
  "top-p": 0.95,
  "max_tokens": 4096,
  "max_attempts": 5,
  "sleep_time": 5,
  "timeout": 180,
  "seed": 42,
  "stream": false
}
```

---

## 3. Reference Solvers & Tự Động Tạo Cache

Hệ thống tích hợp sẵn các bộ giải nghiệm tối ưu/SOTA chuẩn mực:
* **Concorde Exact Solver**: Cho bài toán TSP.
* **PyVRP (Hybrid Genetic Search)**: Cho các biến thể CVRP, OVRP, VRPTW, OVRPTW.
* **OR-Tools CP-SAT**: Cho bài toán lập lịch JSSP.

Trước khi chạy tiến hóa, bạn có thể tính trước toàn bộ nghiệm tham chiếu bằng lệnh `--prepare-only`:

```powershell
uv run cmhh run-suite --streams s3_related_cross_problem --seeds 1 --mode full --prepare-only --no-wandb
```

---

## 4. Danh Mục Các Stream Chuẩn Đang Hoạt Động

### A. Nhóm 4 Pilot Streams (`cmhh/configs/streams/pilot/`)

| Stream ID | Ý Nghĩa Chuyển Giao | Chuỗi Bài Toán |
| :--- | :--- | :--- |
| `s1_tsp_scale` | **Scale Shift** ($N=20 \to 50 \to 100 \to 20\text{-anchor}$) | `tsp_uniform_n20_a` $\to$ `tsp_uniform_n50_a` $\to$ `tsp_uniform_n100_a` $\to$ `tsp_uniform_n20_b` |
| `s2_cvrp_constraint` | **Constraint Shift** (Closed $\to$ Open $\to$ Time-Windows) | `cvrp_uniform_n50_medium` $\to$ `ovrp_uniform_n50_medium` $\to$ `vrptw_uniform_n50_medium` $\to$ `cvrp_uniform_n50_medium_anchor` |
| `s3_related_cross_problem` | **Related Cross-Domain** (TSP $\to$ CVRP $\to$ TSP) | `tsp_uniform_n50_a` $\to$ `cvrp_uniform_n50_medium` $\to$ `tsp_uniform_n50_b` |
| `s4_unrelated_cross_problem` | **Unrelated Domain** (TSP $\to$ JSSP $\to$ TSP) | `tsp_uniform_n50_a` $\to$ `jssp_10x5_easy` $\to$ `tsp_uniform_n50_b` |
| `s5_vrp_variant` | **VRP Constraint Variant Shift** | `cvrp_uniform_n50_medium` $\to$ `ovrp_uniform_n50_medium` $\to$ `ovrptw_uniform_n50_medium` $\to$ `vrptw_uniform_n50_medium` |

### B. Nhóm VRP Constraint Graycode Streams (`cmhh/configs/streams/`)

| Stream ID | Chuỗi Chuyển Giao Biến Đổi Ràng Buộc 1-Bit |
| :--- | :--- |
| `vrp_constraint_graycode` | $\text{CVRP} \longrightarrow \text{OVRP} \longrightarrow \text{VRPTW} \longrightarrow \text{OVRPTW}$ |
| `vrp_constraint_graycode_reverse` | $\text{OVRPTW} \longrightarrow \text{VRPTW} \longrightarrow \text{OVRP} \longrightarrow \text{CVRP}$ |

---

## 5. Hướng Dẫn Chạy Thực Nghiệm

### Cách 1: Chạy Đầy Đủ 1 Lệnh (Tuần tự các điều kiện)
```powershell
uv run cmhh run-suite --streams s3_related_cross_problem --seeds 1 --mode full --run-prefix s3_full --wandb --resume
```

### Cách 2: Chạy Song Song 4 Tab Cho 4 Điều Kiện (Khuyên dùng khi cắm máy qua đêm)
Mở 4 tab PowerShell tại thư mục `HeurAgenix`:

* **Tab 1 (`isolated` + `population`)**:
  ```powershell
  cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
  uv run cmhh run-suite --streams s3_related_cross_problem --conditions isolated,population --seeds 1 --mode full --run-prefix s3_full --wandb --resume
  ```
* **Tab 2 (`naive-bounded`)**:
  ```powershell
  cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
  uv run cmhh run-suite --streams s3_related_cross_problem --conditions naive-bounded --seeds 1 --mode full --run-prefix s3_full --wandb --resume
  ```
* **Tab 3 (`naive-unbounded`)**:
  ```powershell
  cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
  uv run cmhh run-suite --streams s3_related_cross_problem --conditions naive-unbounded --seeds 1 --mode full --run-prefix s3_full --wandb --resume
  ```
* **Tab 4 (`managed`)**:
  ```powershell
  cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
  uv run cmhh run-suite --streams s3_related_cross_problem --conditions managed --seeds 1 --mode full --run-prefix s3_full --wandb --resume
  ```

---

## 6. Cơ Chế Resume Khi Bị Gián Đoạn

Nếu tiến trình bị dừng hoặc máy tính khởi động lại, bạn chỉ cần chạy lại câu lệnh ban đầu với cờ `--resume`:
* Hệ thống sẽ tự động đọc `checkpoints/latest.json` trong thư mục kết quả.
* Bỏ qua toàn bộ các task đã tính xong trước đó.
* Tiếp tục tiến hóa từ thế hệ gần nhất với **3-Layer Runtime Guard** (bảo vệ không bao giờ bị kẹt CPU).
