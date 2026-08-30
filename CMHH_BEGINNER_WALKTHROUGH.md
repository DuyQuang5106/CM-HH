# CMHH — Hướng Dẫn Walkthrough & Thiết Lập Thực Nghiệm Toàn Diện (Beginner & Research Protocol Guide)

**Dự án:** Continual Multi-Agent Hyper-Heuristics (CM-HH)  
**Mục tiêu file này:** Giúp người mới bắt đầu (sinh viên, nghiên cứu sinh, ML engineer) nhanh chóng hiểu bức tranh tổng thể, tự thiết lập môi trường, chạy thử nghiệm kiểm tra nhanh (Smoke Test) và thực thi benchmark khoa học chính thức (**Chạy lặp 3–5 seeds độc lập cho mỗi stream**) để thu thập số liệu cho bài báo.

---

## 1. Giới thiệu Dễ hiểu về CM-HH (Conceptual Overview)

### CM-HH là gì?
Khi huấn luyện AI Agent (LLM) tự động sinh và tiến hóa thuật toán (Heuristics) qua một chuỗi các bài toán tối ưu tổ hợp kế tiếp nhau:
$$
T_1 \rightarrow T_2 \rightarrow T_3 \rightarrow \dots \rightarrow T_K
$$

- Khi giải bài toán nhỏ ($T_1$: TSP 20 thành phố), AI tìm ra nhiều heuristics tốt.
- Khi chuyển sang bài toán lớn hơn ($T_2$: TSP 50 thành phố), ta muốn AI **tận dụng tri thức cũ** (Forward Transfer) thay vì học lại từ đầu, nhưng đồng thời **không được quên** cách giải bài toán cũ ($T_1$ — Backward Transfer / Anti-Forgetting).

**CM-HH** chính là hệ thống quản lý bộ nhớ dài hạn 3 lớp ($h_i, k_i, z_i, \mu_i$) kết hợp cơ chế tuyển chọn (Archivist Gatekeeper), chính sách chuyển giao (Transfer Policy) và truy xuất thông minh (Retriever Engine) để hiện thực hóa việc học liên tục (Continual Learning).

---

### Sơ đồ Luồng Chuyển Giao Tri Thức CM-HH

```text
Task hoàn thành (T_{k-1})
    -> CandidateExtractor: Tuyển chọn các heuristic xuất sắc nhất từ quần thể cuối
    -> Archivist Gatekeeper: Quyết định nạp bộ nhớ dài hạn (Admission) & bảo vệ mỏ neo (Anchor Protection)
    -> MemoryStore: Lưu trữ tri thức dài hạn 3 lớp
    -> Retriever Engine: Truy xuất các heuristic tương đồng cho task mới (T_k)
    -> TransferPolicy: Quyết định DIRECT_REUSE / REFINE / IGNORE
    -> PopulationBuilder: Khởi tạo quần thể P0 kết hợp giữa tri thức cũ và mầm mới
    -> Tiến hóa (Evolution): Tìm kiếm heuristic tối ưu trên task hiện tại
    -> Transfer Feedback: Cập nhật độ tin cậy của bộ nhớ dựa trên bằng chứng validation
```

---

## 2. Danh Sách 13 Stream & 5 Điều Kiện Thử Nghiệm

Dự án CM-HH định nghĩa **13 Stream thực nghiệm** chuẩn hóa đại diện cho các kịch bản dịch chuyển phân phối:

### 2.1 Danh sách 13 Stream:
1. `tsp_size_ascending`: TSP tăng dần kích thước ($n20 \to n50 \to n100 \to n200$). *(Stream cơ sở)*
2. `tsp_size_descending`: TSP giảm dần kích thước ($n200 \to n100 \to n50 \to n20$).
3. `tsp_random_perm_1`: TSP xáo trộn ngẫu nhiên 1 ($n50 \to n200 \to n20 \to n100$).
4. `tsp_random_perm_2`: TSP xáo trộn ngẫu nhiên 2 ($n100 \to n20 \to n200 \to n50$).
5. `cvrp_size_ascending`: Xe giao hàng CVRP tăng dần ($n20 \to n50 \to n100$).
6. `cvrp_size_descending`: Xe giao hàng CVRP giảm dần ($n100 \to n50 \to n20$).
7. `jssp_size_ascending`: Lập lịch máy JSSP tăng dần ($3\times3 \to 6\times6 \to 10\times10$).
8. `jssp_size_descending`: Lập lịch máy JSSP giảm dần ($50\times10 \to 20\times5 \to 10\times5$).
9. `cross_problem_tsp_cvrp_jssp`: Chuyển giao liên miền ($\text{TSP} \to \text{CVRP} \to \text{JSSP}$).
10. `tsp_stationary`: Miền tĩnh kiểm tra ổn định ($n50 \times 4$).
11. `tsp_revisit`: Hồi cứu kiến trúc ($n50 \to n100 \to n50 \to n200$).
12. `related_pair_tsp_cvrp_tsp`: Cặp tương đồng ($\text{TSP} \to \text{CVRP} \to \text{TSP}$).
13. `unrelated_pair_tsp_jssp_tsp`: Cặp dị biệt ($\text{TSP} \to \text{JSSP} \to \text{TSP}$).

