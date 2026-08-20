from __future__ import annotations

import hashlib
import random
from pathlib import Path

from cmhh.config import ExperimentConfig
from cmhh.tasks import TaskSpec


def generate_jssp_instance(
    job_count: int,
    machine_count: int,
    seed: int,
) -> tuple[list[list[int]], list[list[int]]]:
    """Generates random JSSP instance: (job_operation_sequence, job_operation_time)."""
    rng = random.Random(seed)
    job_operation_sequence = []
    job_operation_time = []
    for _ in range(job_count):
        machines = list(range(machine_count))
        rng.shuffle(machines)
        times = [rng.randint(1, 99) for _ in range(machine_count)]
        job_operation_sequence.append(machines)
        job_operation_time.append(times)
    return job_operation_sequence, job_operation_time


def write_jssp(
    path: str | Path,
    job_operation_sequence: list[list[int]],
    job_operation_time: list[list[int]],
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    job_count = len(job_operation_sequence)
    machine_count = len(job_operation_sequence[0])

    with target.open("w", encoding="utf-8") as fp:
        fp.write(f"{job_count} {machine_count}\n")
        for job_idx in range(job_count):
            pairs = []
            for mach, dur in zip(job_operation_sequence[job_idx], job_operation_time[job_idx]):
                pairs.extend([str(mach), str(dur)])
            fp.write(" ".join(pairs) + "\n")
    return target


def generate_jssp_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
    split_dirs = {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }
    job_count = int(task.metadata.get("jobs", _count_from_size_tier(task.size_tier)))
    machine_count = int(task.metadata.get("machines", 5))

    for split_name, directory in split_dirs.items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for index in range(experiment.data.splits[split_name]):
            instance_seed = _instance_seed(seed, task.task_id, split_name, index)
            seq, times = generate_jssp_instance(job_count, machine_count, instance_seed)
            name = f"{task.task_id}_{split_name}_{index:03d}.txt"
            write_jssp(directory / name, seq, times)


def _instance_seed(seed: int, task_id: str, split_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{split_name}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _count_from_size_tier(size_tier: str) -> int:
    digits = "".join(char for char in size_tier if char.isdigit())
    return int(digits) if digits else 20
