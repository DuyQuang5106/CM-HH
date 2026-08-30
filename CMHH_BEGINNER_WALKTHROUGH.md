# CMHH — Hướng Dẫn Walkthrough Dành Cho Người Mới (Beginner & Quickstart Guide)

**Dự án:** CMHH — Continual Multi-Agent Hyper-Heuristics  
**Mục tiêu file này:** Giúp người mới bắt đầu (sinh viên, nghiên cứu sinh, ML engineer) nhanh chóng hiểu bức tranh tổng thể, tự thiết lập môi trường, chạy thử nghiệm đầu tiên và đọc hiểu kết quả một cách dễ dàng nhất.

---

## 2026-08-29 Architecture Note

The clearest way to understand CM-HH now is as a memory-transfer pipeline:

```text
completed task
    -> CandidateExtractor: choose notable heuristics from final population
    -> Archivist: decide what becomes long-term memory
    -> MemoryStore: persist selected knowledge
    -> Retriever: recall relevant memory for the next task
    -> TransferPolicy: choose DIRECT_REUSE / REFINE / IGNORE
    -> PopulationBuilder: build P0 from memory-derived and fresh candidates
    -> evolution: search normally on the current task
    -> feedback: update memory using validation-only transfer evidence
```

Important reading rule:

```text
retrieved != transferred
transferred != survived evolution
survived != caused improvement
```

The current `archivist_managed` condition is a runnable managed-memory
prototype. It should be called "full CM-HH" only after `CandidateExtractor`,
`TransferPolicy`, `PopulationBuilder`, validation-only transfer feedback, and
child-memory lineage are implemented and audited.

---

## 1. Giới thiệu Dễ hiểu về CMHH (Conceptual Overview)

### CMHH là gì?
Hãy tưởng tượng bạn có một **AI Agent (LLM)** chuyên viết code giải các bài toán tối ưu (như bài toán Người du lịch - TSP). 
- Khi giải bài toán nhỏ ($T_1$: TSP 20 thành phố), AI tìm ra một số thuật toán (heuristics) rất hay.
- Khi chuyển sang bài toán lớn hơn ($T_2$: TSP 50 thành phố), bạn muốn AI **tận dụng tri thức cũ** thay vì phải học lại từ đầu, nhưng đồng thời **không được quên** cách giải bài toán nhỏ ($T_1$).

**CMHH** chính là hệ thống quản lý bộ nhớ và điều phối agent để thực hiện việc học liên tục (Continual Learning) đó!

---

### Sơ đồ Kiến trúc 5 Thành phần Chính

```
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
                       - Chọn lọc kinh nghiệm tốt (Admission)
                       - Bảo vệ thuật toán mỏ neo (Anchor Protection)
                       - Đào thải tri thức cũ yếu (Eviction)
                                │
                                ▼
                       [ Long-Term MemoryStore ] (Bộ nhớ dài hạn 3-Layer)
                                ▲
                                │
                       [ Retriever Engine ] (Động cơ truy xuất tri thức)
```

1. **`TaskStream`**: Chuỗi các bài toán nối tiếp nhau ($T_1 \rightarrow T_2 \rightarrow T_3 \dots$).
2. **`WorkingBuffer`**: Bộ đệm ngắn hạn chứa các thuật toán mới được LLM tạo ra trong quá trình tìm kiếm.
3. **`Archivist`**: "Người quản thư" thông minh — quyết định thuật toán nào đủ giỏi để lưu vào bộ nhớ, thuật toán nào là mỏ neo (protected anchor), và thuật toán nào nên xóa khi bộ nhớ đầy.
4. **`MemoryStore` & `Retriever`**: Bộ nhớ dài hạn lưu trữ thuật toán theo dạng 3 lớp ($h_i, k_i, z_i, \mu_i$) và động cơ tìm kiếm gợi ý thuật toán phù hợp cho task mới.
5. **`Probes` ($A$ & $C$)**: Các bài "thi thử" READ-ONLY để đo đạc chính xác khả năng chuyển giao tri thức ($FWT$) và khả năng giữ nét (không bị quên - $BWT$).

---

## 2. Hướng Dẫn Quickstart 5 Phút (Bắt đầu từ Zero)

### Bước 1: Mở Terminal và Đặt Biến Môi Trường `PYTHONPATH`
Mở PowerShell tại thư mục root dự án (`c:\Users\LENOVO\Projects\CM_HH`):

```powershell
$env:PYTHONPATH="HeurAgenix/src"
```

### Bước 2: Chuẩn bị File Cấu Hình LLM (`llm_config.json`)
Tạo một file cấu hình LLM (ví dụ `HeurAgenix/cmhh/configs/llm/my_llm.json`):

#### Nếu dùng OpenAI API:
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

#### Nếu dùng Model Local (vLLM / Ollama / Local Server):
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

