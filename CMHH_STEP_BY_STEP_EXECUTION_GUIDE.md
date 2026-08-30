# CMHH — Hướng Dẫn Thứ Tự Chạy Thử Nghiệm Từng Bước (Step-by-Step Execution Guide)

**Dự án:** Continual Multi-Agent Hyper-Heuristics (CM-HH)  
**Mục đích:** File này cung cấp quy trình chuẩn thực thi thực nghiệm khoa học, danh sách **toàn bộ 13 cấu hình Stream**, yêu cầu **chạy lặp 3–5 seeds độc lập cho mỗi stream** và các câu lệnh copy-paste trực tiếp.

---

## 📋 Sơ Đồ Lộ Trình Thực Nghiệm (Workflow Roadmap)

```text
[Giai đoạn 0: Cài đặt & Chuẩn bị Môi trường]
  └─► Bước 0.1: Cài đặt thư viện Python (pip install -e .)
  └─► Bước 0.2: Cấu hình LLM API (llm_config.local.json)

[Giai đoạn 1: Kiểm Tra Nhanh Trước Khi Chạy (Pre-Execution Smoke Check)]
  └─► Cách 1A: Chạy Zero-LLM Smoke (~1 phút, 0 token LLM)
  └─► Cách 1B: Chạy QuickSmoke 1 Stream (~2–5 phút với LLM thật)

[Giai đoạn 2: Thực Thi Benchmark Khoa Học Chính Thức (3–5 Seeds Bắt Buộc)]
  └─► Lựa chọn A: Chạy tương tác qua Menu (scripts\run_menu.ps1)
  └─► Lựa chọn B: Chạy từng Stream định sẵn (scripts\run_stream_1... đến run_stream_9...)
  └─► Lựa chọn C: Chạy toàn bộ 13 Stream (scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3,4,5)

[Giai đoạn 3: Giám Sát, Phục Hồi & Trích Xuất Báo Cáo]
  └─► Giám sát thời gian thực (scripts\watch_phase1_tsp_run.ps1)
  └─► Phục hồi nếu bị gián đoạn (-Resume)
  └─► Đọc ma trận hiệu năng (performance_matrix.csv) và chỉ số (metrics.json)
```

---

## 🎯 Yêu Cầu Thực Nghiệm Khoa Học: Chạy Lặp 3 Đến 5 Seeds

> [!IMPORTANT]
> **Quy chuẩn bắt buộc cho bảng số liệu bài báo:**
> Mỗi Stream thực nghiệm phải được chạy lặp lại từ **3 đến 5 lần độc lập (Seeds: 1, 2, 3, 4, 5)** để tính giá trị **Trung bình $\pm$ Độ lệch chuẩn ($\text{Mean} \pm \text{Std}$)** cho các độ đo Continual Learning:
> 1. **$AF$ (Average Final Performance)**: $\frac{1}{K} \sum_{j=1}^K R_{K, j}$ (Hiệu năng tổng thể cuối stream).
> 2. **$BWT$ (Backward Transfer)**: $\frac{1}{K-1} \sum_{j=1}^{K-1} (R_{K, j} - R_{j, j})$ (Độ đo chống quên ngược).
> 3. **$FWT$ (Forward Transfer)**: $\frac{1}{K-1} \sum_{j=2}^K (R_{j-1, j}^{\text{probe}} - R_{\text{isolated}, j})$ (Chuyển giao tiến Zero-shot).

---

## 🛠️ GIAI ĐOẠN 0: CÀI ĐẶT & THIẾT LẬP MÔI TRƯỜNG

### Bước 0.1: Cài đặt Dependencies
Mở PowerShell tại thư mục gốc `CM_HH`:
```powershell
pip install -e .
```

### Bước 0.2: Cấu hình API LLM
Điền API key vào file `HeurAgenix/cmhh/configs/llm/llm_config.local.json`:
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

## 🧪 GIAI ĐOẠN 1: KIỂM TRA NHANH TRƯỚC KHI CHẠY (SMOKE CHECK)

Trước khi chạy benchmark lớn, luôn thực hiện 1 lượt kiểm tra nhanh để đảm bảo code, dataset và API kết nối thông suốt:

### Cách 1: Kiểm tra Zero-LLM (~1 phút, không tốn token LLM)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -SmokeOnly
```

### Cách 2: Kiểm tra Quick-LLM 1 Stream (~2–5 phút với API thật)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_stream_1_tsp_ascending.ps1
```

---

## 🔬 GIAI ĐOẠN 2: CHẠY BENCHMARK KHOA HỌC CHÍNH THỨC (3–5 SEEDS)

Dự án cung cấp **13 Stream thực nghiệm** chuẩn hóa phân loại theo kịch bản:

### 2.1 Bảng Danh Sách 13 Stream & Câu Lệnh Thực Thi 3–5 Seeds

