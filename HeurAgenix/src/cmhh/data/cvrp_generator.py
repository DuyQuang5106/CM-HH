from __future__ import annotations

import hashlib
import random
from pathlib import Path

from cmhh.config import ExperimentConfig
from cmhh.data.manifest import sha256_file, write_json_atomic
from cmhh.tasks import TaskSpec


def generate_cvrp_instance(
    node_count: int,
    seed: int,
    coordinate_min: int,
    coordinate_max: int,
) -> tuple[list[tuple[int, int]], list[int], int, int]:
    """Generates random CVRP instance: (coordinates, demands, capacity, vehicle_num)."""
    rng = random.Random(seed)
    coordinates: set[tuple[int, int]] = set()
    span = coordinate_max - coordinate_min + 1
    if span * span < node_count:
        raise ValueError("Coordinate range is too small for unique CVRP nodes")
    while len(coordinates) < node_count:
        coordinates.add((
            rng.randint(coordinate_min, coordinate_max),
            rng.randint(coordinate_min, coordinate_max),
        ))
    coords_list = list(coordinates)

    # Depot (node 1, index 0) has demand 0
    demands = [0]
    for _ in range(1, node_count):
        demands.append(rng.randint(1, 10))

    total_demand = sum(demands)
    # Estimate vehicle capacity and vehicle count
    vehicle_num = max(2, max(3, node_count // 5))
    capacity = max(15, int((total_demand / vehicle_num) * 1.5))

    return coords_list, demands, capacity, vehicle_num


def write_cvrplib(
    path: str | Path,
    name: str,
    coordinates: list[tuple[int, int]],
    demands: list[int],
    capacity: int,
    vehicle_num: int,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    full_name = f"{name}-k{vehicle_num}"
    file_path = target.parent / f"{full_name}.vrp"

    with file_path.open("w", encoding="utf-8") as fp:
        fp.write(f"NAME: {full_name}\n")
        fp.write("TYPE: CVRP\n")
        fp.write(f"DIMENSION: {len(coordinates)}\n")
        fp.write("EDGE_WEIGHT_TYPE: EUC_2D\n")
        fp.write(f"CAPACITY: {capacity}\n")
        fp.write("NODE_COORD_SECTION\n")
        for index, (x, y) in enumerate(coordinates, start=1):
            fp.write(f"{index} {x} {y}\n")
        fp.write("DEMAND_SECTION\n")
        for index, demand in enumerate(demands, start=1):
            fp.write(f"{index} {demand}\n")
        fp.write("DEPOT_SECTION\n")
        fp.write("1\n")
        fp.write("-1\n")
        fp.write("EOF\n")
    return file_path


def generate_cvrp_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
    split_dirs = {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }
    node_count = int(task.metadata.get("nodes", task.metadata.get("customers", 20)))
    for split_name, directory in split_dirs.items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for index in range(experiment.data.splits[split_name]):
            instance_seed = _instance_seed(seed, task.task_id, split_name, index)
            coordinates, demands, capacity, vehicle_num = generate_cvrp_instance(
                node_count,
                instance_seed,
                experiment.data.coordinate_min,
                experiment.data.coordinate_max,
            )
            name = f"{task.task_id}_{split_name}_{index:03d}"
            write_cvrplib(directory / f"{name}.vrp", name, coordinates, demands, capacity, vehicle_num)


def _instance_seed(seed: int, task_id: str, split_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{split_name}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)
