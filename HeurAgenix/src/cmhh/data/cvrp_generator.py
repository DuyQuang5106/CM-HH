from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmhh.config import ExperimentConfig
from cmhh.tasks import TaskSpec


def _coord_hash(coordinates: list[tuple[int, int]]) -> str:
    raw = json.dumps(coordinates, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _demand_hash(demands: list[int]) -> str:
    raw = json.dumps(demands, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class CVRPBaseInstance:
    coords: list[tuple[int, int]]
    demands: list[int]
    fleet_size: int
    total_demand: int
    coordinate_hash: str
    demand_hash: str


@dataclass(frozen=True)
class CVRPConstraintVariant:
    regime: str
    coords: list[tuple[int, int]]
    demands: list[int]
    capacity: int
    fleet_size: int
    coordinate_hash: str
    demand_hash: str
    total_demand: int
    rho_target: float
    rho_actual: float


def generate_cvrp_base_instance(
    node_count: int,
    base_seed: int = 42,
    coordinate_min: int = 0,
    coordinate_max: int = 1000,
    fleet_size: int | None = None,
    demand_min: int = 1,
    demand_max: int = 10,
    seed: int | None = None,
) -> CVRPBaseInstance:
    """Generates a base CVRP instance: (coordinates, demands, fleet_size K).
    
    Total node count = node_count (1 depot at index 0 + node_count - 1 customers).
    """
    effective_seed = seed if seed is not None else base_seed
    rng = random.Random(effective_seed)
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

    # Depot (index 0) has demand 0
    demands = [0]
    for _ in range(1, node_count):
        demands.append(rng.randint(demand_min, demand_max))

    if fleet_size is None:
        fleet_size = max(2, max(3, node_count // 5))

    total_demand = sum(demands)
    return CVRPBaseInstance(
        coords=coords_list,
        demands=demands,
        fleet_size=fleet_size,
        total_demand=total_demand,
        coordinate_hash=_coord_hash(coords_list),
        demand_hash=_demand_hash(demands),
    )


def derive_capacity_for_regime(
    demands: list[int],
    fleet_size: int,
    rho_target: float,
) -> tuple[int, float]:
    """Derives capacity Q and computes rho_actual = total_demand / (K * Q)."""
    total_demand = sum(demands)
    capacity = math.ceil(total_demand / (fleet_size * rho_target))
    rho_actual = total_demand / (fleet_size * capacity)
    return capacity, rho_actual


def generate_cvrp_constraint_regimes(
    node_count: int = 50,
    seed: int = 42,
    fleet_size: int = 8,
    demand_min: int = 1,
    demand_max: int = 10,
    coordinate_min: int = 0,
    coordinate_max: int = 1000,
) -> dict[str, CVRPConstraintVariant]:
    """Generates paired loose (0.55), medium (0.75), and tight (0.90) variants from a single base instance."""
    base = generate_cvrp_base_instance(
        node_count=node_count,
        base_seed=seed,
        coordinate_min=coordinate_min,
        coordinate_max=coordinate_max,
        fleet_size=fleet_size,
        demand_min=demand_min,
        demand_max=demand_max,
    )

    regimes_def = {
        "loose": 0.55,
        "medium": 0.75,
        "tight": 0.90,
    }

    variants: dict[str, CVRPConstraintVariant] = {}
    for regime_name, rho_target in regimes_def.items():
        cap, rho_act = derive_capacity_for_regime(base.demands, base.fleet_size, rho_target)
        variants[regime_name] = CVRPConstraintVariant(
            regime=regime_name,
            coords=base.coords,
            demands=base.demands,
            capacity=cap,
            fleet_size=base.fleet_size,
            coordinate_hash=base.coordinate_hash,
            demand_hash=base.demand_hash,
            total_demand=base.total_demand,
            rho_target=rho_target,
            rho_actual=rho_act,
        )
    return variants


def generate_cvrp_instance(
    node_count: int,
    seed: int,
    coordinate_min: int,
    coordinate_max: int,
    rho_target: float = 0.75,
    fleet_size: int | None = None,
    attempt: int = 0,
    return_meta: bool = False,
) -> Any:
    """Generates a CVRP instance adhering to target tightness with deterministic retry."""
    current_attempt = attempt
    while True:
        effective_seed = int(hashlib.sha256(f"{seed}:attempt_{current_attempt}".encode("utf-8")).hexdigest()[:16], 16)
        base = generate_cvrp_base_instance(
            node_count=node_count,
            base_seed=effective_seed,
            coordinate_min=coordinate_min,
            coordinate_max=coordinate_max,
            fleet_size=fleet_size,
        )
        total_demand = base.total_demand
        demand_max = max(base.demands) if len(base.demands) > 1 else 0
        k = base.fleet_size
        capacity, rho_actual = derive_capacity_for_regime(base.demands, k, rho_target)

        # Basic feasibility assertions: individual demand cannot exceed capacity, total demand cannot exceed total capacity
        if demand_max <= capacity and total_demand <= (k * capacity):
            if not return_meta:
                return base.coords, base.demands, capacity, k

            meta = {
                "total_demand": total_demand,
                "demand_max": demand_max,
                "fleet_size": k,
                "capacity": capacity,
                "rho_target": rho_target,
                "capacity_tightness": rho_target,
                "rho_actual": rho_actual,
                "coordinate_hash": base.coordinate_hash,
                "demand_hash": base.demand_hash,
                "generation_attempt": current_attempt,
                "base_seed": effective_seed,
            }
            return base.coords, base.demands, capacity, k, meta

        current_attempt += 1


def generate_cvrp_instance_with_meta(
    node_count: int,
    seed: int,
    coordinate_min: int,
    coordinate_max: int,
    rho_target: float = 0.75,
    fleet_size: int | None = None,
    attempt: int = 0,
) -> tuple[list[tuple[int, int]], list[int], int, int, dict[str, Any]]:
    return generate_cvrp_instance(
        node_count=node_count,
        seed=seed,
        coordinate_min=coordinate_min,
        coordinate_max=coordinate_max,
        rho_target=rho_target,
        fleet_size=fleet_size,
        attempt=attempt,
        return_meta=True,
    )


def write_cvrplib(
    path: str | Path,
    name: str,
    coordinates: list[tuple[int, int]],
    demands: list[int],
    capacity: int,
    vehicle_num: int,
    meta: dict[str, Any] | None = None,
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

    if meta:
        meta_path = target.parent / f"{full_name}.meta.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return file_path


def generate_cvrp_splits_for_regimes(
    base_output_dir: Path,
    node_count: int = 50,
    base_seed: int = 53050,
    fleet_size: int = 8,
    split_counts: dict[str, int] | None = None,
    coordinate_min: int = 0,
    coordinate_max: int = 1000,
) -> dict[str, Path]:
    """Generates split directories and manifests for loose, medium, and tight CVRP task suites."""
    counts = split_counts or {"train": 10, "validation": 5, "test": 5, "smoke": 2}
    regimes_map = {"loose": 0.55, "medium": 0.75, "tight": 0.90}
    results = {}

    for regime_name, rho_target in regimes_map.items():
        task_id = f"cvrp_uniform_n{node_count}_{regime_name}"
        task_dir = base_output_dir / task_id
        manifest: dict[str, Any] = {
            "task_id": task_id,
            "problem": "cvrp",
            "fleet_size": fleet_size,
            "constraint_regime": regime_name,
            "capacity_tightness": rho_target,
            "total_instances": sum(counts.values()),
            "splits": {},
        }

        for split_name, count in counts.items():
            split_dir = task_dir / split_name
            split_dir.mkdir(parents=True, exist_ok=True)
            manifest["splits"][split_name] = []

            for idx in range(count):
                inst_seed = _instance_seed(base_seed, f"cvrp_base_n{node_count}", split_name, idx)
                coords, demands, cap, k, meta = generate_cvrp_instance_with_meta(
                    node_count=node_count,
                    seed=inst_seed,
                    coordinate_min=coordinate_min,
                    coordinate_max=coordinate_max,
                    rho_target=rho_target,
                    fleet_size=fleet_size,
                )
                inst_name = f"{task_id}_{split_name}_{idx:03d}"
                meta["base_instance_id"] = f"cvrp_base_n{node_count}_{split_name}_{idx:03d}"
                meta["constraint_regime"] = regime_name
                meta["instance_id"] = inst_name

                write_cvrplib(split_dir / f"{inst_name}.vrp", inst_name, coords, demands, cap, k, meta=meta)
                manifest["splits"][split_name].append(meta)

        manifest_path = task_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        results[regime_name] = task_dir

    return results


def generate_cvrp_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
    if task.metadata.get("constraint_family") == "vrp" or task.metadata.get("vrp_variant"):
        from cmhh.data.vrp_generator import generate_vrp_variant_splits

        generate_vrp_variant_splits(task, experiment, seed)
        return

    split_dirs = {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }
    node_count = int(task.metadata.get("nodes", task.metadata.get("customers", 20)))
    effective_seed = int(task.metadata.get("dataset_seed", seed))
    base_id = task.metadata.get("base_dataset_id", f"cvrp_n{node_count}_base")
    regime = task.metadata.get("constraint_regime", "standard")
    rho_target = float(task.metadata.get("capacity_tightness", 0.75))
    fleet_size = int(task.metadata.get("fleet_size", max(2, node_count // 5)))

    for split_name, directory in split_dirs.items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        split_count = experiment.data.splits.get(split_name, 1)
        for index in range(split_count):
            base_seed = _instance_seed(effective_seed, base_id, split_name, index)
            coords, demands, cap, k, meta = generate_cvrp_instance_with_meta(
                node_count=node_count,
                seed=base_seed,
                coordinate_min=experiment.data.coordinate_min,
                coordinate_max=experiment.data.coordinate_max,
                rho_target=rho_target,
                fleet_size=fleet_size,
            )
            name = f"{task.task_id}_{split_name}_{index:03d}"
            meta["base_instance_id"] = f"{base_id}_{split_name}_{index:03d}"
            meta["constraint_regime"] = regime
            meta["instance_id"] = name
            write_cvrplib(directory / f"{name}.vrp", name, coords, demands, cap, k, meta=meta)


def _instance_seed(seed: int, task_id: str, split_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{split_name}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)
