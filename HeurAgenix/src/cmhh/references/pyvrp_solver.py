from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from cmhh.data.manifest import sha256_file
from cmhh.evaluation.problem_adapter import ensure_tsplib95_fallback
from cmhh.references.base import ReferenceResult, ReferenceSolverAdapter, SolverConfig


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
                "Run `uv sync` to install all managed dependencies."
            ) from exc

        ensure_tsplib95_fallback()
        import tsplib95

        started = time.perf_counter()
        instance = Path(instance_path).resolve()
        checksum = sha256_file(instance)

        problem_data = tsplib95.load(str(instance))

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
        depot_loc = model.add_depot(x=depot_x, y=depot_y)

        client_locs = []
        for c_node in customer_nodes:
            cx, cy = node_coords[c_node]
            c_loc = model.add_client(
                x=cx,
                y=cy,
                delivery=demands[c_node],
            )
            client_locs.append(c_loc)

        model.add_vehicle_type(
            num_available=vehicle_num,
            capacity=capacity,
        )

        # Add edges between all locations with Euclidean distances scaled by 1000
        SCALE = 1000
        all_locs = [depot_loc] + client_locs
        all_nids = [depot_node] + customer_nodes

        for i, loc_i in enumerate(all_locs):
            xi, yi = node_coords[all_nids[i]]
            for j, loc_j in enumerate(all_locs):
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
            exact_cost = 0.0
            reconstructed_routes: list[list[int]] = []

            for r in result.best.routes():
                visits = r.visits()
                if not visits:
                    continue
                # visits are 1-indexed into client_locs (1 -> customer_nodes[0])
                route_nodes = [customer_nodes[idx - 1] for idx in visits]
                reconstructed_routes.append(route_nodes)

                full_path = [depot_node] + route_nodes + [depot_node]
                for k in range(len(full_path) - 1):
                    x1, y1 = node_coords[full_path[k]]
                    x2, y2 = node_coords[full_path[k + 1]]
                    exact_cost += math.hypot(x1 - x2, y1 - y2)

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
                    "iterations": getattr(result, "iterations", None),
                    "num_routes": len(reconstructed_routes),
                    "routes": reconstructed_routes,
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
                "error": "No feasible CVRP solution found within time limit",
            },
        )