### 2.2 5 Điều Kiện Đối Sánh Bắt Buộc (Comparison Conditions):
1. **`isolated`**: Cold start độc lập từng task (không chuyển giao).
2. **`population_carryover`**: Kế thừa quần thể heuristics cuối từ task trước (không có bộ nhớ ngoài).
3. **`naive_bounded`**: Bộ nhớ thô giới hạn dung lượng ($C=20$, FIFO/overwrite đơn giản).
4. **`naive_unbounded`**: Bộ nhớ thô không giới hạn dung lượng.
5. **`archivist_managed`**: Hệ thống quản lý tri thức CM-HH hoàn chỉnh (Archivist + Retriever + Transfer Policy).

---

## 3. Tiêu Chuẩn Thống Kê: Chạy Lặp 3 Đến 5 Lần (Multi-Seed Protocol)

> [!IMPORTANT]
> **Yêu cầu bắt buộc cho công bố khoa học:**
> Do tính ngẫu nhiên của LLM và thuật toán tiến hóa, mỗi Stream **bắt buộc phải được chạy từ 3 đến 5 lần độc lập (Seeds: 1, 2, 3, 4, 5)**.
> Kết quả cuối cùng báo cáo trên bài báo là giá trị **Trung bình $\pm$ Độ lệch chuẩn ($\text{Mean} \pm \text{Std}$)** của các chỉ số:
> - **$AF$ (Average Final Performance)**: Hiệu năng tổng thể trung bình tại cuối stream.
> - **$BWT$ (Backward Transfer)**: Khả năng chống quên (Negative Forgetting).
> - **$FWT$ (Forward Transfer)**: Khả năng chuyển giao tiến Zero-shot.

---

## 4. Thiết Lập Môi Trường (Setup trong 2 Phút)

### Bước 4.1: Cài đặt thư viện Python
Mở PowerShell tại thư mục gốc `CM_HH`:
```powershell
pip install -e .
```
*(Toàn bộ các thư viện PyVRP, OR-Tools, Concorde wrapper, TSPLIB95, SciPy, OpenAI... sẽ được tự động cài đặt).*

### Bước 4.2: Cấu hình LLM API
Chỉnh sửa file `HeurAgenix/cmhh/configs/llm/llm_config.local.json` (hoặc tạo file cấu hình riêng):
```json
{
  "type": "api_model",
  "name": "nvidia-gpt-oss-120b",
  "url": "https://integrate.api.nvidia.com/v1/chat/completions",
  "api_key": "nvapi-dien-key-cua-ban",
  "model": "openai/gpt-oss-120b",
  "temperature": 1,
  "max_tokens": 4096,
  "max_attempts": 5,
  "seed": 42
}
```

---

## 5. Hướng Dẫn Thực Thi Thử Nghiệm

Dự án cung cấp 3 cách chạy từ đơn giản đến toàn diện:

### 🌟 Cách 1: Sử Dụng Menu Tương Tác Chọn Số (Dễ Nhất)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_menu.ps1
```
Màn hình sẽ hiển thị menu 12 lựa chọn stream. Bạn chỉ việc gõ số (ví dụ `1` cho TSP, `3` cho CVRP, `12` cho All Streams) và chọn chế độ chạy.

---

### 🚀 Cách 2: Chạy Từng Stream Riêng Lẻ Bằng Script Định Sẵn

Hệ thống có sẵn các file script được đặt tên tương ứng với từng bài toán:

| File Script | Bài toán & Thứ tự Stream | Lệnh Chạy Kiểm Tra Nhanh (~2–5 phút) | Lệnh Chạy Chuẩn 3–5 Seeds (Full Benchmark) |
|---|---|---|---|
| `scripts\run_stream_1_tsp_ascending.ps1` | **Stream 1:** TSP tăng dần | `.\scripts\run_stream_1_tsp_ascending.ps1` | `.\scripts\run_stream_1_tsp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_2_tsp_descending.ps1` | **Stream 2:** TSP giảm dần | `.\scripts\run_stream_2_tsp_descending.ps1` | `.\scripts\run_stream_2_tsp_descending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_3_cvrp_ascending.ps1` | **Stream 3:** CVRP tăng dần | `.\scripts\run_stream_3_cvrp_ascending.ps1` | `.\scripts\run_stream_3_cvrp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_4_jssp_ascending.ps1` | **Stream 4:** JSSP tăng dần | `.\scripts\run_stream_4_jssp_ascending.ps1` | `.\scripts\run_stream_4_jssp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_5_cross_domain.ps1` | **Stream 5:** TSP $\to$ CVRP $\to$ JSSP | `.\scripts\run_stream_5_cross_domain.ps1` | `.\scripts\run_stream_5_cross_domain.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_6_tsp_stationary.ps1` | **Stream 6:** TSP miền tĩnh | `.\scripts\run_stream_6_tsp_stationary.ps1` | `.\scripts\run_stream_6_tsp_stationary.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_7_tsp_revisit.ps1` | **Stream 7:** TSP hồi cứu | `.\scripts\run_stream_7_tsp_revisit.ps1` | `.\scripts\run_stream_7_tsp_revisit.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_8_cvrp_descending.ps1` | **Stream 8:** CVRP giảm dần | `.\scripts\run_stream_8_cvrp_descending.ps1` | `.\scripts\run_stream_8_cvrp_descending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| `scripts\run_stream_9_jssp_descending.ps1` | **Stream 9:** JSSP giảm dần | `.\scripts\run_stream_9_jssp_descending.ps1` | `.\scripts\run_stream_9_jssp_descending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |

---

### 🌐 Cách 3: Chạy Tự Động Toàn Bộ 13 Stream (All Streams Runner)

Dùng cho máy trạm / server chạy tự động qua đêm cho toàn bộ 13 stream:

#### A. Kiểm tra nhanh trước khi chạy lớn (Smoke Check ~5–10 phút):
```powershell
# Chế độ Zero-LLM (0 token LLM, kiểm tra dữ liệu và solver trong 1 phút):
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -SmokeOnly

