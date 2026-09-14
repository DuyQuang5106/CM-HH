# CM-HH: Hướng Dẫn Toàn Diện Cho Người Mới Bắt Đầu

**Dự án:** Continual Multi-Agent Hyper-Heuristics (CM-HH)  
**Tài liệu:** Hướng dẫn từ thiết lập môi trường, chuẩn bị dữ liệu, chạy thực nghiệm đến phân tích kết quả.

---

## 1. Tổng Quan Về Kiến Trúc CM-HH

CM-HH là framework học liên tục (Continual Learning) dành cho Hyper-Heuristics dựa trên mô hình ngôn ngữ lớn (LLM). Hệ thống điều phối các agent sinh và tiến hóa thuật toán heuristic qua một **chuỗi bài toán tối ưu tổ hợp (Task Stream)**:

$$\mathcal{T}_1 \longrightarrow \mathcal{T}_2 \longrightarrow \mathcal{T}_3 \longrightarrow \dots \longrightarrow \mathcal{T}_K$$

### Vòng Lặp Học Liên Tục Chuẩn (Continual Loop)

```text
               +-------------------------------------------------------------+
               |                        Task Hiện Tại                        |
               +-------------------------------------------------------------+
                                              |
                                              v
               +-------------------------------------------------------------+
               | 1. Retrieval Engine: Truy xuất tri thức phù hợp từ Memory   |
               +-------------------------------------------------------------+
                                              |
                                              v
               +-------------------------------------------------------------+
               | 2. Transfer Policy: Lập kế hoạch (DIRECT_REUSE / REFINE)    |
               +-------------------------------------------------------------+
                                              |
                                              v
               +-------------------------------------------------------------+
               | 3. Population Builder: Khởi tạo P0 (Tri thức cũ + Mới)      |
               +-------------------------------------------------------------+
                                              |
                                              v
               +-------------------------------------------------------------+
               | 4. Heuristic Evolver: Tiến hóa thuật toán (3-Layer Guard)  |
               +-------------------------------------------------------------+
                                              |
                                              v
               +-------------------------------------------------------------+
               | 5. Candidate Extractor: Trích xuất thuật toán xuất sắc      |
               +-------------------------------------------------------------+
                                              |
                                              v
               +-------------------------------------------------------------+
               | 6. Archivist Gatekeeper: Kiểm duyệt & Nạp vào MemoryStore   |
               +-------------------------------------------------------------+
```

---

## 2. Hướng Dẫn Cài Đặt Từ Đầu (Từ Clone Repo)

### Bước 2.1: Clone Repository
```powershell
git clone https://github.com/DuyQuang5106/CM-HH.git
cd CM-HH/HeurAgenix
```

### Bước 2.2: Thiết Lập Môi Trường Bằng `uv`
Dự án sử dụng `uv` để quản lý gói nhanh chóng và đồng bộ tuyệt đối trên Windows, Linux, macOS:

```powershell
# Cài đặt toàn bộ dependencies theo uv.lock
uv sync
```

Kiểm tra CLI hoạt động:
```powershell
uv run cmhh --help
uv run cmhh run-suite --help
uv run cmhh run-stream --help
```

### Bước 2.3: Cấu Hình LLM
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

## 3. Hệ Thống Reference Solvers (Nghiệm Tham Chiếu Chuẩn)

Để đánh giá chất lượng của heuristic sinh ra bằng thước đo **Relative Gap** khách quan, CM-HH tích hợp sẵn các bộ giải nghiệm tối ưu/SOTA chuyên biệt:

| Miền Bài Toán | Reference Solver | Cơ Chế Giải | Mục Đích |
| :--- | :--- | :--- | :--- |
| **TSP** | **Concorde** | Exact Branch-and-Cut | Tìm tour có tổng khoảng cách tối ưu tuyệt đối. |
| **CVRP / OVRP / VRPTW / OVRPTW** | **PyVRP** | Hybrid Genetic Search (SOTA) | Giải bài toán định tuyến xe đa ràng buộc (sức chứa, đường mở, cửa sổ thời gian). |
| **JSSP** | **OR-Tools CP-SAT** | Constraint Programming SAT | Tìm lịch trình phân phối công việc tối ưu makespan ($C_{\max}$). |