| STT | Tên Stream | Bản chất phân phối Task | Câu Lệnh Chạy 3–5 Seeds (Full Benchmark) |
|:---:|---|---|---|
| **1** | `tsp_size_ascending` | TSP tăng quy mô: $n20 \to n50 \to n100 \to n200$ | `powershell -ExecutionPolicy Bypass -File scripts\run_stream_1_tsp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| **2** | `tsp_size_descending` | TSP giảm quy mô: $n200 \to n100 \to n50 \to n20$ | `powershell -ExecutionPolicy Bypass -File scripts\run_stream_2_tsp_descending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| **3** | `cvrp_size_ascending` | CVRP tăng quy mô: $n20 \to n50 \to n100$ | `powershell -ExecutionPolicy Bypass -File scripts\run_stream_3_cvrp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| **4** | `jssp_size_ascending` | JSSP tăng quy mô: $3\times3 \to 6\times6 \to 10\times10$ | `powershell -ExecutionPolicy Bypass -File scripts\run_stream_4_jssp_ascending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| **5** | `cross_problem_tsp_cvrp_jssp` | Liên miền: $\text{TSP} \to \text{CVRP} \to \text{JSSP}$ | `powershell -ExecutionPolicy Bypass -File scripts\run_stream_5_cross_domain.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| **6** | `tsp_stationary` | Miền tĩnh kiểm tra ổn định: $n50 \times 4$ | `powershell -ExecutionPolicy Bypass -File scripts\run_stream_6_tsp_stationary.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| **7** | `tsp_revisit` | Hồi cứu: $n50 \to n100 \to n50 \to n200$ | `powershell -ExecutionPolicy Bypass -File scripts\run_stream_7_tsp_revisit.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| **8** | `cvrp_size_descending` | CVRP giảm quy mô: $n100 \to n50 \to n20$ | `powershell -ExecutionPolicy Bypass -File scripts\run_stream_8_cvrp_descending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| **9** | `jssp_size_descending` | JSSP giảm quy mô: $50\times10 \to 20\times5 \to 10\times5$ | `powershell -ExecutionPolicy Bypass -File scripts\run_stream_9_jssp_descending.ps1 -FullBenchmark -Seeds 1,2,3,4,5` |
| **10** | `tsp_random_perm_1` | Xáo trộn ngẫu nhiên 1 | `powershell -ExecutionPolicy Bypass -File scripts\run_single_stream.ps1 -Stream tsp_random_perm_1 -Seeds 1,2,3,4,5` |
| **11** | `tsp_random_perm_2` | Xáo trộn ngẫu nhiên 2 | `powershell -ExecutionPolicy Bypass -File scripts\run_single_stream.ps1 -Stream tsp_random_perm_2 -Seeds 1,2,3,4,5` |
| **12** | `related_pair_tsp_cvrp_tsp` | Cặp tương đồng | `powershell -ExecutionPolicy Bypass -File scripts\run_single_stream.ps1 -Stream related_pair_tsp_cvrp_tsp -Seeds 1,2,3,4,5 -SkipReferences` |
| **13** | `unrelated_pair_tsp_jssp_tsp`| Cặp dị biệt | `powershell -ExecutionPolicy Bypass -File scripts\run_single_stream.ps1 -Stream unrelated_pair_tsp_jssp_tsp -Seeds 1,2,3,4,5 -SkipReferences` |

---

### 2.2 Chạy Tự Động Toàn Bộ 13 Stream Trên Server / Máy Trạm

Để chạy toàn bộ benchmark 13 stream tự động với 3 seeds hoặc 5 seeds:

```powershell
# Chạy 3 seeds (Seeds 1, 2, 3):
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3 -LlmConfig cmhh/configs/llm/llm_config.local.json

# Chạy 5 seeds đầy đủ (Seeds 1, 2, 3, 4, 5):
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 -Seeds 1,2,3,4,5 -LlmConfig cmhh/configs/llm/llm_config.local.json
```

---

## 📊 GIAI ĐOẠN 3: GIÁM SÁT & ĐỌC HIỂU KẾT QUẢ

### 3.1 Giám sát thời gian thực (Live Monitoring)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\watch_phase1_tsp_run.ps1
```

### 3.2 Vị trí đọc kết quả
Kết quả của từng lượt chạy được lưu tại: `HeurAgenix/cmhh/results/<run_id>/`

1. **Ma trận hiệu năng ($R_{i,j}$)**: `cmhh/results/<run_id>/performance_matrix.csv`
2. **Chỉ số tổng hợp ($AF, BWT, FWT$)**: `cmhh/results/<run_id>/metrics.json`
3. **Chẩn đoán bộ nhớ & Lineage đào thải**: `cmhh/results/<run_id>/memory/diagnostics.json`
4. **Nhật ký audit toàn bộ sự kiện**: `cmhh/results/<run_id>/events.jsonl`

### 3.3 Kiểm định độ tin cậy kết quả (Audit Run)
```powershell
python -m cmhh.cli --repo-root HeurAgenix audit-run --run-id <run_id>
```
