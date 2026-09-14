# CM-HH: Báo Cáo Chuyển Giao Kỹ Thuật (Engineering Handoff Review)

**Dự án:** Continual Multi-Agent Hyper-Heuristics (CM-HH)  
**Trạng thái hệ thống:** Đã hoàn thiện 100% kiến trúc CM-HH đầy đủ, tích hợp Reference Solvers và vượt qua toàn bộ 168 bài kiểm thử đơn vị & tích hợp.

---

## 1. Trạng Thái Hiện Tại Của Codebase

Toàn bộ các module cốt lõi của hệ thống học liên tục CM-HH đã được cài đặt và kiểm thử nghiêm ngặt:

```text
Các thành phần đã hoàn thiện & hoạt động:
  [x] Pilot 4 Streams (s1_tsp_scale, s2_cvrp_constraint, s3_related_cross_problem, s4_unrelated_cross_problem)
  [x] VRP Constraint Family Graycode Streams (vrp_constraint_graycode, vrp_constraint_graycode_reverse)
  [x] Reference Solvers Pipeline (Concorde cho TSP, PyVRP cho VRP/OVRP/VRPTW, OR-Tools CP-SAT cho JSSP)
  [x] CandidateExtractor (Trích xuất thuật toán tối ưu theo validation score & code hash lineage)
  [x] DeterministicTransferPolicy (Lập kế hoạch chuyển giao: DIRECT_REUSE / REFINE / IGNORE)
  [x] MemoryAwarePopulationBuilder (Khởi tạo quần thể P0 kết hợp giữa tri thức truy xuất và sinh mới)
  [x] 3-Layer Memory Hierarchy (WorkingBuffer -> Archivist Gatekeeper -> MemoryStore jsonl)
  [x] Retriever Engine (Truy xuất dựa trên độ tương đồng cấu trúc và điểm hữu dụng)
  [x] 3-Layer Runtime Complexity Guard (Layer 1: Prompt bounds, Layer 2: Smoke hard timeout 1s, Layer 3: Validation two-tier timeout 15s/60s)
  [x] Strict Validation Contract & Invariant (Loại bỏ hoàn toàn lỗi Survivorship Bias)
  [x] Tracking & Observability (Console logging, File logging, WandB sync, Event logger schema v1)
  [x] Checkpointing & Resilience (--resume bỏ qua các task đã hoàn thành)
```

---

## 2. Sơ Đồ Luồng Hoạt Động Cốt Lõi (Architecture Map)

```text
Task Hoàn Thành
      │
      ▼
CandidateExtractor (Trích xuất top-k candidate xuất sắc)
      │
      ▼
Archivist Gatekeeper (Kiểm duyệt & đánh giá tính mới / chất lượng)
      │
      ▼
MemoryStore (Lưu trữ MemoryUnit bền vững dưới dạng JSONL)
      │
      ▼
RetrieverV0 (Truy xuất tri thức tương thích cho Task mới)
      │
      ▼
DeterministicTransferPolicy (Phân loại hành động: DIRECT_REUSE / REFINE / IGNORE)
      │
      ▼
MemoryAwarePopulationBuilder (Khởi tạo quần thể P0 theo định ngạch tri thức)
      │
      ▼
HeuristicEvolver (Tiến hóa thuật toán với 3-Layer Runtime Guard)
      │
      ▼
Transfer Feedback (Ghi nhận kết quả chuyển giao & cập nhật phả hệ lineage)
```

---

## 3. Hệ Thống Reference Solvers Chuẩn

Hệ thống cung cấp nghiệm tham chiếu chuẩn (Ground Truth) để tính toán **Relative Gap** một cách khách quan:

1. **TSP**: **Concorde Exact Solver** — Giải chính xác bằng phương pháp nhánh và cắt (Branch-and-Cut).
2. **CVRP / OVRP / VRPTW / OVRPTW**: **PyVRP** — Giải bằng thuật toán Hybrid Genetic Search tiên tiến nhất hiện nay, hỗ trợ mọi biến thể ràng buộc.
3. **JSSP**: **OR-Tools CP-SAT** — Giải bài toán phân chia công việc bằng Constraint Programming.

---

## 4. Cơ Chế Bảo Vệ 3-Layer Runtime Guard & Đảm Bảo Độ Phức Tạp

Để đảm bảo các tiến trình chạy tự động qua đêm không bao giờ bị kẹt CPU hoặc sinh mã nguồn lặp vô hạn:

* **Layer 1 (Prompt Constraint)**: Tự động nhúng ràng buộc độ phức tạp tối đa $O(N \log N)$ hoặc $O(N^2)$ vào prompt hệ thống.
* **Layer 2 (Smoke Guard)**: Subprocess riêng biệt chạy thử nghiệm trên 1 instance nhỏ với **Hard Timeout 1.0s**. Loại bỏ ngay các candidate lặp vô hạn trước khi bước vào tiến hóa.
* **Layer 3 (Validation Guard)**: Subprocess độc lập với cơ chế **Two-tier Timeout** (15s mỗi case, 60s tổng mỗi candidate) kết hợp với **Fail-fast Policy**. Bất kỳ candidate nào gặp lỗi hoặc timeout đều bị đánh dấu `INVALID` và loại bỏ trước khi xếp hạng.

---

## 5. Kết Quả Kiểm Thử (Verification Status)

Tất cả 168 bài kiểm thử đơn vị và tích hợp trong thư mục `tests/` đều vượt qua 100%:

```text
============================ 168 passed in 55.01s =============================
```

Bao gồm kiểm thử cho:
- Bộ giải tham chiếu Reference Solvers (PyVRP, Concorde, CP-SAT).
- Cơ chế quản lý bộ nhớ 3 lớp (WorkingBuffer, Archivist, MemoryStore).
- Cơ chế truy xuất, lập kế hoạch và phân bổ hạt giống quần thể.
- Cơ chế Runtime Guard và phòng chống lặp vô hạn.
- Cơ chế khôi phục từ checkpoint (`--resume`).
