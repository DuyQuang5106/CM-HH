from __future__ import annotations

import hashlib
import random
from pathlib import Path

from cmhh.config import ExperimentConfig
from cmhh.tasks import TaskSpec


def generate_mkp_instance(
    item_count: int,
    resource_count: int,
    seed: int,
) -> tuple[list[float], list[list[float]], list[float]]:
    """Generates random MKP instance: (profits, weight_matrix, capacities)."""
    rng = random.Random(seed)
    profits = [round(rng.uniform(10.0, 100.0), 2) for _ in range(item_count)]
    weight_matrix = []
    capacities = []
    for _ in range(resource_count):
        weights = [round(rng.uniform(1.0, 50.0), 2) for _ in range(item_count)]
        weight_matrix.append(weights)
        capacity = round(sum(weights) * 0.5, 2)
        capacities.append(capacity)

    return profits, weight_matrix, capacities


def write_mkp(
    path: str | Path,
    profits: list[float],
    weight_matrix: list[list[float]],
    capacities: list[float],
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    item_count = len(profits)
    resource_count = len(weight_matrix)

    with target.open("w", encoding="utf-8") as fp:
        fp.write(f"{item_count} {resource_count}\n")
        fp.write(" ".join(str(p) for p in profits) + "\n")
        for weights in weight_matrix:
            fp.write(" ".join(str(w) for w in weights) + "\n")
        fp.write(" ".join(str(c) for c in capacities) + "\n")
    return target


def generate_mkp_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
    split_dirs = {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }
    item_count = int(task.metadata.get("items", _count_from_size_tier(task.size_tier)))
    resource_count = int(task.metadata.get("resources", 5))

    for split_name, directory in split_dirs.items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for index in range(experiment.data.splits[split_name]):
            instance_seed = _instance_seed(seed, task.task_id, split_name, index)
            profits, weight_matrix, capacities = generate_mkp_instance(item_count, resource_count, instance_seed)
            name = f"{task.task_id}_{split_name}_{index:03d}.txt"
            write_mkp(directory / name, profits, weight_matrix, capacities)


def _instance_seed(seed: int, task_id: str, split_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{split_name}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _count_from_size_tier(size_tier: str) -> int:
    digits = "".join(char for char in size_tier if char.isdigit())
    return int(digits) if digits else 20
