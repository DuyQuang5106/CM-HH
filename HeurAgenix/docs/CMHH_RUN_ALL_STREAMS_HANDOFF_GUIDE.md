# Hướng Dẫn Chạy Thử & Bàn Giao Thí Nghiệm Tất Cả Các Stream (CM-HH All Streams Guide)

**Dự án:** Continual Multi-Agent Hyper-Heuristics (CM-HH)  
**Script chính:** `HeurAgenix/scripts/run_all_streams_no_eoh.ps1`  
**Mục đích:** Hướng dẫn cách chạy kiểm tra nhanh toàn bộ luồng trước khi bàn giao và cách chạy benchmark chính thức (Full Budget) cho người nhận bàn giao.

---

## 1. Tổng Quan Về Các Stream & 5 Điều Kiện Thử Nghiệm

Script `run_all_streams_no_eoh.ps1` tự động điều phối thực nghiệm qua **13 Stream bài toán** và **5 điều kiện so sánh**:

### Danh sách 13 Stream:
1. `tsp_size_ascending` (TSP tăng dần kích thước)
2. `tsp_size_descending` (TSP giảm dần kích thước)
3. `tsp_random_perm_1` (TSP hoán vị ngẫu nhiên 1)
4. `tsp_random_perm_2` (TSP hoán vị ngẫu nhiên 2)
5. `cvrp_size_ascending` (CVRP tăng dần kích thước)
6. `cvrp_size_descending` (CVRP giảm dần kích thước)
7. `jssp_size_ascending` (JSSP tăng dần kích thước)
8. `jssp_size_descending` (JSSP giảm dần kích thước)
9. `cross_problem_tsp_cvrp_jssp` (Chuyển giao liên miền: TSP -> CVRP -> JSSP)
10. `tsp_revisit` (Hồi cứu kiến trúc TSP)
11. `tsp_stationary` (Miền tĩnh kiểm tra ổn định)
12. `related_pair_tsp_cvrp_tsp` (Cặp tương đồng)
13. `unrelated_pair_tsp_jssp_tsp` (Cặp dị biệt)

### 5 Điều Kiện So Sánh Trên Mỗi Stream:
1. **`isolated`**: Cold start độc lập từng task.
2. **`population_carryover`**: Kế thừa quần thể heuristics cuối từ task trước.
3. **`naive_bounded`**: Bộ nhớ giới hạn dung lượng (FIFO / overwrite đơn giản).
4. **`naive_unbounded`**: Bộ nhớ không giới hạn (tích lũy toàn bộ).
5. **`archivist_managed`**: Hệ thống quản lý bộ nhớ CM-HH (Archivist + Retriever + Transfer Policy).

---

## 2. Các Cấp Độ Chạy Thử Nghiệm (Execution Profiles)

| Cấp độ | Cờ tham số (Switch) | Ngân sách / Task | Thời gian ước tính | Mục đích sử dụng |
|---|---|---|---|---|
| **Level 1A: Quick LLM Smoke** | `-QuickSmoke` hoặc `-QuickTest` | 1 gen, 1 candidate, 2 LLM calls | ~5–10 phút / toàn bộ stream | Kiểm tra kết nối LLM API và toàn bộ luồng sinh mã trước khi bàn giao |
| **Level 1B: Zero-LLM Smoke** | `-SmokeOnly` hoặc `-NoLLM` | Baseline heuristic (0 LLM call) | ~1–2 phút | Kiểm tra logic dữ liệu, nghiệm chuẩn, bộ nhớ, ma trận CSV không tốn token |
| **Level 2: Mini-Pilot** | `-Pilot` hoặc `-HandoffSmoke` | 2 gens, 1 candidate, 5 LLM calls | ~15–30 phút | Thử nghiệm nhỏ trên 5 stream đại diện để xem động lực tiến hóa |
| **Level 3: Full Benchmark** | (Mặc định không truyền cờ smoke) | 100 gens, 5 candidates, 500 calls | Chạy qua đêm / nhiều ngày | Benchmark sản phẩm chính thức cho bài báo / báo cáo |

---

## 3. Hướng Dẫn Từng Bước Cho Người Bàn Giao (Pre-Handoff Sanity Check)

Mở PowerShell tại thư mục `c:\Users\LENOVO\Projects\CM_HH\HeurAgenix` (hoặc thư mục root):

### Bước 3.1: Kiểm tra siêu tốc Zero-LLM (1–2 phút)
Xác nhận tất cả dữ liệu, cấu hình YAML và xuất báo cáo hoạt động tốt:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -SmokeOnly
```

### Bước 3.2: Kiểm tra nhanh với LLM API thật (-QuickSmoke)
Xác nhận kết nối API NVIDIA/OpenAI, sinh prompt, tiến hóa mã và trích xuất candidate qua 13 stream:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -QuickSmoke -LlmConfig cmhh/configs/llm/llm_config.local.json
```

