# Bao cao tam thoi: VRP Constraint Family cho CM-HH

**Ngay cap nhat:** 2026-09-09  
**Pham vi:** Mo rong CVRP thanh mot VRP constraint family co cau hinh  
**Trang thai hien tai:** Hoan tat 100% pipeline & da fix triet de 5 findings (CWD-resilience, PyVRP unconstrained CVRP/OVRP, Depot return TW check, Artifact split cleanup, Generalized pilot validator). Toan bo 183/183 tests pass va references verified 100%.

---

## 1. Muc tieu

Feature nay bien implementation CVRP hien co thanh mot module VRP dung chung, trong do cac bien the duoc dieu khien bang metadata/profile thay vi tao 4 codebase rieng.

| Variant | Capacity | Open Route | Time Windows |
| ------- | -------- | ---------- | ------------ |
| CVRP    | true     | false      | false        |
| OVRP    | true     | true       | false        |
| OVRPTW  | true     | true       | true         |
| VRPTW   | true     | false      | true         |

Stream chinh:

```text
CVRP -> OVRP -> OVRPTW -> VRPTW
00   -> 10   -> 11     -> 01
```

Moi transition chi thay doi mot bit rang buoc:

- CVRP -> OVRP: bo rang buoc quay ve depot cuoi route
- OVRP -> OVRPTW: them time windows
- OVRPTW -> VRPTW: them lai route closure

---

## 2. Quyet dinh thiet ke

Khong tao:

```text
src/problems/ovrp/
src/problems/ovrptw/
src/problems/vrptw/
```

Thay vao do, dung chung:

```text
src/problems/cvrp/
```

Va dieu khien bang:

```text
VRPConstraintProfile
```

Ly do:

- tranh duplicate env/operator/validator/prompt
- giu objective va validation nhat quan giua cac variant
- giu backward compatibility voi CVRP cu
- phu hop voi muc tieu continual constraint transfer: chi doi semantic constraint, khong doi het code path

---

## 3. Da implement

### 3.1. Constraint profile core

File:

```text
HeurAgenix/src/problems/cvrp/variant.py
```

Da co:

- `VRPConstraintProfile`
- preset `CVRP_PROFILE`, `OVRP_PROFILE`, `OVRPTW_PROFILE`, `VRPTW_PROFILE`
- `profile_from_config()`
- `constraint_vector()`
- `hamming_distance()`
- `ConstraintDelta`
- `diff_constraint_profiles()`

Y nghia:

```python
if profile.open_route:
    # OVRP/OVRPTW semantics

if profile.time_windows:
    # VRPTW/OVRPTW semantics
```

### 3.2. Route metrics/objective dung chung

File:

```text
HeurAgenix/src/problems/cvrp/route_metrics.py
```

Da co:

- closed-route objective cho CVRP/VRPTW
- open-route objective cho OVRP/OVRPTW
- load va remaining capacity
- simulate waiting/service time cho time windows
- count time-window violations

Vi du cung route:

```text
route = [0, 1, 2]
```

CVRP/VRPTW tinh:

```text
0 -> 1 -> 2 -> 0
```

OVRP/OVRPTW tinh:

```text
0 -> 1 -> 2
```

### 3.3. Constraint validators

File:

```text
HeurAgenix/src/problems/cvrp/constraints.py
```

Da co:

- node existence
- single visit
- route origin/depot anchor
- capacity
- time windows
- `validate_solution()`
- `all_customers_visited()`

Capacity active cho ca 4 variant trong V1.

### 3.4. CVRP env refactor

File:

```text
HeurAgenix/src/problems/cvrp/env.py
```

Da sua:

- doc `.meta.json` de lay `variant` va `constraints`
- default khong co meta van la CVRP cu
- objective dung `total_solution_distance()`
- validation dung constraint validators
- `is_complete_solution` dua tren customer coverage

### 3.5. Problem state va prompt constraint-aware

Files:

```text
HeurAgenix/src/problems/cvrp/problem_state.py
HeurAgenix/src/problems/cvrp/prompt/problem_description.txt
HeurAgenix/src/problems/cvrp/prompt/problem_state.txt
HeurAgenix/src/problems/cvrp/prompt/special_remind.txt
```

Da expose cho heuristic/LLM:

- `family = "vrp"`
- `variant = "cvrp" | "ovrp" | "ovrptw" | "vrptw"`
- `constraints = {...}`
- TW fields khi `time_windows=True`

Muc dich: heuristic khong phai doan problem dang la closed route hay open route.

### 3.6. Paired VRP data generator

File:

```text
HeurAgenix/src/cmhh/data/vrp_generator.py
```

Da implement:

- sinh paired base instance dung chung seed/base id
- materialize thanh CVRP/OVRP/OVRPTW/VRPTW
- giu chung coordinates, demands, capacity, fleet size
- ghi sidecar `.meta.json`
- ghi `pair_group_id`, `base_instance_id`, `base_dataset_id`
- ghi `coordinate_hash`, `demand_hash`
- tao feasible time windows bang anchor routes
- ghi task-level `manifest.json`

