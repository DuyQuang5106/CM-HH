# Reference Solvers in CM-HH

This document specifies the architecture, installation, semantics, and execution of reference solvers across the combinatorial problems in CM-HH.

---

## 1. Reference Solver Matrix

| Problem | Solver | Installation | Reference Semantics |
| :--- | :--- | :--- | :--- |
| **TSP** (Traveling Salesperson) | **Concorde** | External binary | `optimal` (proven optimal) |
| **CVRP** (Capacitated Vehicle Routing) | **PyVRP** | Automatic via `uv sync` | `best_known` (state-of-the-art metaheuristic) |
| **JSSP** (Job Shop Scheduling) | **OR-Tools CP-SAT** | Automatic via `uv sync` | `optimal` (if proven optimal) / `best_known` (if feasible) |

### Scientific Semantics
- **`optimal`**: Strictly reserved for reference solutions with mathematical proof of optimality (e.g. Concorde branch-and-cut or CP-SAT with `OPTIMAL` status).
- **`best_known`**: High-quality feasible solutions without optimality proof (e.g. PyVRP HGS metaheuristic or CP-SAT `FEASIBLE` status).
- **`failed`**: Infeasible instance, solver timeout without feasible solution, or missing external dependency.

### Reporting Semantics

When reporting `relative_gap`, always name the reference type:

- **TSP gap** is measured against a Concorde `optimal` reference, so it can be reported as gap to proven optimum.
- **CVRP gap** is measured against a PyVRP `best_known` reference, so it should be reported as gap to best-known solver reference, not proven optimum.
- **JSSP gap** is measured against OR-Tools CP-SAT. If CP-SAT returns `OPTIMAL`, report gap to proven optimum; if it returns `FEASIBLE`, report gap to best-known reference.

The JSON schema is shared across all problems. The backend solver changes only the `solver`, `status`, `proven_optimal`-derived status, and metadata fields.

---

## 2. Quickstart for Fresh Clone

```bash
git clone <repo-url>
cd CM_HH

# 1. Install all dependencies (including PyVRP and OR-Tools)
uv sync

# 2. Check solver environment health
uv run python scripts/check_reference_solvers.py
```

Expected output:
```text
Reference solver check

[OK] PyVRP
     version: 0.11.3

[OK] OR-Tools CP-SAT
     version: 9.15.6755

[OK] Concorde
     path: C:\...\concorde.exe
```

---

## 3. Concorde Dependency Configuration (TSP)

Because Concorde is a native C binary, it is treated as an **explicit external dependency**. It is not committed to git.

### Resolution Hierarchy
When generating TSP references, CM-HH searches for the Concorde executable in the following order:
1. `executable:` field in `cmhh/configs/solvers/concorde.yaml`.
2. `CONCORDE_PATH` or `CONCORDE_EXECUTABLE` environment variable.
3. System `PATH` (`concorde` or `concorde.exe`).
4. Known local directory (`tools/concorde/concorde.exe`).

### Setting the Environment Variable
- **PowerShell (Windows)**:
  ```powershell
  $env:CONCORDE_PATH = "C:\tools\concorde\concorde.exe"
  ```
- **Bash / Zsh (Linux / macOS)**:
  ```bash
  export CONCORDE_PATH="/usr/local/bin/concorde"
  ```

If Concorde cannot be located, CM-HH emits an actionable error detailing all checked paths and remediation steps.

---

## 4. Reference Generation Commands

### Traveling Salesperson Problem (TSP)
```bash
uv run python -m cmhh generate-references \
  --stream cmhh/configs/streams/tsp_size_ascending.yaml \
  --split validation --split test \
  --solver-config cmhh/configs/solvers/concorde.yaml
```

### Capacitated Vehicle Routing Problem (CVRP)
```bash
uv run python -m cmhh generate-references \
  --stream cmhh/configs/streams/cvrp_size_ascending.yaml \
  --split validation --split test \
  --solver-config cmhh/configs/solvers/pyvrp.yaml
```

### Job Shop Scheduling Problem (JSSP)
```bash
uv run python -m cmhh generate-references \
  --stream cmhh/configs/streams/jssp_size_ascending.yaml \
  --split validation --split test \
  --solver-config cmhh/configs/solvers/ortools_cpsat.yaml
```

---

## 5. Solver Configurations

Solver configuration files are located under `cmhh/configs/solvers/`:

### `cmhh/configs/solvers/pyvrp.yaml`
```yaml
version: 1
solver:
  name: pyvrp
  problem: cvrp
  time_limit_seconds: 60
  seed: 1
  max_workers: 2
  timeouts:
    n20: 60
    n50: 120
    n100: 300
    n200: 600
```

### `cmhh/configs/solvers/ortools_cpsat.yaml`
```yaml
version: 1
solver:
  name: ortools_cpsat
  problem: jssp
  time_limit_seconds: 60
  num_workers: 1
  seed: 1
  max_workers: 2
  timeouts:
    j10_m5: 60
    j20_m5: 120
    j50_m10: 300
```

### `cmhh/configs/solvers/concorde.yaml`
```yaml
version: 1
solver:
  name: concorde
  problem: tsp
  executable: null
  command_prefix:
    - tools/concorde/concorde.exe
  arguments: [-x, -o, "{tour_path}", "{instance_path}"]
  max_workers: 2
  timeouts:
    n20: 60
    n50: 300
    n100: 900
    n200: 1800
```
