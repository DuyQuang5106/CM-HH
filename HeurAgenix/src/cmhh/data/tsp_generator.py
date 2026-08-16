from __future__ import annotations

import hashlib
import random
from pathlib import Path

from cmhh.config import ExperimentConfig
from cmhh.data.manifest import sha256_file, write_json_atomic
from cmhh.tasks import TaskRegistry, TaskSpec


def generate_tsp_instance(
    node_count: int,
    seed: int,
    coordinate_min: int,
    coordinate_max: int,
) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    coordinates: set[tuple[int, int]] = set()
    span = coordinate_max - coordinate_min + 1
    if span * span < node_count:
        raise ValueError("Coordinate range is too small for unique TSP nodes")
    while len(coordinates) < node_count:
        coordinates.add((
            rng.randint(coordinate_min, coordinate_max),
            rng.randint(coordinate_min, coordinate_max),
        ))
    return list(coordinates)


def write_tsplib(path: str | Path, name: str, coordinates: list[tuple[int, int]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fp:
        fp.write(f"NAME: {name}\n")
        fp.write("TYPE: TSP\n")
        fp.write(f"DIMENSION: {len(coordinates)}\n")
        fp.write("EDGE_WEIGHT_TYPE: EUC_2D\n")
        fp.write("NODE_COORD_SECTION\n")
        for index, (x, y) in enumerate(coordinates, start=1):
            fp.write(f"{index} {x} {y}\n")
        fp.write("EOF\n")


def generate_tsp_datasets(
    registry: TaskRegistry,
    task_ids: tuple[str, ...],
    experiment: ExperimentConfig,
    seed: int,
) -> list[Path]:
    manifests = []
    for task_id in task_ids:
        task = registry.get(task_id)
        if task.problem != "tsp":
            continue
        _generate_task_splits(task, experiment, seed)
        manifest = _write_task_manifest(task, experiment, seed)
        manifests.append(manifest)
    return manifests


def _generate_task_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
    split_dirs = {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }
    node_count = int(task.metadata.get("nodes", _nodes_from_size_tier(task.size_tier)))
    for split_name, directory in split_dirs.items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for index in range(experiment.data.splits[split_name]):
            instance_seed = _instance_seed(seed, task.task_id, split_name, index)
            coordinates = generate_tsp_instance(
                node_count,
                instance_seed,
                experiment.data.coordinate_min,
                experiment.data.coordinate_max,
            )
            name = f"{task.task_id}_{split_name}_{index:03d}"
            write_tsplib(directory / f"{name}.tsp", name, coordinates)


def _write_task_manifest(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> Path:
    base = task.splits.train.parent
    records = {}
    for split_name, directory in {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }.items():
        if directory is None:
            continue
        records[split_name] = {
            path.name: sha256_file(path)
            for path in sorted(directory.glob("*.tsp"))
        }
    manifest_path = base / "manifest.json"
    write_json_atomic(manifest_path, {
        "task_id": task.task_id,
        "problem": task.problem,
        "size_tier": task.size_tier,
        "distribution": task.distribution,
        "data_seed": seed,
        "coordinate_min": experiment.data.coordinate_min,
        "coordinate_max": experiment.data.coordinate_max,
        "splits": records,
    })
    return manifest_path


def _instance_seed(seed: int, task_id: str, split_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{split_name}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _nodes_from_size_tier(size_tier: str) -> int:
    digits = "".join(char for char in size_tier if char.isdigit())
    if not digits:
        raise ValueError(f"Cannot infer node count from size tier {size_tier}")
    return int(digits)
