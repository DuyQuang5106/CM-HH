from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from cmhh.data.manifest import sha256_file
from cmhh.references.base import ReferenceResult, ReferenceSolverAdapter, SolverConfig


class ORToolsCPSATSolverAdapter(ReferenceSolverAdapter):
    @property
    def problem_name(self) -> str:
        return "jssp"

    def solve(self, instance_path: Path, config: SolverConfig) -> ReferenceResult:
        try:
            import ortools
            from ortools.sat.python import cp_model
        except ImportError as exc:
            raise ImportError(
                "OR-Tools is required for JSSP reference generation. "
                "Create the conda env from `environment.yml` or run "
                "`python -m pip install ortools` in the active environment."
            ) from exc

        started = time.perf_counter()
        instance = Path(instance_path).resolve()
        checksum = sha256_file(instance)

        with instance.open("r", encoding="utf-8") as fp:
            lines = [line.strip() for line in fp if line.strip()]

        parts = lines[0].split()
        job_count = int(parts[0])
        machine_count = int(parts[1])

        job_operation_sequence: list[list[int]] = []
        job_operation_time: list[list[int]] = []
        for line in lines[1: job_count + 1]:
            data = [int(v) for v in line.split()]
            job_operation_sequence.append([data[i] for i in range(0, len(data), 2)])
            job_operation_time.append([data[i + 1] for i in range(0, len(data), 2)])

        # Build CP-SAT Model
        model = cp_model.CpModel()
        horizon = sum(sum(durations) for durations in job_operation_time)

        all_tasks: dict[tuple[int, int], tuple[Any, Any, Any]] = {}
        machine_to_intervals: dict[int, list[Any]] = {m: [] for m in range(machine_count)}

        for j in range(job_count):
            num_ops = len(job_operation_sequence[j])
            for op in range(num_ops):
                m = job_operation_sequence[j][op]
                d = job_operation_time[j][op]
                suffix = f"_{j}_{op}"
                start_var = model.NewIntVar(0, horizon, f"start{suffix}")
                end_var = model.NewIntVar(0, horizon, f"end{suffix}")
                interval_var = model.NewIntervalVar(start_var, d, end_var, f"interval{suffix}")
                all_tasks[j, op] = (start_var, end_var, interval_var)
                machine_to_intervals[m].append(interval_var)

        # Precedence constraints within each job
        for j in range(job_count):
            num_ops = len(job_operation_sequence[j])
            for op in range(num_ops - 1):
                model.Add(all_tasks[j, op + 1][0] >= all_tasks[j, op][1])

        # Disjunctive machine constraints (no overlap)
        for m in range(machine_count):
            model.AddNoOverlap(machine_to_intervals[m])

        # Makespan objective: minimize max end time over all jobs
        makespan = model.NewIntVar(0, horizon, "makespan")
        last_op_ends = [
            all_tasks[j, len(job_operation_sequence[j]) - 1][1]
            for j in range(job_count)
        ]
        model.AddMaxEquality(makespan, last_op_ends)
        model.Minimize(makespan)

        # Solver configuration
        solver = cp_model.CpSolver()
        time_limit = max(0.1, float(config.timeout_seconds))
        workers = max(1, int(config.num_workers if config.num_workers is not None else 1))
        seed = int(config.seed if config.seed is not None else 1)

        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_workers = workers
        solver.parameters.random_seed = seed

        status = solver.Solve(model)
        runtime = time.perf_counter() - started

        try:
            import importlib.metadata
            ortools_version = importlib.metadata.version("ortools")
        except Exception:
            ortools_version = getattr(ortools, "__version__", "unknown")

        best_bound = None
        try:
            best_bound = float(solver.BestObjectiveBound())
        except Exception:
            pass

        wall_time = runtime
        try:
            wall_time = float(solver.WallTime())
        except Exception:
            pass

        solver_status_name = "UNKNOWN"
        try:
            solver_status_name = solver.StatusName(status)
        except Exception:
            pass

        if status == cp_model.OPTIMAL:
            obj_val = float(solver.ObjectiveValue())
            return ReferenceResult(
                instance_id=instance.stem,
                objective=obj_val,
                status="optimal",
                solver="ortools_cpsat",
                instance_sha256=checksum,
                runtime_seconds=runtime,
                proven_optimal=True,
                best_bound=best_bound,
                metadata={
                    "solver": "ortools_cpsat",
                    "solver_version": ortools_version,
                    "solver_status": solver_status_name,
                    "best_objective_bound": best_bound,
                    "wall_time": wall_time,
                    "seed": seed,
                    "num_workers": workers,
                    "time_limit_seconds": time_limit,
                    "jobs": job_count,
                    "machines": machine_count,
                },
            )
        elif status == cp_model.FEASIBLE:
            obj_val = float(solver.ObjectiveValue())
            return ReferenceResult(
                instance_id=instance.stem,
                objective=obj_val,
                status="best_known",
                solver="ortools_cpsat",
                instance_sha256=checksum,
                runtime_seconds=runtime,
                proven_optimal=False,
                best_bound=best_bound,
                metadata={
                    "solver": "ortools_cpsat",
                    "solver_version": ortools_version,
                    "solver_status": solver_status_name,
                    "best_objective_bound": best_bound,
                    "wall_time": wall_time,
                    "seed": seed,
                    "num_workers": workers,
                    "time_limit_seconds": time_limit,
                    "jobs": job_count,
                    "machines": machine_count,
                },
            )
        else:
            return ReferenceResult(
                instance_id=instance.stem,
                objective=None,
                status="failed",
                solver="ortools_cpsat",
                instance_sha256=checksum,
                runtime_seconds=runtime,
                proven_optimal=False,
                best_bound=best_bound,
                metadata={
                    "solver": "ortools_cpsat",
                    "solver_version": ortools_version,
                    "solver_status": solver_status_name,
                    "best_objective_bound": best_bound,
                    "wall_time": wall_time,
                    "seed": seed,
                    "num_workers": workers,
                    "time_limit_seconds": time_limit,
                    "jobs": job_count,
                    "machines": machine_count,
                    "error": f"CP-SAT solver returned non-feasible status: {solver_status_name}",
                },
            )