### Bước 3: Kiểm tra Sanity Check Hệ Thống
Chạy lệnh kiểm tra cấu hình để đảm bảo mọi file manifest và code đều sẵn sàng:

```powershell
python -m cmhh.cli --repo-root HeurAgenix validate-config
```
*Nếu đầu ra báo:* `Validated 12 tasks; stream has 4 tasks` $\rightarrow$ **Chúc mừng, hệ thống của bạn hoàn toàn sẵn sàng!**

---

## 3. Quy Trình Chạy Thử Nghiệm Chi Tiết (Từng Bước)

Để chạy một thử nghiệm hoàn chỉnh, bạn thực hiện 4 bước đơn giản sau:

### Bước 1: Sinh Dữ Liệu Benchmark TSPLIB
Tạo dữ liệu các bài toán TSP (20, 50, 100, 200 thành phố) dùng chung cho các thí nghiệm:

```powershell
python -m cmhh.cli --repo-root HeurAgenix generate-data --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --seed 42
```

### Bước 2: Sinh Nghiệm Chuẩn Tối Ưu (Exact Optimal Tours)
Sinh nghiệm tối ưu tuyệt đối bằng Concorde solver để làm mốc so sánh khoảng cách (relative gap):

```powershell
python -m cmhh.cli --repo-root HeurAgenix generate-references --solver-config HeurAgenix/cmhh/configs/solvers/concorde.yaml --split validation --split test
```

### Bước 3: Chạy Stream Học Liên Tục (Continual Learning Stream)
Chạy thử nghiệm CMHH với chế độ bộ nhớ quản lý bởi Archivist:

```powershell
python -m cmhh.cli --repo-root HeurAgenix run-stream --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --generator heuragenix --llm-config HeurAgenix/cmhh/configs/llm/my_llm.json --seed 42 --run-id my_first_cmhh_run
```

### Bước 4: Kiểm Định Thư Mục Kết Quả (Audit Check)
Sau khi stream chạy xong, kiểm tra xem thư mục kết quả có đạt chuẩn audit nghiên cứu không:

```powershell
python -m cmhh.cli --repo-root HeurAgenix audit-run --run-id my_first_cmhh_run
```

---

## 4. Hướng Dẫn Đọc Hiểu Kết Quả Kết Xuất (Result Interpretation)

Sau khi chạy xong, kết quả sẽ nằm tại thư mục: `HeurAgenix/cmhh/results/my_first_cmhh_run/`.

### 4.1 Cấu trúc Thư mục Kết quả:
```text
my_first_cmhh_run/
├── performance_matrix.csv     <-- File quan trọng nhất: Ma trận hiệu năng (Relative Gap)
├── metrics.json               <-- Điểm tổng hợp cho paper: AF, BWT, FWT
├── events.jsonl               <-- Nhật ký toàn bộ sự kiện (schema_version = 1)
├── memory/
│   ├── memory.jsonl           <-- Kho bộ nhớ dài hạn
│   └── diagnostics.json       <-- Chẩn đoán sức khỏe bộ nhớ & lineage đào thải
└── checkpoints/
    └── latest.json            # File dùng để resume nếu đứt đoạn
```

---

### 4.2 Cách đọc file `performance_matrix.csv` (Dễ hiểu nhất)

File này lưu Ma trận Hiệu năng $R_{k,j}$ chứa **Khoảng cách tương đối so với nghiệm tối ưu (Relative Gap)**.
- **Quy ước điểm:** Điểm $= - \text{Relative Gap} = - \frac{\text{Kết quả Heuristic} - \text{Nghiệm Tối ưu}}{\text{Nghiệm Tối ưu}}$
- **Nguyên tắc:** Điểm càng gần `0.0` càng tốt (ví dụ: `-0.02` tức là chỉ cách nghiệm tối ưu $2\%$).

#### Mẫu file `performance_matrix.csv`:
```csv
after_task,tsp_20,tsp_50,tsp_100,tsp_200
tsp_20,-0.012,,
tsp_50,-0.015,-0.035,,
tsp_100,-0.018,-0.038,-0.062,
tsp_200,-0.021,-0.040,-0.065,-0.098
```

#### Hướng dẫn soi ma trận:
- **Đường chéo chính (`-0.012`, `-0.035`, `-0.062`, `-0.098`)**: Kết quả đạt được trên từng bài toán **ngay sau khi học xong** bài toán đó.
- **Nhìn theo Cột (ví dụ cột `tsp_20`)**:
  - Khi mới học xong `tsp_20`: điểm là `-0.012`.
  - Sau khi học tiếp `tsp_50`: điểm `tsp_20` thành `-0.015`.
  - Sau khi học tiếp `tsp_200`: điểm `tsp_20` thành `-0.021`.
  $\Rightarrow$ Điểm giảm nhẹ nghĩa là có hiện tượng quên nhẹ qua thời gian. Nếu điểm giữ nguyên `-0.012` $\implies$ **Zero Forgetting** (Hoàn hảo!).