*(Tùy chọn) Nếu chỉ muốn test 1–2 stream cụ thể để test LLM trong 30 giây:*
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -QuickSmoke -Streams "tsp_size_ascending,cvrp_size_ascending"
```

---

## 4. Hướng Dẫn Cho Người Nhận Bàn Giao (Production Benchmark Run)

### Bước 4.1: Cấu hình file API LLM
Đảm bảo file `HeurAgenix/cmhh/configs/llm/llm_config.local.json` chứa API key và endpoint chính xác:
```json
{
  "type": "api_model",
  "name": "nvidia-gpt-oss-120b",
  "url": "https://integrate.api.nvidia.com/v1/chat/completions",
  "api_key": "nvapi-xxx",
  "model": "openai/gpt-oss-120b",
  "temperature": 1,
  "top-p": 1,
  "max_tokens": 4096,
  "max_attempts": 5,
  "sleep_time": 5,
  "seed": 42,
  "stream": false
}
```

### Bước 4.2: Chạy Full Benchmark Toàn Bộ 13 Stream (Seed 1)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1 -LlmConfig cmhh/configs/llm/llm_config.local.json
```

### Bước 4.3: Chạy Đầy Đủ 3 Seeds Độc Lập (Multi-Seed Benchmark)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3 -LlmConfig cmhh/configs/llm/llm_config.local.json
```

### Bước 4.4: Phục Hồi Nếu Bị Gián Đoạn (--Resume)
Nếu máy tính bị tắt hoặc ngắt mạng giữa chừng, chỉ cần thêm cờ `-Resume`:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1 -Resume
```
Hệ thống sẽ đọc checkpoint tại `cmhh/results/<run-id>/checkpoints/latest.json` và tiếp tục đúng task đang dở mà không phải chạy lại từ đầu.

---

## 5. Chạy Từng Stream Riêng Lẻ (Single Stream Runner)

Dự án cung cấp 2 cách chạy từng stream cực kỳ tiện lợi:

### Cách 5.1: Dùng Menu chọn số (Interactive Selector)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_menu.ps1
```

### Cách 5.2: Các file script định sẵn tương ứng từng Stream:

| File Script có sẵn | Tên Stream | Chi tiết thứ tự Task |
|---|---|---|
| `scripts\run_stream_1_tsp_ascending.ps1` | `tsp_size_ascending` | $n20 \to n50 \to n100 \to n200$ |
| `scripts\run_stream_2_tsp_descending.ps1` | `tsp_size_descending` | $n200 \to n100 \to n50 \to n20$ |
| `scripts\run_stream_3_cvrp_ascending.ps1` | `cvrp_size_ascending` | $n20 \to n50 \to n100$ |
| `scripts\run_stream_4_jssp_ascending.ps1` | `jssp_size_ascending` | $3\times3 \to 6\times6 \to 10\times10$ |
| `scripts\run_stream_5_cross_domain.ps1` | `cross_problem_tsp_cvrp_jssp` | $\text{TSP} \to \text{CVRP} \to \text{JSSP}$ |
| `scripts\run_stream_6_tsp_stationary.ps1` | `tsp_stationary` | $n50 \times 4$ (Kiểm chứng ổn định) |
| `scripts\run_stream_7_tsp_revisit.ps1` | `tsp_revisit` | $n50 \to n100 \to n50 \to n200$ (Hồi cứu) |
| `scripts\run_stream_8_cvrp_descending.ps1` | `cvrp_size_descending` | $n100 \to n50 \to n20$ |
| `scripts\run_stream_9_jssp_descending.ps1` | `jssp_size_descending` | $50\times10 \to 20\times5 \to 10\times5$ |

**Ví dụ thực thi:**
- **Test nhanh CVRP giảm dần (~2 phút):**
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\run_stream_8_cvrp_descending.ps1
  ```
- **Test nhanh JSSP giảm dần (~2 phút):**
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\run_stream_9_jssp_descending.ps1
  ```
- **Chạy Full Benchmark chính thức (Seed 1,2,3):**
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\run_stream_8_cvrp_descending.ps1 -FullBenchmark -Seeds 1,2,3
  ```


---

## 6. Giám Sát Tiến Trình Thời Gian Thực (Live Monitoring)

Mở một cửa sổ PowerShell thứ hai và chạy:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\watch_phase1_tsp_run.ps1
```
Watcher sẽ tự động tìm run mới nhất và hiển thị:
- Số task đã hoàn thành (`completed tasks: k / N`).
- Ma trận hiệu năng hiện tại (`performance_matrix.csv`).
- Trạng thái bộ nhớ và sự kiện mới nhất (`events.jsonl`).
- Log chi tiết tiến hóa LLM gần nhất.

---

## 7. Các Tệp Báo Cáo Kết Quả Cần Kiểm Tra

Sau khi chạy xong, kết quả được lưu tại `HeurAgenix/cmhh/results/<run-id>/`:
1. `performance_matrix.csv`: Ma trận hiệu năng $R_{i,j}$ đánh giá khả năng chuyển giao tiến và chống quên ngược.
2. `metrics.json`: Các chỉ số Continual Learning (Average Final Performance, Backward Transfer, Forward Transfer).
3. `pre_learning_scores.json`: Điểm Zero-shot Probe trước khi tiến hóa.
4. `memory/diagnostics.json`: Thống kê tần suất truy xuất, tỷ lệ tái sử dụng và độ hiệu quả của bộ nhớ Archivist.
5. `<RunPrefix>_driver.log`: Toàn bộ log console quá trình chạy.

