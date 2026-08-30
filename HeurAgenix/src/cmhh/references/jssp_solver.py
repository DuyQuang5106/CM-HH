from __future__ import annotations

import time
from pathlib import Path

from cmhh.data.manifest import sha256_file
from cmhh.references.base import ReferenceResult, ReferenceSolverAdapter, SolverConfig


from cmhh.references.ortools_cpsat_solver import ORToolsCPSATSolverAdapter


class JSSPSolverAdapter(ReferenceSolverAdapter):
    def __init__(self) -> None:
        self._cpsat_adapter = ORToolsCPSATSolverAdapter()

    @property
    def problem_name(self) -> str:
        return "jssp"

    def solve(self, instance_path: Path, config: SolverConfig) -> ReferenceResult:
        try:
            return self._cpsat_adapter.solve(instance_path, config)
        except ImportError:
            started = time.perf_counter()
            checksum = sha256_file(instance_path)

            with instance_path.open("r", encoding="utf-8") as fp:
                lines = [line.strip() for line in fp if line.strip()]

            parts = lines[0].split()
            job_count = int(parts[0])
            machine_count = int(parts[1])

            job_operation_sequence = []
            job_operation_time = []
            for line in lines[1: job_count + 1]:
                data = [int(v) for v in line.split()]
                job_operation_sequence.append([data[i] for i in range(0, len(data), 2)])
                job_operation_time.append([data[i + 1] for i in range(0, len(data), 2)])

            best_makespan = _solve_jssp_active_schedule_search(
                job_count=job_count,
                machine_count=machine_count,
                job_operation_sequence=job_operation_sequence,
                job_operation_time=job_operation_time,
                timeout_seconds=config.timeout_seconds,
            )

            runtime = time.perf_counter() - started
            return ReferenceResult(
                instance_id=instance_path.stem,
                objective=float(best_makespan),
                status="best_known",
                solver="jssp_active_schedule_search",
                instance_sha256=checksum,
                runtime_seconds=runtime,
                proven_optimal=False,
                metadata={
                    "jobs": job_count,
                    "machines": machine_count,
                },
            )


def _solve_jssp_active_schedule_search(
    job_count: int,
    machine_count: int,
    job_operation_sequence: list[list[int]],
    job_operation_time: list[list[int]],
    timeout_seconds: float = 30.0,
) -> float:
    # Multiple dispatch priority rules for finding best known makespan
    priority_rules = ["spt", "lpt", "mwr", "lwr", "fifo"]
    best_makespan = float("inf")

    total_work = [sum(job_operation_time[j]) for j in range(job_count)]

    for rule in priority_rules:
        makespan = _simulate_schedule(
            job_count,
            machine_count,
            job_operation_sequence,
            job_operation_time,
            total_work,
            rule,
        )
        if makespan < best_makespan:
            best_makespan = makespan

    return best_makespan


def _simulate_schedule(
    job_count: int,
    machine_count: int,
    job_operation_sequence: list[list[int]],
    job_operation_time: list[list[int]],
    total_work: list[int],
    rule: str,
) -> float:
    job_op_idx = [0] * job_count
    job_next_available = [0.0] * job_count
    machine_next_available = [0.0] * machine_count
    total_ops = job_count * machine_count

    remaining_work = list(total_work)

    for _ in range(total_ops):
        # Eligible operations (next operation for each unfinished job)
        eligible = []
        for j in range(job_count):
            op = job_op_idx[j]
            if op < machine_count:
                m = job_operation_sequence[j][op]
                dur = job_operation_time[j][op]
                earliest_start = max(job_next_available[j], machine_next_available[m])
                eligible.append((j, op, m, dur, earliest_start))

        if not eligible:
            break

        # Select candidate based on priority rule
        if rule == "spt":
            eligible.sort(key=lambda item: (item[4], item[3]))
        elif rule == "lpt":
            eligible.sort(key=lambda item: (item[4], -item[3]))
        elif rule == "mwr":
            eligible.sort(key=lambda item: (item[4], -remaining_work[item[0]]))
        elif rule == "lwr":
            eligible.sort(key=lambda item: (item[4], remaining_work[item[0]]))
        else:
            eligible.sort(key=lambda item: item[4])

        selected_job, selected_op, selected_machine, dur, start_time = eligible[0]
        end_time = start_time + dur
        job_next_available[selected_job] = end_time
        machine_next_available[selected_machine] = end_time
        job_op_idx[selected_job] += 1
        remaining_work[selected_job] -= dur

    return max(machine_next_available)