---

### 4.3 Cách đọc file `metrics.json` (Các con số đưa vào Paper)

```json
{
  "average_final_performance": -0.056,
  "backward_transfer": -0.007,
  "forward_transfer": 0.042
}
```

1. **`average_final_performance` ($AF$)**: Điểm trung bình của hệ thống trên tất cả các task ở **thời điểm kết thúc stream**. ($AF$ càng gần $0.0$ càng tốt).
2. **`backward_transfer` ($BWT$)**: Đánh giá khả năng "giữ nét" bài học cũ:
   - $BWT = 0$: Không bị quên bài cũ.
   - $BWT < 0$: Bị quên bài cũ (Quên chức năng).
   - $BWT > 0$: Học bài mới giúp giải bài cũ **tốt hơn nữa** (Học hỗ trợ ngược).
3. **`forward_transfer` ($FWT$)**: Khả năng "học một biết mười" (Zero-shot transfer) khi gặp bài toán mới hoàn toàn so với việc học từ đầu. ($FWT > 0$ nghĩa là bộ nhớ giúp giải task mới tốt hơn ngay từ đầu).

---

### 4.4 Cách đọc file `memory/diagnostics.json` (Sức khỏe Bộ nhớ)

```json
{
  "schema_version": 1,
  "retrieval_coverage": 0.416,
  "duplicate_key_rate_mean": 0.0,
  "post_reuse_validation_delta_mean": 0.038,
  "eviction_lineage": [
    {
      "memory_id": "mem_12345",
      "task_id": "tsp_100",
      "timestamp": "2026-08-20T00:15:30.123456+00:00"
    }
  ],
  "failure_mode_labels": []
}
```

- **`retrieval_coverage`**: Tỷ lệ phần trăm bộ nhớ từng được lấy ra tái sử dụng.
- **`post_reuse_validation_delta_mean`**: Mức độ cải thiện kết quả khi tái sử dụng bộ nhớ (Delta $> 0$ là bộ nhớ có ích).
- **`eviction_lineage`**: Danh sách truy vết chính xác thuật toán nào đã bị xóa, xóa ở task nào và vào lúc nào.
- **`failure_mode_labels`**: Tự động cảnh báo nếu bộ nhớ gặp sự cố (ví dụ `harmful_reuse`: tái sử dụng gây hại, `retrieval_pollution`: rác bộ nhớ).

---

## 5. Các Tình Huống Thường Gặp & Cách Xử Lý (Troubleshooting)

### Q1: Đang chạy stream thì bị mất mạng / đứt API key giữa chừng?
**Trả lời:** Đừng lo! CMHH tự động lưu checkpoint sau mỗi task. Bạn chỉ cần sửa lỗi mạng/API rồi thêm cờ `--resume`:
```powershell
python -m cmhh.cli --repo-root HeurAgenix run-stream --experiment HeurAgenix/cmhh/configs/experiments/phase0_tsp.yaml --stream HeurAgenix/cmhh/configs/streams/tsp_size_ascending.yaml --run-id my_first_cmhh_run --resume --generator heuragenix --llm-config HeurAgenix/cmhh/configs/llm/my_llm.json
```

### Q2: Làm sao để so sánh CMHH với các phương pháp Baseline khác?
**Trả lời:** Để vẽ biểu đồ so sánh pilot, bạn chạy baseline/prototype đã có với các file cấu hình experiment tương ứng:
1. **`isolated_tsp.yaml`**: Học từng task độc lập (Cold start).
2. **`population_carryover_tsp.yaml`**: Bê nguyên quần thể cũ sang task mới (Không có bộ nhớ dài hạn).
3. **`naive_memory_tsp.yaml`**: Lưu bộ nhớ thô (Không có Archivist lọc và bảo vệ).
4. **`archivist_tsp.yaml` / `archivist_managed.yaml`**: Managed Archivist prototype (Có Archivist & WorkingBuffer). Chưa gọi là full CM-HH nếu chưa có transfer pipeline đầy đủ.
5. **`h1_naive_unbounded.yaml`**: Naive memory không giới hạn capacity, dùng để chẩn đoán capacity pressure.
6. **`eoh_cold_start.yaml`**: Official EOH cold-start baseline.

---

## 6. Lời Kết & Liên Hệ

Hệ thống CMHH đã được thiết kế sẵn sàng, chuẩn hóa 100% theo các tiêu chí nghiên cứu khoa học nghiêm ngặt. Nếu bạn gặp khó khăn trong quá trình chạy, hãy kiểm tra file `events.jsonl` hoặc chạy lệnh `audit-run` để nhận thông báo hướng dẫn chi tiết!
