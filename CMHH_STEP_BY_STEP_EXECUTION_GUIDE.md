# CMHH — Hướng Dẫn Thứ Tự Chạy Thử Nghiệm Từng Bước (Step-by-Step Execution Guide)

**Dự án:** Continual Multi-Agent Hyper-Heuristics (CMHH)  
**Mục đích:** File này cung cấp **thứ tự chạy chính xác từng bước một (chỉ số thứ tự từ 1 đến 8)** kèm theo danh sách **toàn bộ 8 cấu hình Stream** và các câu lệnh copy-paste trực tiếp.

---

## 2026-08-29 Architecture Note

The run commands in this guide are valid for pilot experiments. The
`archivist_managed` condition is currently a managed-memory prototype. It should
be reported as full CM-HH only after explicit `CandidateExtractor`,
`TransferPolicy`, `PopulationBuilder`, validation-only transfer feedback, and
child-memory lineage are implemented and audited.

Authoritative design:
`IDEA/source_of_truth/CMHH_Archivist_Retriever_Design_Specification.md`

---

## 📋 Sơ Đồ Lộ Trình Chạy Thử Nghiệm (Workflow Roadmap)

```text
[Giai đoạn 0: Chuẩn bị]
  └─► Bước 0.1: Đặt biến môi trường PYTHONPATH
  └─► Bước 0.2: Tạo file cấu hình LLM (llm_config.json)

[Giai đoạn 1: Chuẩn bị Dữ liệu & Ground-Truth Baseline]
  └─► Bước 1: Validate hệ thống (validate-config)
  └─► Bước 2: Sinh dữ liệu bài toán TSPLIB (generate-data)
  └─► Bước 3: Sinh nghiệm tối ưu chuẩn Concorde (generate-references)
  └─► Bước 4: Kiểm tra checksum nghiệm tối ưu (verify-references)
  └─► Bước 5: Đánh giá Heuristics cơ sở (evaluate-baselines)

[Giai đoạn 2: Chạy Stream Thực Nghiệm Theo Kịch Bản Nghiên Cứu]
  └─► Lựa chọn Stream (Scale-Shift, Domain-Shift, hoặc Curriculum Control)
  └─► Chạy baseline/prototype: EOH, Isolated, Population Carryover, Naive bounded/unbounded, Managed Archivist

[Giai đoạn 3: Phục Hồi & Kiểm Định Kết Quả]
  └─► Bước 7: Phục hồi luồng nếu bị ngắt gián đoạn (--resume)
  └─► Bước 8: Kiểm định thư mục kết quả (audit-run)
```

---

## 🛠️ GIAI ĐOẠN 0: CHUẨN BỊ MÔI TRƯỜNG & LLM API

### Bước 0.1: Mở PowerShell và Thiết Lập `PYTHONPATH`
Mở ứng dụng PowerShell tại thư mục root của dự án (`c:\Users\LENOVO\Projects\CM_HH`):

```powershell
$env:PYTHONPATH="HeurAgenix/src"
```

---

### Bước 0.2: Tạo File Cấu Hình API LLM
Tạo một file định dạng JSON tại đường dẫn: `HeurAgenix/cmhh/configs/llm/my_llm.json`.

#### Mẫu A: Dùng OpenAI API (GPT-4o-mini / GPT-4o)
```json
{
  "type": "api_model",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "api_key": "sk-xxx-key-cua-ban",
  "temperature": 0.0,
  "max_tokens": 2048
}
```

#### Mẫu B: Dùng LLM Local (vLLM / Ollama Qwen2.5-Coder / Llama-3)
```json
{
  "type": "api_model",
  "provider": "openai_compatible",
  "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "api_base": "http://localhost:8000/v1",
  "api_key": "none",
  "temperature": 0.0,
  "max_tokens": 2048
}
```

---

## 🚀 GIAI ĐOẠN 1: CHUẨN BỊ DỮ LIỆU & BENCHMARK REFERENCE

### BƯỚC 1: Validate Hệ Thống (Sanity Check)
Kiểm tra tính hợp lệ của tất cả manifest bài toán và cấu hình stream trước khi sinh dữ liệu:

```powershell
python -m cmhh.cli --repo-root HeurAgenix validate-config --experiment HeurAgenix/cmhh/configs/experiments/archivist_managed.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml
```
*Kết quả chuẩn:* `Validated 12 tasks; stream has 4 tasks` (Exit Code 0).

---