> **Lưu ý:** Toàn bộ kết quả giải của Reference Solvers sẽ được tự động tính toán và lưu cache tại `cmhh/data/references/` khi chạy lệnh chuẩn bị (`--prepare-only`) hoặc khi bắt đầu stream.

---

## 4. Danh Mục Các Stream Hiện Tại (Active Streams)

Dự án hiện tập trung vào 2 nhóm Stream chuẩn khoa học:

### A. Nhóm 4 Pilot Streams (`cmhh/configs/streams/pilot/`)

| Stream ID | Giả Thuyết Đánh Giá (Hypothesis) | Chuỗi Chuyển Giao (Task Sequence) |
| :--- | :--- | :--- |
| `s1_tsp_scale` | **Scale Shift** (Thay đổi quy mô $N$) | $\text{TSP}_{n20\text{-A}} \to \text{TSP}_{n50\text{-A}} \to \text{TSP}_{n100\text{-A}} \to \text{TSP}_{n20\text{-B}}$ |
| `s2_cvrp_constraint` | **Constraint Shift** (Thay đổi ràng buộc VRP) | $\text{CVRP}_{n50} \to \text{OVRP}_{n50} \to \text{VRPTW}_{n50} \to \text{CVRP}_{n50\text{-Anchor}}$ |
| `s3_related_cross_problem` | **Related Cross-Domain** (Chuyển giao liên miền gần) | $\text{TSP}_{n50\text{-A}} \to \text{CVRP}_{n50\text{-Medium}} \to \text{TSP}_{n50\text{-B}}$ |
| `s4_unrelated_cross_problem` | **Unrelated Domain** (Kiểm tra Negative Transfer) | $\text{TSP}_{n50\text{-A}} \to \text{JSSP}_{10\times5} \to \text{TSP}_{n50\text{-B}}$ |
| `s5_vrp_variant` | **VRP Constraint Variant Shift** (Chuyển giao biến thể VRP) | $\text{CVRP}_{n50} \to \text{OVRP}_{n50} \to \text{OVRPTW}_{n50} \to \text{VRPTW}_{n50}$ |

### B. Nhóm VRP Constraint Graycode Streams (`cmhh/configs/streams/`)

| Stream ID | Mục Đích | Chuỗi Chuyển Giao (1-Bit Constraint Transitions) |
| :--- | :--- | :--- |
| `vrp_constraint_graycode` | Chuỗi bổ sung/gỡ ràng buộc tuần tự | $\text{CVRP} \longrightarrow \text{OVRP} \longrightarrow \text{VRPTW} \longrightarrow \text{OVRPTW}$ |
| `vrp_constraint_graycode_reverse` | Chuỗi đảo ngược kiểm tra đối xứng | $\text{OVRPTW} \longrightarrow \text{VRPTW} \longrightarrow \text{OVRP} \longrightarrow \text{CVRP}$ |

---

## 5. 5 Chế Độ Học Liên Tục (Experimental Conditions)

| Condition | Tên Khoa Học | Cơ Chế Hoạt Động |
| :--- | :--- | :--- |
| `isolated` | **Cold Start Baseline** | Không chuyển giao; mỗi task trong stream được tiến hóa độc lập từ đầu để làm mốc so sánh ($Score_{\text{cold}}$). |
| `population` | **Population Carryover** | Quần thể nghiệm cuối cùng của task trước được nạp làm hạt giống khởi tạo ($P_0$) cho task sau. |
| `naive-bounded` | **Naive Bounded Memory** | Bộ nhớ ngoài lưu trữ heuristic không kiểm duyệt với giới hạn dung lượng ($K=20$, cơ chế FIFO). |
| `naive-unbounded` | **Naive Unbounded Memory** | Bộ nhớ ngoài lưu trữ không giới hạn (kiểm tra hiện tượng tích tụ nhiễu khi tri thức quá nhiều). |
| `managed` | **Full CM-HH (Archivist)** | Hệ thống quản lý bộ nhớ toàn diện: Đánh giá chất lượng $\to$ Phân loại $\to$ Truy xuất thông minh $\to$ Kế hoạch chuyển giao. |

