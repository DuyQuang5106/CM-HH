from __future__ import annotations

import hashlib
import random
from pathlib import Path

from cmhh.config import ExperimentConfig
from cmhh.tasks import TaskSpec
try:
    from problems.dposp.generate_data import build_data
except ModuleNotFoundError:
    from src.problems.dposp.generate_data import build_data


def generate_dposp_instance(
    production_line_num: int,
    product_num: int,
    order_num: int,
    seed: int,
    output_dir: Path,
) -> None:
    random.seed(seed)
    production_distribution = {1: 0.5, 2: 0.25, 3: 0.25}
    production_rate_distribution = {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}
    transition_distribution = {-1: 0.25, 0: 0.25, 1: 0.25, 2: 0.25}
    order_quantity_rate_distribution = {1: 0.5, 2: 0.5}
    order_deadline_distribution = {12: 0.5, 24: 0.5}

    build_data(
        production_line_num=production_line_num,
        product_num=product_num,
        order_num=order_num,
        production_distribution=production_distribution,
        production_rate_distribution=production_rate_distribution,
        transition_distribution=transition_distribution,
        order_quantity_rate_distribution=order_quantity_rate_distribution,
        order_deadline_distribution=order_deadline_distribution,
        output_dir=str(output_dir),
    )


def generate_dposp_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
    split_dirs = {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }
    order_num = int(task.metadata.get("orders", _count_from_size_tier(task.size_tier)))
    production_line_num = int(task.metadata.get("lines", 5))
    product_num = int(task.metadata.get("products", 10))

    for split_name, directory in split_dirs.items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for index in range(experiment.data.splits[split_name]):
            instance_seed = _instance_seed(seed, task.task_id, split_name, index)
            instance_dir = directory / f"{task.task_id}_{split_name}_{index:03d}"
            generate_dposp_instance(
                production_line_num,
                product_num,
                order_num,
                instance_seed,
                instance_dir,
            )


def _instance_seed(seed: int, task_id: str, split_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{split_name}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _count_from_size_tier(size_tier: str) -> int:
    digits = "".join(char for char in size_tier if char.isdigit())
    return int(digits) if digits else 20