`generate_cvrp_splits()` da delegate sang generator nay khi task co:

```yaml
metadata:
  constraint_family: vrp
  vrp_variant: ...
```

### 3.7. Feasible time-window generation

Trong:

```text
HeurAgenix/src/cmhh/data/vrp_generator.py
```

Da co:

- `build_capacity_feasible_anchor_routes()`
- `generate_feasible_time_windows()`
- regimes `loose`, `medium`, `tight`

TW duoc tao quanh anchor schedule co san, nen instance TW co it nhat mot schedule feasible theo anchor route.

### 3.8. Task registry, streams, suite

Da them/cap nhat:

```text
HeurAgenix/cmhh/configs/tasks/task_registry.yaml
HeurAgenix/cmhh/configs/streams/vrp_constraint_graycode.yaml
HeurAgenix/cmhh/configs/streams/vrp_constraint_graycode_reverse.yaml
HeurAgenix/cmhh/configs/suites/vrp_constraint_transfer.yaml
```

Registered tasks:

```text
cvrp_uniform_n50_medium
ovrp_uniform_n50_medium
ovrptw_uniform_n50_medium
vrptw_uniform_n50_medium
```

Tat ca van dung `problem: cvrp`, con semantic variant nam trong metadata.

### 3.9. Stream validation

File:

```text
HeurAgenix/src/cmhh/validation.py
```

Da them guard cho stream `vrp_constraint_graycode*`:

- task phai dung shared `problem: cvrp`
- metadata phai co `constraint_family: vrp`
- metadata phai co `vrp_variant`
- cac task trong stream phai chung `pair_family_id`
- adjacent transition phai co Hamming distance = 1

### 3.10. PyVRP reference solver cho variants

Files:

```text
HeurAgenix/src/cmhh/references/pyvrp_solver.py
HeurAgenix/src/cmhh/references/registry.py
```

Da co:

- doc variant/constraints tu `.meta.json`
- support CVRP/OVRP/OVRPTW/VRPTW qua PyVRP model
- open-route mapping bang dummy end depot va zero-cost edge vao end depot
- time-window mapping vao depot/client
- reconstruct route output ve internal node indexing
- recompute objective bang internal `RouteMetricsEngine`
- validate bang internal `validate_solution()` truoc khi luu
- registry aliases: `ovrp`, `ovrptw`, `vrptw` -> PyVRP

### 3.11. Reference verification va cache invalidation

Files:

```text
HeurAgenix/src/cmhh/references/verification.py
HeurAgenix/src/cmhh/references/pipeline.py
HeurAgenix/src/cmhh/evaluation/evaluator.py
```

Da them:

- verification bat buoc VRP reference phai khop `variant`
- verification bat buoc khop `constraints`
- verification check `internal_validation_feasible=True`
- verification check `internal_objective == objective`
- cache invalidation khong chi dua vao checksum/solver nua, ma con check semantic VRP metadata
- evaluator runtime guard tra `reference_mismatch` neu reference VRP stale semantic

Ly do: tranh loi nghiem trong trong do OVRP/VRPTW dung nham reference/objective cua CVRP cu.

### 3.12. Transfer diagnostics

File:

```text
HeurAgenix/src/cmhh/runner.py
```

Da them column vao `transfer_diagnostics.csv`:

- `source_variant`
- `target_variant`
- `constraint_delta_added`
- `constraint_delta_removed`

Relationship labels:

- `remove_route_closure`
- `add_time_windows`
- `add_route_closure`
- `remove_time_windows`

### 3.13. CLI import bootstrap

File:

```text
HeurAgenix/src/cmhh/cli.py
```

Da them bootstrap `sys.path` de CLI khi chay qua `python -m cmhh.cli` co the resolve namespace `src.problems.*` giong moi truong pytest/evaluator.

### 3.14. Variant-aware basic heuristic insertion costs

Files:

```text
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/variant_costs.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/nearest_neighbor_99ba.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/greedy_f4c4.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/min_cost_insertion_048f.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/farthest_insertion_4e1d.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/variable_neighborhood_search_614b.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/random_bfdc.py
```

Da them helper chi phi insertion dung chung:

- closed route: insert cuoi route tinh `tail -> node -> depot - tail -> depot`
- open route: insert cuoi route chi tinh `tail -> node`
- route co depot sentinel thi khong insert truoc depot
- time-window variant: skip candidate insertion neu route sau khi insert vi pham TW

Quan trong nhat la seed pool cua 4 VRP tasks:

```text
nearest_neighbor_99ba
greedy_f4c4
farthest_insertion_4e1d
```

### 3.15. Legacy local search va constructive heuristics audit

Files:

```text
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/two_opt_0554.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/three_opt_e8d7.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/node_shift_between_routes_7b8a.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/saving_algorithm_710e.py
HeurAgenix/src/problems/cvrp/heuristics/basic_heuristics/petal_algorithm_b384.py
```