### BƯỚC 2: Sinh Dữ Liệu Bài Toán TSPLIB Benchmark
Tạo ngẫu nhiên các tập dữ liệu thành phố TSP (20, 50, 100, 200 thành phố) dùng chung cho các thí nghiệm:

```powershell
python -m cmhh.cli --repo-root HeurAgenix generate-data --experiment HeurAgenix/cmhh/configs/experiments/archivist_managed.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --seed 42
```

---

### BƯỚC 3: Sinh Nghiệm Tối Ưu Tuyệt Đối (Concorde Exact Reference)
Chạy Concorde Solver để sinh tour tối ưu tuyệt đối (Certified Optimal Tours) cho các tập data `validation` và `test`:

```powershell
python -m cmhh.cli --repo-root HeurAgenix generate-references --solver-config HeurAgenix/cmhh/configs/solvers/concorde.yaml --split validation --split test
```

---

### BƯỚC 4: Verify Checksum & Tính Toàn Vẹn Của Nghiệm Tối Ưu
Xác nhận rằng tất cả các nghiệm tối ưu đã được tạo đầy đủ và khớp với checksum:

```powershell
python -m cmhh.cli --repo-root HeurAgenix verify-references --split validation --split test
```

---

### BƯỚC 5: Đánh Giá Các Thuật Toán Cơ Sở (Baselines)
Đánh giá hiệu năng của các heuristic mầm (nearest neighbor, 2-opt) trên toàn bộ stream:

```powershell
python -m cmhh.cli --repo-root HeurAgenix evaluate-baselines --split validation
python -m cmhh.cli --repo-root HeurAgenix evaluate-baselines --split test
```

---

## 🔬 GIAI ĐOẠN 2: CHẠY THỬ NGHIỆM CONTINUAL STREAM

### 2.1 Danh Sách 8 Stream Phân Theo Kịch Bản Nghiên Cứu

Bạn chọn một trong **8 file Stream YAML** (`HeurAgenix/cmhh/configs/streams/`):

#### Group A: Pilot Scale-Shift Streams (Dịch chuyển quy mô kích thước bài toán)
- 📌 `tsp_size_ascending.yaml`: TSP tăng dần kích thước ($n20 \to n50 \to n100 \to n200$). *(Stream Pilot cơ sở)*
- 📌 `pfsp_size_ascending.yaml`: Flow Shop Scheduling (PFSP) tăng dần kích thước ($n20 \to n50 \to n100 \to n200$).
- 📌 `obp_size_ascending.yaml`: Online Bin Packing (OBP) tăng dần kích thước ($n20 \to n50 \to n100 \to n200$).

#### Group B: Curriculum Learning & Task Ordering Controls (Đánh giá giả thuyết RQ4)
- 📌 `tsp_size_descending.yaml`: TSP giảm dần kích thước ($n200 \to n100 \to n50 \to n20$).
- 📌 `random_perm_1.yaml`: Thứ tự xáo trộn ngẫu nhiên 1 ($n50 \to n200 \to n20 \to n100$).
- 📌 `random_perm_2.yaml`: Thứ tự xáo trộn ngẫu nhiên 2 ($n100 \to n20 \to n200 \to n50$).

#### Group C: Cross-Problem Domain Shift Streams (Dịch chuyển miền bài toán)
- 📌 `cross_problem_same_size.yaml`: Đổi domain bài toán cùng quy mô $n50$ ($\text{TSP-n50} \to \text{PFSP-n50} \to \text{OBP-n50}$).
- 📌 `mixed_problem_size.yaml`: Đổi hỗn hợp bài toán và quy mô ($\text{TSP-n20} \to \text{PFSP-n50} \to \text{OBP-n100} \to \text{TSP-n200}$).

---

### 2.2 Quy Trình Chạy Baseline/Prototype Cho Mỗi Stream

Để phục vụ cho các bảng số liệu pilot, đối với mỗi Stream đã chọn ở trên (ví dụ chọn `tsp_size_ascending.yaml`), bạn lần lượt chạy các baseline/prototype đã có:

---

#### BƯỚC 6.1: Chạy Điều Kiện 1 — `isolated` (Cold-Start Baseline)
*Ý nghĩa:* Mỗi bài toán học độc lập từ đầu, không chuyển giao bất kỳ tri thức nào.

```powershell
python -m cmhh.cli --repo-root HeurAgenix run-stream `
  --experiment HeurAgenix/cmhh/configs/experiments/isolated.yaml `
  --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml `
  --generator heuragenix `
  --llm-config HeurAgenix/cmhh/configs/llm/my_llm.json `
  --seed 42 `
  --run-id run_1_isolated
```

