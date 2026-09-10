from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from cmhh.data.manifest import sha256_file
from cmhh.evaluation.problem_adapter import ensure_tsplib95_fallback
from cmhh.references.base import ReferenceResult, ReferenceSolverAdapter, SolverConfig
from src.problems.cvrp.components import Solution
from src.problems.cvrp.constraints import validate_solution
from src.problems.cvrp.route_metrics import total_solution_distance
from src.problems.cvrp.variant import CVRP_PROFILE, profile_from_config


class PyVRPSolverAdapter(ReferenceSolverAdapter):
    @property
    def problem_name(self) -> str:
        return "cvrp"

    def solve(self, instance_path: Path, config: SolverConfig) -> ReferenceResult:
        try:
            import pyvrp
            from pyvrp import Model
            from pyvrp.stop import MaxRuntime
        except ImportError as exc:
            raise ImportError(
                "PyVRP is required for CVRP reference generation. "
                "Create the conda env from `environment.yml` or run "
                "`python -m pip install pyvrp` in the active environment."
            ) from exc

        ensure_tsplib95_fallback()
        import tsplib95

        started = time.perf_counter()
        instance = Path(instance_path).resolve()
        checksum = sha256_file(instance)

        problem_data = tsplib95.load(str(instance))
        meta = _load_meta(instance)
        profile = profile_from_config(meta.get("variant") or meta.get("constraints") or CVRP_PROFILE)

        # Determine depot
        depot_node = problem_data.depots[0] if getattr(problem_data, "depots", None) else 1
        node_coords = problem_data.node_coords
        capacity = int(problem_data.capacity)

        # 1-indexed node IDs in TSPLIB
        nodes = list(sorted(node_coords.keys()))
        customer_nodes = [nid for nid in nodes if nid != depot_node]

        demands = {
            nid: int(problem_data.demands.get(nid, 0))
            for nid in nodes
        }
        internal_demands = [demands[nid] for nid in nodes]

        # Vehicle number from file name or estimate
        stem = instance.stem
        vehicle_num = 5
        if "-k" in stem:
            try:
                vehicle_num = int(stem.split("-k")[-1].split(".")[0])
            except ValueError:
                vehicle_num = max(2, len(customer_nodes) // 5)
        else:
            vehicle_num = max(2, len(customer_nodes) // 5)

        # Build PyVRP Model
        model = Model()
        depot_x, depot_y = node_coords[depot_node]
        if profile.time_windows:
            depot_tw_early, depot_tw_late = _time_window_for_internal_node(meta, 0, scale=1000)
            depot_loc = model.add_depot(x=depot_x, y=depot_y, tw_early=depot_tw_early, tw_late=depot_tw_late)
            end_depot_loc = None
            if profile.open_route:
                end_depot_loc = model.add_depot(x=depot_x, y=depot_y, tw_early=depot_tw_early, tw_late=depot_tw_late)
        else:
            depot_loc = model.add_depot(x=depot_x, y=depot_y)
            end_depot_loc = None
            if profile.open_route:
                end_depot_loc = model.add_depot(x=depot_x, y=depot_y)

        client_locs = []
        for c_node in customer_nodes:
            cx, cy = node_coords[c_node]
            internal_node = c_node - 1
            if profile.time_windows:
                tw_early, tw_late = _time_window_for_internal_node(meta, internal_node, scale=1000)
                c_loc = model.add_client(
                    x=cx,
                    y=cy,
                    delivery=demands[c_node] if profile.capacitated else 0,
                    service_duration=_service_time_for_internal_node(meta, internal_node, scale=1000),
                    tw_early=tw_early,
                    tw_late=tw_late,
                )
            else:
                c_loc = model.add_client(
                    x=cx,
                    y=cy,
                    delivery=demands[c_node] if profile.capacitated else 0,
                )
            client_locs.append(c_loc)

        model.add_vehicle_type(
            num_available=vehicle_num,
            capacity=capacity if profile.capacitated else [],
            start_depot=depot_loc,
            end_depot=end_depot_loc if profile.open_route else depot_loc,
        )

        # Add edges between all locations with Euclidean distances scaled by 1000
        SCALE = 1000
        all_locs = [depot_loc] + client_locs + ([end_depot_loc] if end_depot_loc is not None else [])
        all_nids = [depot_node] + customer_nodes + ([None] if end_depot_loc is not None else [])

        for i, loc_i in enumerate(all_locs):
            for j, loc_j in enumerate(all_locs):
                if profile.open_route and all_nids[j] is None:
                    d = 0.0
                elif all_nids[i] is None or all_nids[j] is None:
                    d = 0.0
                else:
                    xi, yi = node_coords[all_nids[i]]
                    xj, yj = node_coords[all_nids[j]]
                    d = math.hypot(xi - xj, yi - yj)
                scaled_d = int(round(d * SCALE))
                model.add_edge(loc_i, loc_j, distance=scaled_d, duration=scaled_d)

        # Solver configuration
        time_limit = max(0.1, float(config.timeout_seconds))
        seed = int(config.seed if config.seed is not None else 1)

        result = model.solve(stop=MaxRuntime(time_limit), seed=seed, display=False)
        runtime = time.perf_counter() - started

        try:
            import importlib.metadata
            pyvrp_version = importlib.metadata.version("pyvrp")
        except Exception:
            pyvrp_version = getattr(pyvrp, "__version__", "unknown")

        if result.is_feasible() and result.best:
            # Recompute exact floating-point Euclidean cost
            reconstructed_routes: list[list[int]] = []
            internal_routes: list[list[int]] = []

            for r in result.best.routes():
                visits = r.visits()
                if not visits:
                    continue
                route_nodes = [
                    customer_nodes[_client_index_from_visit(idx, depot_count=2 if profile.open_route else 1, client_count=len(customer_nodes))]
                    for idx in visits
                ]
                reconstructed_routes.append(route_nodes)
                internal_routes.append([node - 1 for node in route_nodes])

            internal_instance = _internal_instance_data(
                nodes=nodes,
                node_coords=node_coords,
                demands=internal_demands,
                depot_node=depot_node,
                vehicle_num=vehicle_num,
                capacity=capacity,
                profile=profile,
                meta=meta,
            )
            solution_routes = [[depot_node - 1, *route] for route in internal_routes]
            while len(solution_routes) < vehicle_num:
                solution_routes.append([depot_node - 1])
            solution = Solution(routes=solution_routes, depot=depot_node - 1)
            validation_results = validate_solution(solution, internal_instance, profile)
            internal_feasible = all(item.feasible for item in validation_results)
            exact_cost = total_solution_distance(solution, internal_instance, profile)
            if not internal_feasible:
                return ReferenceResult(
                    instance_id=instance.stem,
                    objective=None,
                    status="failed",
                    solver="pyvrp",
                    instance_sha256=checksum,
                    runtime_seconds=runtime,
                    proven_optimal=False,
                    metadata={
                        "solver": "pyvrp",
                        "solver_version": pyvrp_version,
                        "seed": seed,
                        "time_limit_seconds": time_limit,
                        "variant": profile.variant,
                        "constraints": profile.to_dict(),
                        "routes": reconstructed_routes,
                        "internal_routes": internal_routes,
                        "internal_validation": [item.__dict__ for item in validation_results],
                        "error": "PyVRP returned a route that failed internal VRP validation",
                    },
                )

            return ReferenceResult(
                instance_id=instance.stem,
                objective=float(exact_cost),
                status="best_known",
                solver="pyvrp",
                instance_sha256=checksum,
                runtime_seconds=runtime,
                proven_optimal=False,
                metadata={
                    "solver": "pyvrp",
                    "solver_version": pyvrp_version,
                    "seed": seed,
                    "time_limit_seconds": time_limit,
                    "variant": profile.variant,
                    "constraints": profile.to_dict(),
                    "iterations": getattr(result, "iterations", None),
                    "num_routes": len(reconstructed_routes),
                    "routes": reconstructed_routes,
                    "internal_routes": internal_routes,
                    "internal_objective": float(exact_cost),
                    "internal_validation_feasible": internal_feasible,
                    "vehicle_num": vehicle_num,
                    "capacity": capacity,
                },
            )

        return ReferenceResult(
            instance_id=instance.stem,
            objective=None,
            status="failed",
            solver="pyvrp",
            instance_sha256=checksum,
            runtime_seconds=runtime,
            proven_optimal=False,
            metadata={
                "solver": "pyvrp",
                "solver_version": pyvrp_version,
                "seed": seed,
                "time_limit_seconds": time_limit,
                "variant": profile.variant,
                "constraints": profile.to_dict(),
                "error": f"No feasible {profile.variant.upper()} solution found within time limit",
            },
        )


def _load_meta(instance: Path) -> dict[str, Any]:
    meta_path = instance.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _client_index_from_visit(visit: int, depot_count: int, client_count: int) -> int:
    client_index = int(visit) - depot_count
    if 0 <= client_index < client_count:
        return client_index
    legacy_index = int(visit) - 1
    if 0 <= legacy_index < client_count:
        return legacy_index
    if 0 <= int(visit) < client_count:
        return int(visit)
    raise IndexError(f"PyVRP visit id {visit} cannot be mapped to {client_count} clients")


def _time_window_for_internal_node(meta: dict[str, Any], node: int, scale: int) -> tuple[int, int]:
    time_windows = meta.get("time_windows", {})
    value = None
    if isinstance(time_windows, dict):
        if node == 0:
            value = time_windows.get("depot")
        if value is None:
            customers = time_windows.get("customers", {})
            value = customers.get(str(node), customers.get(node))
        if value is None:
            value = time_windows.get(str(node), time_windows.get(node))
    elif time_windows and node < len(time_windows):
        value = time_windows[node]
    if value is None:
        return 0, 9223372036854775807
    return int(round(float(value[0]) * scale)), int(round(float(value[1]) * scale))


def _service_time_for_internal_node(meta: dict[str, Any], node: int, scale: int) -> int:
    service_times = meta.get("service_times", {})
    if isinstance(service_times, dict):
        value = service_times.get(str(node), service_times.get(node, service_times.get("default", 0.0)))
    elif service_times and node < len(service_times):
        value = service_times[node]
    else:
        value = 0.0
    return int(round(float(value) * scale))


def _internal_instance_data(
    nodes: list[int],
    node_coords: dict[int, tuple[float, float]],
    demands: list[int],
    depot_node: int,
    vehicle_num: int,
    capacity: int,
    profile,
    meta: dict[str, Any],
) -> dict[str, Any]:
    matrix = []
    for left in nodes:
        row = []
        x1, y1 = node_coords[left]
        for right in nodes:
            x2, y2 = node_coords[right]
            row.append(math.hypot(x1 - x2, y1 - y2))
        matrix.append(row)
    return {
        "node_num": len(nodes),
        "distance_matrix": matrix,
        "depot": depot_node - 1,
        "vehicle_num": vehicle_num,
        "capacity": capacity,
        "demands": demands,
        "family": "vrp",
        "variant": profile.variant,
        "constraints": profile.to_dict(),
        "constraint_profile": profile,
        "time_windows": meta.get("time_windows", {}) if profile.time_windows else {},
        "service_times": meta.get("service_times", {"default": 0.0}) if profile.time_windows else {"default": 0.0},
    }
