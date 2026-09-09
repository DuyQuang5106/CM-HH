from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import Any

from cmhh.config import ExperimentConfig
from cmhh.data.manifest import sha256_file, write_json_atomic
from cmhh.tasks import TaskRegistry, TaskSpec


def generate_uniform_tsp(
    node_count: int,
    seed: int,
    coordinate_min: int,
    coordinate_max: int,
) -> list[tuple[int, int]]:
    """Generates uniform 2D TSP coordinates deterministically using a local RNG."""
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


def generate_clustered_tsp(
    node_count: int,
    seed: int,
    coordinate_min: int,
    coordinate_max: int,
    num_clusters: int = 3,
    sigma_fraction: float = 0.07,
    margin_fraction: float = 0.1,
) -> list[tuple[int, int]]:
    """Generates clustered 2D TSP coordinates deterministically using a local RNG.
    
    Samples k cluster centers with a margin, then samples nodes around centers
    using Gaussian noise with rejection resampling to prevent boundary artifacts.
    """
    rng = random.Random(seed)
    span = coordinate_max - coordinate_min
    if span <= 0:
        raise ValueError("coordinate_max must be strictly greater than coordinate_min")
    
    margin = int(span * margin_fraction)
    center_min = coordinate_min + margin
    center_max = coordinate_max - margin
    if center_max <= center_min:
        center_min, center_max = coordinate_min, coordinate_max

    # 1. Sample k cluster centers uniformly within the inner margin
    centers: list[tuple[int, int]] = []
    for _ in range(num_clusters):
        centers.append((
            rng.randint(center_min, center_max),
            rng.randint(center_min, center_max),
        ))

    sigma = max(1.0, span * sigma_fraction)
    coordinates: set[tuple[int, int]] = set()
    max_attempts = node_count * 1000
    attempts = 0

    while len(coordinates) < node_count and attempts < max_attempts:
        attempts += 1
        center = rng.choice(centers)
        x = int(round(rng.gauss(center[0], sigma)))
        y = int(round(rng.gauss(center[1], sigma)))
        # Rejection resampling: reject out-of-bounds or duplicate coordinates
        if coordinate_min <= x <= coordinate_max and coordinate_min <= y <= coordinate_max:
            coordinates.add((x, y))

    if len(coordinates) < node_count:
        # Fallback to uniform for any remaining nodes if extreme rejection occurs
        while len(coordinates) < node_count:
            coordinates.add((
                rng.randint(coordinate_min, coordinate_max),
                rng.randint(coordinate_min, coordinate_max),
            ))

    return list(coordinates)


def generate_tsp_instance(
    node_count: int,
    seed: int,
    coordinate_min: int,
    coordinate_max: int,
) -> list[tuple[int, int]]:
    """Backward-compatible wrapper for uniform TSP instance generation."""
    return generate_uniform_tsp(node_count, seed, coordinate_min, coordinate_max)


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
    effective_seed = int(task.metadata.get("dataset_seed", seed))
    dist_type = str(task.metadata.get("distribution_type", task.distribution)).lower()

    num_clusters = int(task.metadata.get("num_clusters", 3))
    sigma_fraction = float(task.metadata.get("sigma_fraction", 0.07))

    for split_name, directory in split_dirs.items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for index in range(experiment.data.splits[split_name]):
            instance_seed = _instance_seed(effective_seed, task.task_id, split_name, index)
            if "clustered" in dist_type:
                coordinates = generate_clustered_tsp(
                    node_count=node_count,
                    seed=instance_seed,
                    coordinate_min=experiment.data.coordinate_min,
                    coordinate_max=experiment.data.coordinate_max,
                    num_clusters=num_clusters,
                    sigma_fraction=sigma_fraction,
                )
            else:
                coordinates = generate_uniform_tsp(
                    node_count=node_count,
                    seed=instance_seed,
                    coordinate_min=experiment.data.coordinate_min,
                    coordinate_max=experiment.data.coordinate_max,
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
    effective_seed = int(task.metadata.get("dataset_seed", seed))
    write_json_atomic(manifest_path, {
        "task_id": task.task_id,
        "problem": task.problem,
        "size_tier": task.size_tier,
        "distribution": task.distribution,
        "dataset_seed": effective_seed,
        "data_seed": effective_seed,
        "coordinate_min": experiment.data.coordinate_min,
        "coordinate_max": experiment.data.coordinate_max,
        "metadata": task.metadata,
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