---

#### BƯỚC 6.2: Chạy Điều Kiện 2 — `population_carryover` (Working Population Baseline)
*Ý nghĩa:* Chuyển giao trực tiếp quần thể thuật toán tiến hóa từ task $T_{k-1}$ sang $T_k$ (không có bộ nhớ dài hạn bên ngoài).

```powershell
python -m cmhh.cli --repo-root HeurAgenix run-stream `
  --experiment HeurAgenix/cmhh/configs/experiments/population_carryover.yaml `
  --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml `
  --generator heuragenix `
  --llm-config HeurAgenix/cmhh/configs/llm/my_llm.json `
  --seed 42 `
  --run-id run_2_carryover
```

---

#### BƯỚC 6.3: Chạy Điều Kiện 3 — `naive_memory_sequential` (Uncurated External Memory)
*Ý nghĩa:* Ghi tất cả thuật toán sống sót vào `MemoryStore` thô (dung lượng $C=20$, top-$k=5$, không có Archivist lọc hay bảo vệ).

```powershell
python -m cmhh.cli --repo-root HeurAgenix run-stream `
  --experiment HeurAgenix/cmhh/configs/experiments/naive_memory_sequential.yaml `
  --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml `
  --generator heuragenix `
  --llm-config HeurAgenix/cmhh/configs/llm/my_llm.json `
  --seed 42 `
  --run-id run_3_naive_memory
```

---

#### BƯỚC 6.4: Chạy Điều Kiện 4 — `archivist_managed` (Managed Archivist Prototype)
*Ý nghĩa:* Managed-memory prototype với `WorkingBuffer`, `DefaultArchivist` (Admission Gate, Anchor Protection, Eviction Policy). Chưa gọi là full CM-HH cho báo cáo cuối nếu chưa có `CandidateExtractor`, `TransferPolicy`, `PopulationBuilder`, validation-only transfer feedback, và child-memory lineage.

```powershell
python -m cmhh.cli --repo-root HeurAgenix run-stream `
  --experiment HeurAgenix/cmhh/configs/experiments/archivist_managed.yaml `
  --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml `
  --generator heuragenix `
  --llm-config HeurAgenix/cmhh/configs/llm/my_llm.json `
  --seed 42 `
  --run-id run_4_cmhh_archivist
```

---

## 🚑 GIAI ĐOẠN 3: PHỤC HỒI & KIỂM ĐỊNH KẾT QUẢ

### BƯỚC 7: Phục Hồi Stream Khi Bị Gián Đoạn (Resume Stream Run)
Nếu trong lúc chạy (Bước 6.1 - 6.4) bị mất điện, rớt mạng hoặc đứt API LLM giữa stream, bạn chỉ cần thêm cờ **`--resume`** vào đúng lệnh đã chạy:

```powershell
python -m cmhh.cli --repo-root HeurAgenix run-stream `
  --experiment HeurAgenix/cmhh/configs/experiments/archivist_managed.yaml `
  --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml `
  --generator heuragenix `
  --llm-config HeurAgenix/cmhh/configs/llm/my_llm.json `
  --seed 42 `
  --run-id run_4_cmhh_archivist `
  --resume
```

---

### BƯỚC 8: Kiểm Định Độ Tin Cậy Của Thư Mục Kết Quả (Audit Run)
Sau khi một stream chạy xong, kiểm định xem dữ liệu có đạt các tiêu chuẩn nghiên cứu khoa học không:

```powershell
python -m cmhh.cli --repo-root HeurAgenix audit-run --run-id run_4_cmhh_archivist
```

---

## 📊 VỊ TRÍ ĐỌC KẾT QUẢ

Kết quả của từng lượt chạy được lưu tại: `HeurAgenix/cmhh/results/<run_id>/`

1. **Ma trận hiệu năng (Relative Gap)**: `HeurAgenix/cmhh/results/<run_id>/performance_matrix.csv`
2. **Chỉ số tổng hợp ($AF, BWT, FWT$)**: `HeurAgenix/cmhh/results/<run_id>/metrics.json`
3. **Chẩn đoán bộ nhớ & Lineage đào thải**: `HeurAgenix/cmhh/results/<run_id>/memory/diagnostics.json`
4. **Nhật ký audit toàn bộ sự kiện**: `HeurAgenix/cmhh/results/<run_id>/events.jsonl`
