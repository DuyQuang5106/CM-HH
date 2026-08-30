from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cmhh.data.manifest import sha256_file, write_json_atomic
from cmhh.data.references import ReferenceRecord, load_reference_set, write_reference_set
from cmhh.evaluation.problem_adapter import ProblemRegistry
from cmhh.references.base import ReferenceResult, SolverConfig
from cmhh.references.concorde import ConcordeConfig, SolverFailure
from cmhh.references.registry import ReferenceSolverRegistry
from cmhh.tasks import TaskSpec


def generate_task_references(
    task: TaskSpec,
    split: str,
    config: Any | None = None,
    pilot_count: int | None = None,
) -> tuple[list[ReferenceRecord], list[SolverFailure]]:
    split_path = getattr(task.splits, split)
    if split_path is None or not split_path.exists():
        raise FileNotFoundError(f"Missing {split} split for {task.task_id}")

    adapter = ProblemRegistry.get(task.problem)
    instances = adapter.discover_instances(split_path)
    if pilot_count is not None:
        instances = instances[:pilot_count]

    reference_path = task.reference.path
    if reference_path is None:
        raise ValueError(f"{task.task_id} has no reference output path")

    failures: list[SolverFailure] = []
    solver, solver_config = _resolve_solver(task, config)

    existing: dict[str, ReferenceRecord] = {}
    if reference_path.exists():
        existing = {record.instance_id: record for record in load_reference_set(reference_path).records}

    records = dict(existing)
    pending = []
    for instance in instances:
        cached = records.get(instance.stem)
        if cached and _cached_reference_is_current(cached, instance, solver_config):
            continue
        records.pop(instance.stem, None)
        pending.append(instance)

    with ThreadPoolExecutor(max_workers=solver_config.max_workers) as executor:
        futures = {
            executor.submit(_solve_single_instance, solver, instance, solver_config): instance
            for instance in pending
        }
        for future in as_completed(futures):
            instance = futures[future]
            try:
                outcome = future.result()
                if isinstance(outcome, ReferenceRecord):
                    records[outcome.instance_id] = outcome
                else:
                    failures.append(outcome)
            except Exception as exc:
                failures.append(SolverFailure(
                    instance_id=instance.stem,
                    status="crash",
                    error=traceback.format_exc(),
                    runtime_seconds=0.0,
                ))
            write_reference_set(reference_path, task.task_id, list(records.values()))

    if not pending and not reference_path.exists():
        write_reference_set(reference_path, task.task_id, [])
    failure_path = reference_path.parent / f"{split}_solver_failures.json"
    write_json_atomic(failure_path, {
        "task_id": task.task_id,
        "split": split,
        "failures": [asdict(item) for item in sorted(failures, key=lambda item: item.instance_id)],
    })
    return list(records.values()), failures


def _resolve_solver(task: TaskSpec, config: Any | None):
    concorde_cfg = config if isinstance(config, ConcordeConfig) else None
    solver = ReferenceSolverRegistry.get_solver(task.problem, concorde_config=concorde_cfg)

    if isinstance(config, SolverConfig):
        solver_config = config
    elif isinstance(config, ConcordeConfig):
        solver_config = SolverConfig(
            max_workers=config.max_workers,
            solver_name="concorde",
            timeout_seconds=config.timeouts.get(task.size_tier, 300.0) if task.size_tier in config.timeouts else 300.0,
        )
    elif isinstance(config, dict):
        timeouts = config.get("timeouts", {})
        timeout = float(timeouts.get(task.size_tier, config.get("time_limit_seconds", 300.0)))
        solver_config = SolverConfig(
            timeout_seconds=timeout,
            max_workers=int(config.get("max_workers", 4)),
            solver_name=str(config.get("name", "default")).lower(),
            seed=int(config.get("seed", 1)),
            num_workers=int(config.get("num_workers", 1)),
            options=config,
        )
    else:
        solver_config = SolverConfig(
            max_workers=4,
            timeout_seconds=300.0,
        )
    return solver, solver_config


def _cached_reference_is_current(
    cached: ReferenceRecord,
    instance: Path,
    solver_config: SolverConfig,
) -> bool:
    if cached.instance_sha256 != sha256_file(instance):
        return False
    if solver_config.solver_name != "default" and cached.solver != solver_config.solver_name:
        return False
    return not cached.tour_path or Path(cached.tour_path).exists()


def _solve_single_instance(solver, instance: Path, config: SolverConfig) -> ReferenceRecord | SolverFailure:
    try:
        res: ReferenceResult = solver.solve(instance, config)
        if res.status == "failed" or res.objective is None:
            return SolverFailure(
                instance_id=instance.stem,
                status="failed",
                error=str(res.metadata.get("error", "Solver failed")),
                runtime_seconds=res.runtime_seconds,
            )
        return res.to_reference_record()
    except Exception as exc:
        return SolverFailure(
            instance_id=instance.stem,
            status="error",
            error=str(exc),
            runtime_seconds=0.0,
        )



