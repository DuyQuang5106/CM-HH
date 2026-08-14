from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

from cmhh.data.manifest import sha256_file, write_json_atomic
from cmhh.data.references import ReferenceRecord, load_reference_set, write_reference_set
from cmhh.references.concorde import ConcordeConfig, SolverFailure, solve_instance
from cmhh.tasks import TaskSpec


def generate_task_references(
    task: TaskSpec,
    split: str,
    config: ConcordeConfig,
    pilot_count: int | None = None,
) -> tuple[list[ReferenceRecord], list[SolverFailure]]:
    split_path = getattr(task.splits, split)
    if split_path is None or not split_path.exists():
        raise FileNotFoundError(f"Missing {split} split for {task.task_id}")
    instances = sorted(split_path.glob("*.tsp"))
    if pilot_count is not None:
        instances = instances[:pilot_count]

    reference_path = task.reference.path
    if reference_path is None:
        raise ValueError(f"{task.task_id} has no reference output path")
    existing: dict[str, ReferenceRecord] = {}
    if reference_path.exists():
        existing = {record.instance_id: record for record in load_reference_set(reference_path).records}

    records = dict(existing)
    pending = []
    for instance in instances:
        cached = records.get(instance.stem)
        if cached and cached.instance_sha256 == sha256_file(instance) and (
            not cached.tour_path or Path(cached.tour_path).exists()
        ):
            continue
        pending.append(instance)

    failures: list[SolverFailure] = []
    tour_dir = reference_path.parent / "tours"
    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        futures = {
            executor.submit(
                solve_instance,
                instance,
                task.size_tier,
                config,
                tour_dir / f"{instance.stem}.tour",
            ): instance
            for instance in pending
        }
        for future in as_completed(futures):
            outcome = future.result()
            if isinstance(outcome, ReferenceRecord):
                records[outcome.instance_id] = outcome
            else:
                failures.append(outcome)
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

