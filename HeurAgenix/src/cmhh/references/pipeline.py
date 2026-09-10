from __future__ import annotations

import math
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cmhh.data.manifest import load_json, sha256_file, write_json_atomic
from cmhh.data.references import ReferenceRecord, load_reference_set, write_reference_set
from cmhh.evaluation.problem_adapter import ProblemRegistry
from cmhh.references.base import ReferenceResult, SolverConfig
from cmhh.references.concorde import ConcordeConfig, SolverFailure
from cmhh.references.registry import ReferenceSolverRegistry
from cmhh.tasks import TaskSpec
from src.problems.cvrp.variant import profile_from_config


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
        if cached and _cached_reference_is_current(cached, instance, solver_config, task):
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
    task: TaskSpec | None = None,
) -> bool:
    if cached.instance_sha256 != sha256_file(instance):
        return False
    if solver_config.solver_name != "default" and cached.solver != solver_config.solver_name:
        return False
    if cached.tour_path and not Path(cached.tour_path).exists():
        return False
    if _is_vrp_constraint_family_task(task):
        return _cached_vrp_reference_metadata_is_current(cached, instance, task)
    return True


def _is_vrp_constraint_family_task(task: TaskSpec | None) -> bool:
    if task is None or task.problem != "cvrp":
        return False
    return task.metadata.get("constraint_family") == "vrp" or bool(task.metadata.get("vrp_variant"))


def _cached_vrp_reference_metadata_is_current(
    cached: ReferenceRecord,
    instance: Path,
    task: TaskSpec | None,
) -> bool:
    instance_meta = _load_instance_meta(instance)
    expected_variant = str(
        instance_meta.get("variant")
        or task.metadata.get("vrp_variant")
        or task.metadata.get("variant")
        or "cvrp"
    ).lower()
    expected_profile = profile_from_config(
        instance_meta.get("constraints")
        or instance_meta.get("variant")
        or task.metadata.get("constraints")
        or task.metadata.get("vrp_variant")
        or "cvrp"
    )

    metadata = cached.metadata if isinstance(cached.metadata, dict) else {}
    if str(metadata.get("variant", "")).lower() != expected_variant:
        return False
    if metadata.get("constraints") != expected_profile.to_dict():
        return False
    if metadata.get("internal_validation_feasible") is not True:
        return False

    try:
        internal_objective = float(metadata.get("internal_objective"))
    except (TypeError, ValueError):
        return False
    if not math.isfinite(internal_objective):
        return False

    tolerance = 1e-6 * max(1.0, abs(cached.objective))
    return abs(internal_objective - cached.objective) <= tolerance


def _load_instance_meta(instance: Path) -> dict:
    meta_path = instance.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    meta = load_json(meta_path)
    return meta if isinstance(meta, dict) else {}


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