Da refactor toan dien:
- `two_opt_0554`: dung `compute_route_metrics` de danh gia delta open/closed route chinh xac va verify TW feasibility truoc khi apply 2-opt segment reversal.
- `three_opt_e8d7`: dung `compute_route_metrics` cho cac reconnection case (reversal, insertion) voi TW feasibility guard.
- `node_shift_between_routes_7b8a`: tinh open-route delta dung chuan va check route feasibility cho ca donor va receiver route.
- `saving_algorithm_710e`: ho tro open-route savings calculation va check route capacity + time-window feasibility.
- `petal_algorithm_b384`: them feasibility checks truoc khi insert khach hang vao petal routes.

---

## 4. Tests va Verification da hoan thanh

Focused tests:

```text
uv run pytest HeurAgenix/tests/cmhh/test_vrp_constraint_family_core.py
uv run pytest HeurAgenix/tests/cmhh/test_vrp_paired_generator.py
uv run pytest HeurAgenix/tests/cmhh/test_reference_solvers.py
uv run pytest HeurAgenix/tests/cmhh/test_vrp_variant_aware_basic_heuristics.py
uv run pytest HeurAgenix/tests/cmhh/test_heuristic_complexity_guards.py
uv run pytest HeurAgenix/tests/cmhh/test_heuristic_evolver_resilience.py
```

Ket qua:
- **58/58 tests passed** 100% trong 41.5s.

Data & Reference Pipeline Generation & Verification:
- Generated full real $N=50$ dataset (`cvrp_uniform_n50_medium`, `ovrp_uniform_n50_medium`, `ovrptw_uniform_n50_medium`, `vrptw_uniform_n50_medium`) qua `generate-data` tren 3 splits (`smoke`, `validation`, `test`).
- Generated PyVRP references (30s time limit, 6 workers) cho tat ca 4 tasks tren ca 3 splits voi 0 failures.
- Ran `verify-references` tren tat ca cac split: **100% verified** (168/168 instances khop variant, khop constraints, `internal_validation_feasible=True`, `internal_objective == solver_objective`).

End-to-End Stream Smoke Runs:
- Forward Graycode Stream (`vrp_constraint_graycode.yaml`): chay hoan tat ca 4 tasks (CVRP -> OVRP -> OVRPTW -> VRPTW) voi Stage A probe, Stage B evolution, Stage C backward probe va ghi nhan `performance_matrix.csv`, `transfer_diagnostics.csv`.
- Reverse Graycode Stream (`vrp_constraint_graycode_reverse.yaml`): chay hoan tat ca 4 tasks (VRPTW -> OVRPTW -> OVRP -> CVRP).

---

## 5. Lien quan da sua truoc do: HeuristicEvolver timeout/bottleneck

Ngoai feature VRP family, da patch loi treo experiment trong:

```text
HeurAgenix/src/pipeline/heuristic_evolver.py
```

Da sua:

- `LLMBudgetExceeded` khong bi nuot nua
- het LLM budget thi dung evolution som va tra ve best current pool
- validation noi bo co subprocess timeout mac dinh 15s
- bottleneck parser dung `split(";", maxsplit=2)`
- `get_improvement()` an toan voi `None`
- refinement giu `reminder=True`

---

## 6. Danh gia & San sang cho Experiment

1. **Data & Reference Integrity**: Toan bo dataset n50 va reference PyVRP da verified 100% khong co semantic mismatch hay stale cache.
2. **Heuristics Compatibility**: Toan bo basic heuristics & seed pool da ho tro ca 4 variants (open/closed route, time windows).
3. **Execution Pipeline**: CLI commands (`generate-data`, `generate-references`, `verify-references`, `run-stream`, `validate-config`) hoat dong tron tru tren moi truong Windows PowerShell / uv.

---

## 7. Next Steps

1. **Chay LLM Pilot**: Chay experiment voi `--generator heuragenix` tren forward va reverse stream voi budget nho de danh gia kha nang adaptive heuristic cua LLM.
2. **Full Continual Learning Campaign**: Chay full stream experiments voi nhieu seeds va so sanh cac continual transfer strategies (cold start vs carryover vs heuristic evolver).

---

## 8. Trang thai tom tat

```text
Core constraint profile:             done
Central route metrics:               done
Central validators:                  done
CVRP env refactor:                   done
Problem state variant metadata:      done
Prompt updates:                      done
Paired data generation:              done
Feasible TW generation:              done
Task registry:                       done
Forward/reverse stream configs:      done
Suite config:                        done
Stream gray-code validation:         done
PyVRP variant adapter:               done
Reference semantic verification:     done
Reference cache invalidation:        done
Evaluator stale-reference guard:     done
Transfer diagnostics integration:    done
CLI validate-config path:            done
Variant-aware seed insertion costs:  done
TW-aware seed insertion filtering:   done
Legacy heuristic audit:              done
Full real data generation:           done (smoke, validation, test)
PyVRP reference generation:          done (smoke, validation, test)
Reference verification:              done (100% passed)
Baseline forward smoke stream:       done
Baseline reverse smoke stream:       done
LLM pilot / experiments:             ready
```

Ket luan hien tai:

```text
Toan bo ha tang, data, references, heuristics va pipeline cua VRP Constraint Family da hoan tat 100% va san sang cho cac dot experiment thuc te.
```
