from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from cmhh.config import ExperimentConfig
from cmhh.data.cvrp_generator import (
    _coord_hash,
    _demand_hash,
    _instance_seed,
    generate_cvrp_instance_with_meta,
    write_cvrplib,
)
from cmhh.tasks import TaskSpec
from src.problems.cvrp.variant import (
    CVRP_PROFILE,
    OVRP_PROFILE,
    OVRPTW_PROFILE,
    VRPTW_PROFILE,
    VRPConstraintProfile,
    profile_from_config,
)


VRP_VARIANT_PROFILES: dict[str, VRPConstraintProfile] = {
    "cvrp": CVRP_PROFILE,
    "ovrp": OVRP_PROFILE,
    "ovrptw": OVRPTW_PROFILE,
    "vrptw": VRPTW_PROFILE,
}


TIME_WINDOW_REGIMES: dict[str, tuple[float, float]] = {
    "loose": (1000.0, 2000.0),
    "medium": (600.0, 1200.0),
    "tight": (300.0, 600.0),
}



def generate_vrp_variant_splits(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> None:
    """Generates one task's VRP variant splits from a deterministic paired base instance."""
    variant_name = str(task.metadata.get("vrp_variant", task.metadata.get("variant", "cvrp"))).lower()
    profile = profile_from_config(variant_name)
    node_count = int(task.metadata.get("nodes", task.metadata.get("customers", 50)))
    effective_seed = int(task.metadata.get("dataset_seed", seed))
    base_id = str(task.metadata.get("base_dataset_id", f"vrp_uniform_n{node_count}_base"))
    rho_target = float(task.metadata.get("capacity_tightness", 0.75))
    fleet_size = int(task.metadata.get("fleet_size", max(2, node_count // 5)))
    tw_regime = str(task.metadata.get("time_window_regime", "medium"))
    service_duration = float(task.metadata.get("service_duration", 0.0))

    for split_name, directory in _task_split_dirs(task).items():
        if directory is None:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for old_file in list(directory.glob("*.vrp")) + list(directory.glob("*.meta.json")):
            try:
                old_file.unlink()
            except OSError:
                pass
        split_count = experiment.data.splits.get(split_name, 1)
        for index in range(split_count):
            pair_group_id = f"{base_id}_{split_name}_{index:03d}"
            base_seed = _instance_seed(effective_seed, base_id, split_name, index)
            coords, demands, capacity, generated_fleet_size, base_meta = generate_cvrp_instance_with_meta(
                node_count=node_count,
                seed=base_seed,
                coordinate_min=experiment.data.coordinate_min,
                coordinate_max=experiment.data.coordinate_max,
                rho_target=rho_target,
                fleet_size=fleet_size,
            )
            anchor_routes = build_capacity_feasible_anchor_routes(
                demands=demands,
                capacity=capacity,
                fleet_size=generated_fleet_size,
                coordinates=coords,
            )
            time_windows, tw_meta = generate_feasible_time_windows(
                coordinates=coords,
                anchor_routes=anchor_routes,
                regime=tw_regime,
                service_duration=service_duration,
                seed=_instance_seed(base_seed, "time_windows", split_name, index),
            )
            instance_id = f"{task.task_id}_{split_name}_{index:03d}"
            meta = {
                **base_meta,
                "family": "vrp",
                "variant": variant_name,
                "constraints": profile.to_dict(),
                "objective": "min_total_distance",
                "pair_group_id": pair_group_id,
                "base_instance_id": pair_group_id,
                "base_dataset_id": base_id,
                "instance_id": instance_id,
                "coordinate_hash": _coord_hash(coords),
                "demand_hash": _demand_hash(demands),
                "fleet_size": generated_fleet_size,
                "capacity": capacity,
                "capacity_tightness": rho_target,
                "time_windows": time_windows,
                "service_times": {"default": service_duration},
                "time_window_generation": tw_meta,
            }
            write_cvrplib(directory / f"{instance_id}.vrp", instance_id, coords, demands, capacity, generated_fleet_size, meta=meta)

    _write_vrp_task_manifest(task, experiment, effective_seed, profile, base_id)


def build_capacity_feasible_anchor_routes(
    demands: list[int],
    capacity: int,
    fleet_size: int,
    coordinates: list[tuple[int, int]],
) -> list[list[int]]:
    """Builds deterministic capacity-feasible customer routes for TW anchoring."""
    customers = sorted(range(1, len(demands)), key=lambda node: (-demands[node], node))
    routes: list[list[int]] = [[] for _ in range(fleet_size)]
    loads = [0 for _ in range(fleet_size)]

    for customer in customers:
        demand = int(demands[customer])
        candidates = [
            route_index
            for route_index, load in enumerate(loads)
            if load + demand <= capacity
        ]
        if not candidates:
            raise ValueError("Unable to construct a capacity-feasible anchor route assignment")
        route_index = min(candidates, key=lambda idx: (loads[idx], idx))
        routes[route_index].append(customer)
        loads[route_index] += demand

    return [_nearest_neighbor_order(route, coordinates) for route in routes]


def generate_feasible_time_windows(
    coordinates: list[tuple[int, int]],
    anchor_routes: list[list[int]],
    regime: str = "medium",
    service_duration: float = 0.0,
    seed: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generates hard time windows around one known feasible anchor schedule."""
    slack_before, slack_after = TIME_WINDOW_REGIMES.get(regime, TIME_WINDOW_REGIMES["medium"])
    distance_matrix = _distance_matrix(coordinates)
    customer_windows: dict[str, list[float]] = {}
    anchor_service_times: dict[str, float] = {}
    latest_seen = 0.0

    for route in anchor_routes:
        current_node = 0
        current_time = 0.0
        for customer in route:
            arrival = current_time + distance_matrix[current_node][customer]
            earliest = max(0.0, arrival - slack_before)
            latest = arrival + slack_after
            customer_windows[str(customer)] = [round(earliest, 6), round(latest, 6)]
            anchor_service_times[str(customer)] = round(arrival, 6)
            latest_seen = max(latest_seen, latest)
            current_time = arrival + service_duration
            current_node = customer

    horizon = round(latest_seen + slack_after + max(max(row) for row in distance_matrix), 6)
    time_windows = {
        "depot": [0.0, horizon],
        "customers": customer_windows,
    }
    metadata = {
        "method": "reference_schedule_anchor",
        "regime": regime,
        "seed": seed,
        "slack_before": slack_before,
        "slack_after": slack_after,
        "service_duration": service_duration,
        "anchor_routes": anchor_routes,
        "anchor_service_times": anchor_service_times,
    }
    return time_windows, metadata


def _nearest_neighbor_order(route: list[int], coordinates: list[tuple[int, int]]) -> list[int]:
    remaining = set(route)
    ordered = []
    current = 0
    while remaining:
        next_node = min(
            remaining,
            key=lambda node: (_euclidean(coordinates[current], coordinates[node]), node),
        )
        ordered.append(next_node)
        remaining.remove(next_node)
        current = next_node
    return ordered


def _distance_matrix(coordinates: list[tuple[int, int]]) -> list[list[float]]:
    return [
        [_euclidean(left, right) for right in coordinates]
        for left in coordinates
    ]


def _euclidean(left: tuple[int, int], right: tuple[int, int]) -> float:
    return math.hypot(float(left[0]) - float(right[0]), float(left[1]) - float(right[1]))


def _task_split_dirs(task: TaskSpec):
    return {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }


def _write_vrp_task_manifest(
    task: TaskSpec,
    experiment: ExperimentConfig,
    seed: int,
    profile: VRPConstraintProfile,
    base_id: str,
) -> Path:
    base = task.splits.train.parent
    records = {}
    for split_name, directory in _task_split_dirs(task).items():
        if directory is None or not directory.exists():
            continue
        records[split_name] = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.meta.json"))
        ]

    manifest_path = base / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "task_id": task.task_id,
                "problem": task.problem,
                "family": "vrp",
                "variant": profile.variant,
                "constraints": profile.to_dict(),
                "size_tier": task.size_tier,
                "distribution": task.distribution,
                "dataset_seed": seed,
                "data_seed": seed,
                "base_dataset_id": base_id,
                "coordinate_min": experiment.data.coordinate_min,
                "coordinate_max": experiment.data.coordinate_max,
                "metadata": task.metadata,
                "splits": records,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return manifest_path


def paired_seed_digest(*parts: object) -> str:
    return hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()