---

## 6. Hướng Dẫn Thực Thi Từng Bước

### Bước 6.1: Chạy Smoke Test (0 Token LLM - Kiểm tra hệ thống)
Chạy kiểm tra toàn bộ pipeline, bộ đọc dữ liệu và solver trong vài giây mà không tốn token:

```powershell
cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
uv run cmhh run-suite --suite pilot_small_smoke --generator baseline --skip-references --no-wandb
```

### Bước 6.2: Chuẩn Bị Dữ Liệu & Tính Reference Cache
```powershell
uv run cmhh run-suite --streams s3_related_cross_problem --seeds 1 --mode full --prepare-only --no-wandb
```

### Bước 6.3: Chạy Stream Đơn Lẻ (Ví dụ S3 Seed 1)
```powershell
uv run cmhh run-suite --streams s3_related_cross_problem --seeds 1 --mode full --run-prefix s3_full --wandb --resume
```

### Bước 6.4: Chạy Song Song 4 Tab PowerShell Cho 4 Điều Kiện (Cắm Máy Qua Đêm)
Mở 4 tab PowerShell riêng biệt tại thư mục `HeurAgenix`:

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

## 7. Cơ Chế Bảo Vệ 3-Layer Runtime Guard

Để loại bỏ hoàn toàn nguy cơ sinh code có độ phức tạp $O(N^4)$ hoặc lặp vô tận gây treo máy:

1. **Layer 1 (Prompt Constraint)**: Tự động nhúng ràng buộc độ phức tạp tối đa $O(N \log N)$ hoặc $O(N^2)$ vào prompt sinh và tinh chỉnh heuristic.
2. **Layer 2 (Smoke Guard)**: Subprocess độc lập kiểm tra heuristic trên 1 instance nhỏ với **Hard Timeout 1.0s**. Nếu vi phạm sẽ loại bỏ candidate ngay lập tức.
3. **Layer 3 (Validation Guard)**: Kiểm soát với cơ chế **Two-tier Timeout** (15s mỗi case, 60s tổng mỗi candidate) và chính sách **Fail-fast**. Nếu candidate có bất kỳ case nào bị lỗi/timeout, candidate đó sẽ bị đánh dấu `INVALID` và loại bỏ, ngăn chặn hiện tượng sai lệch độ thích nghi (Survivorship Bias).

---

## 8. Đọc Và Phân Tích Kết Quả

Kết quả sau khi chạy được lưu tại `cmhh/results/<run_id>/`:

* `performance_matrix.csv`: Ma trận hiệu năng Relative Gap qua các task:
  $$\text{Relative Gap} = \frac{\text{Objective} - \text{Reference}}{\text{Reference}}$$
* `metrics.json`: Các chỉ số chuyển giao cốt lõi:
  - **Average Final Performance (AF)**: Hiệu năng trung bình trên toàn stream.
  - **Backward Transfer (BWT)**: Đo lường mức độ chống quên tri thức cũ.
  - **Forward Transfer (FWT)**: Đo lường mức độ thích ứng nhanh với task mới.
* `transfer_diagnostics.csv`: Phân tích chi tiết từng bước chuyển giao giữa các cặp bài toán.
* `events.jsonl`: Toàn bộ nhật ký sự kiện khoa học trong suốt quá trình chạy.
* `llm_calls.jsonl`: Thông tin chi tiết về số token, độ trễ và trạng thái của từng request LLM.
