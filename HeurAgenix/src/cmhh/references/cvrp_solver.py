from __future__ import annotations

import math
import os
import time
from pathlib import Path

from cmhh.data.manifest import sha256_file
from cmhh.evaluation.problem_adapter import ensure_tsplib95_fallback
from cmhh.references.base import ReferenceResult, ReferenceSolverAdapter, SolverConfig


from cmhh.references.pyvrp_solver import PyVRPSolverAdapter


class CVRPSolverAdapter(ReferenceSolverAdapter):
    def __init__(self) -> None:
        self._pyvrp_adapter = PyVRPSolverAdapter()

    @property
    def problem_name(self) -> str:
        return "cvrp"

    def solve(self, instance_path: Path, config: SolverConfig) -> ReferenceResult:
        try:
            return self._pyvrp_adapter.solve(instance_path, config)
        except ImportError:
            ensure_tsplib95_fallback()
            import tsplib95
            import numpy as np

            started = time.perf_counter()
            instance = tsplib95.load(str(instance_path))
            checksum = sha256_file(instance_path)

            depot = instance.depots[0] - 1
            node_coords = instance.node_coords
            node_num = len(node_coords)
            capacity = instance.capacity
            demands = [int(instance.demands.get(i + 1, 0)) for i in range(node_num)]

            # Distance matrix
            dist = np.zeros((node_num, node_num))
            for i in range(node_num):
                x1, y1 = node_coords[i + 1]
                for j in range(node_num):
                    if i != j:
                        x2, y2 = node_coords[j + 1]
                        dist[i][j] = math.hypot(x1 - x2, y1 - y2)

            # Vehicle number from file name or default
            stem = instance_path.stem
            vehicle_num = 5
            if "-k" in stem:
                try:
                    vehicle_num = int(stem.split("-k")[-1].split(".")[0])
                except ValueError:
                    vehicle_num = max(2, node_num // 5)

            best_cost, best_routes = _solve_cvrp_savings_and_local_search(
                depot=depot,
                node_num=node_num,
                capacity=capacity,
                demands=demands,
                dist=dist,
                vehicle_num=vehicle_num,
                time_limit=config.timeout_seconds,
            )

            runtime = time.perf_counter() - started
            return ReferenceResult(
                instance_id=instance_path.stem,
                objective=float(best_cost),
                status="best_known",
                solver="cvrp_clarke_wright_local_search",
                instance_sha256=checksum,
                runtime_seconds=runtime,
                proven_optimal=False,
                metadata={
                    "vehicle_num": vehicle_num,
                    "node_num": node_num,
                    "capacity": capacity,
                    "routes": best_routes,
                },
            )


def _solve_cvrp_savings_and_local_search(
    depot: int,
    node_num: int,
    capacity: int,
    demands: list[int],
    dist: any,
    vehicle_num: int,
    time_limit: float = 30.0,
) -> tuple[float, list[list[int]]]:
    customers = [i for i in range(node_num) if i != depot]
    
    # 1. Clarke-Wright savings initialization
    savings = []
    for i in customers:
        for j in customers:
            if i < j:
                s = dist[depot][i] + dist[depot][j] - dist[i][j]
                savings.append((s, i, j))
    savings.sort(key=lambda item: item[0], reverse=True)

    # Initial routes: each customer in its own route
    routes: list[list[int]] = [[c] for c in customers]
    route_loads = [demands[c] for c in customers]

    for s, i, j in savings:
        # Find which routes contain i and j
        r_i_idx, r_j_idx = None, None
        for idx, r in enumerate(routes):
            if r_i_idx is None and i in r:
                r_i_idx = idx
            if r_j_idx is None and j in r:
                r_j_idx = idx
        if r_i_idx is None or r_j_idx is None or r_i_idx == r_j_idx:
            continue

        r_i = routes[r_i_idx]
        r_j = routes[r_j_idx]

        if route_loads[r_i_idx] + route_loads[r_j_idx] > capacity:
            continue

        # Check if i and j are at endpoints
        merged = None
        if r_i[-1] == i and r_j[0] == j:
            merged = r_i + r_j
        elif r_j[-1] == j and r_i[0] == i:
            merged = r_j + r_i
        elif r_i[0] == i and r_j[0] == j:
            merged = list(reversed(r_i)) + r_j
        elif r_i[-1] == i and r_j[-1] == j:
            merged = r_i + list(reversed(r_j))

        if merged is not None:
            routes[r_i_idx] = merged
            route_loads[r_i_idx] += route_loads[r_j_idx]
            routes.pop(r_j_idx)
            route_loads.pop(r_j_idx)

    # 2. 2-opt intra-route improvement
    improved_routes = []
    for route in routes:
        if len(route) > 2:
            route = _two_opt_route(route, depot, dist)
        improved_routes.append(route)

    # Calculate total cost
    total_cost = 0.0
    full_routes = []
    for r in improved_routes:
        full = [depot] + r + [depot]
        full_routes.append(full)
        for idx in range(len(full) - 1):
            total_cost += dist[full[idx]][full[idx + 1]]

    return total_cost, full_routes


def _two_opt_route(route: list[int], depot: int, dist: any) -> list[int]:
    best = list(route)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                # Cost change of reversing subsegment best[i:j+1]
                prev_node = depot if i == 0 else best[i - 1]
                next_node = depot if j == len(best) - 1 else best[j + 1]

                current_cost = dist[prev_node][best[i]] + dist[best[j]][next_node]
                new_cost = dist[prev_node][best[j]] + dist[best[i]][next_node]

                if new_cost < current_cost - 1e-6:
                    best[i:j + 1] = reversed(best[i:j + 1])
                    improved = True
                    break
            if improved:
                break
    return best
