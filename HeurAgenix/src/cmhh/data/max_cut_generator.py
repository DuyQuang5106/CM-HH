from __future__ import annotations

import hashlib
import random
from pathlib import Path

from cmhh.config import ExperimentConfig
from cmhh.tasks import TaskSpec


def generate_max_cut_instance(
    node_count: int,
    density: float,
    seed: int,
) -> tuple[int, list[tuple[int, int, int]]]:
    """Generates random MaxCut graph: (node_count, edges_with_weights)."""
    rng = random.Random(seed)
    edges = []
    for u in range(1, node_count + 1):
        for v in range(u + 1, node_count + 1):
            if rng.random() < density:
                weight = rng.randint(1, 20)
                edges.append((u, v, weight))

    if not edges:
        # Guarantee at least connected cycle
        for u in range(1, node_count):
            edges.append((u, u + 1, rng.randint(1, 20)))
        edges.append((node_count, 1, rng.randint(1, 20)))

    return node_count, edges


def write_max_cut(
    path: str | Path,
    node_count: int,
    edges: list[tuple[int, int, int]],
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", encoding="utf-8") as fp:
        fp.write(f"{node_count} {len(edges)}\n")
        for u, v, weight in edges:
            fp.write(f"{u} {v} {weight}\n")
    return target


def generate_max_cut_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
    split_dirs = {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }
    node_count = int(task.metadata.get("nodes", _count_from_size_tier(task.size_tier)))
    density = float(task.metadata.get("density", 0.5))

    for split_name, directory in split_dirs.items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for index in range(experiment.data.splits[split_name]):
            instance_seed = _instance_seed(seed, task.task_id, split_name, index)
            n, edges = generate_max_cut_instance(node_count, density, instance_seed)
            name = f"{task.task_id}_{split_name}_{index:03d}.txt"
            write_max_cut(directory / name, n, edges)


def _instance_seed(seed: int, task_id: str, split_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{split_name}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _count_from_size_tier(size_tier: str) -> int:
    digits = "".join(char for char in size_tier if char.isdigit())
    return int(digits) if digits else 20