# Chế độ QuickSmoke (1 gen / 2 LLM calls per task):
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -QuickSmoke -LlmConfig cmhh/configs/llm/llm_config.local.json
```

#### B. Chạy Benchmark chính thức (3–5 Seeds độc lập):
```powershell
# Chạy 3 seeds độc lập (Seeds 1, 2, 3):
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3 -LlmConfig cmhh/configs/llm/llm_config.local.json

# Chạy đầy đủ 5 seeds độc lập (Seeds 1, 2, 3, 4, 5):
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3,4,5 -LlmConfig cmhh/configs/llm/llm_config.local.json
```

#### C. Phục hồi nếu bị gián đoạn mạng hoặc tắt máy (-Resume):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3 -Resume
```

---

## 6. Giám Sát Thời Gian Thực (Live Monitoring)

Trong khi thí nghiệm đang chạy, mở một cửa sổ PowerShell thứ hai và chạy:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\watch_phase1_tsp_run.ps1
```
Màn hình sẽ hiển thị trực tiếp:
- Tiến độ hoàn thành các task ($k / N$).
- Ma trận hiệu năng thời gian thực $R_{i,j}$ (`performance_matrix.csv`).
- Nhật ký sự kiện bộ nhớ (`events.jsonl`).
- Điểm đánh giá Zero-shot probe trước và sau khi học.

---

## 7. Đọc Hiểu Báo Cáo Kết Quả (Result Interpretation)

Toàn bộ kết quả được lưu tại: `HeurAgenix/cmhh/results/<run_id>/`

### 7.1 Cấu trúc file kết quả:
```text
cmhh/results/<stream_id>_<timestamp>_<condition>_seed<seed>/
├── performance_matrix.csv     <-- Ma trận hiệu năng R_{i,j} (Relative Gap)
├── metrics.json               <-- Chỉ số Continual Learning (AF, BWT, FWT)
├── events.jsonl               <-- Nhật ký toàn bộ sự kiện của hệ thống (audit trail)
├── pre_learning_scores.json   <-- Điểm probe zero-shot trước khi tiến hóa
└── memory/
    ├── memory.jsonl           <-- Kho heuristics được lưu trữ trong bộ nhớ
    └── diagnostics.json       <-- Thống kê tỷ lệ tái sử dụng, đào thải và lineage
```

### 7.2 Cách đọc ma trận `performance_matrix.csv`:
Quy ước điểm: $\text{Score} = -\text{Relative Gap} = -\frac{\text{Heuristic Cost} - \text{Optimal Cost}}{\text{Optimal Cost}}$ (Càng gần `0.0` càng tốt).

```csv
after_task,tsp_n20_uniform,tsp_n50_uniform,tsp_n100_uniform,tsp_n200_uniform
tsp_n20_uniform,-0.120787,,,
tsp_n50_uniform,-0.120787,-0.223088,,
tsp_n100_uniform,-0.120787,-0.223088,-0.237938,
tsp_n200_uniform,-0.120787,-0.223088,-0.237938,-0.253197
```
- **Đường chéo chính:** Hiệu năng đạt được ngay sau khi học xong từng bài toán.
- **Theo cột (từ trên xuống dưới):** Nếu điểm giữ nguyên qua các hàng $\implies$ **Zero Forgetting (Không quên tri thức cũ)**.

### 7.3 Cách đọc `metrics.json`:
- **`average_final_performance` ($AF$):** Điểm trung bình hàng cuối cùng của ma trận.
- **`backward_transfer` ($BWT$):** Chênh lệch hiệu năng các bài cũ trước và sau khi học bài mới ($BWT \ge 0$ là không bị quên).
- **`forward_transfer` ($FWT$):** Mức độ hỗ trợ giải bài mới nhờ tri thức cũ so với cold-start ban đầu ($FWT > 0$ là học nhanh hơn).
