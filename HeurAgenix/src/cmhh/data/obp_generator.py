from __future__ import annotations

import hashlib
import random
from pathlib import Path

from cmhh.config import ExperimentConfig
from cmhh.tasks import TaskSpec


def generate_obp_instance(
    item_count: int,
    bin_capacity: int,
    seed: int,
) -> tuple[int, list[int]]:
    """Generates random OBP instance: (bin_capacity, item_sizes)."""
    rng = random.Random(seed)
    item_sizes = [rng.randint(1, bin_capacity) for _ in range(item_count)]
    return bin_capacity, item_sizes


def write_obp(
    path: str | Path,
    bin_capacity: int,
    item_sizes: list[int],
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", encoding="utf-8") as fp:
        fp.write(f"{bin_capacity}\n")
        fp.write(f"{len(item_sizes)}\n")
        for size in item_sizes:
            fp.write(f"{size}\n")
    return target


def generate_obp_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
    split_dirs = {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }
    item_count = int(task.metadata.get("items", _count_from_size_tier(task.size_tier)))
    bin_capacity = int(task.metadata.get("bin_capacity", 100))

    for split_name, directory in split_dirs.items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for index in range(experiment.data.splits[split_name]):
            instance_seed = _instance_seed(seed, task.task_id, split_name, index)
            cap, sizes = generate_obp_instance(item_count, bin_capacity, instance_seed)
            name = f"{task.task_id}_{split_name}_{index:03d}.txt"
            write_obp(directory / name, cap, sizes)


def _instance_seed(seed: int, task_id: str, split_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{split_name}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _count_from_size_tier(size_tier: str) -> int:
    digits = "".join(char for char in size_tier if char.isdigit())
    return int(digits) if digits else 20
