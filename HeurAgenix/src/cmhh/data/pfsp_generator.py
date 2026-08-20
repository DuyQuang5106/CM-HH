from __future__ import annotations

import hashlib
import random
from pathlib import Path

from cmhh.config import ExperimentConfig
from cmhh.tasks import TaskSpec


def generate_pfsp_instance(
    job_count: int,
    machine_count: int,
    seed: int,
) -> list[list[int]]:
    """Generates random PFSP instance matrix: processing_times[job][machine]."""
    rng = random.Random(seed)
    processing_times = []
    for _ in range(job_count):
        times = [rng.randint(1, 99) for _ in range(machine_count)]
        processing_times.append(times)
    return processing_times


def write_pfsp(
    path: str | Path,
    processing_times: list[list[int]],
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    job_count = len(processing_times)
    machine_count = len(processing_times[0])

    with target.open("w", encoding="utf-8") as fp:
        fp.write(f"{job_count} {machine_count}\n")
        for times in processing_times:
            fp.write(" ".join(str(t) for t in times) + "\n")
    return target


def generate_pfsp_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
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
            times = generate_pfsp_instance(job_count, machine_count, instance_seed)
            name = f"{task.task_id}_{split_name}_{index:03d}.txt"
            write_pfsp(directory / name, times)


def _instance_seed(seed: int, task_id: str, split_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{split_name}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _count_from_size_tier(size_tier: str) -> int:
    digits = "".join(char for char in size_tier if char.isdigit())
    return int(digits) if digits else 20
