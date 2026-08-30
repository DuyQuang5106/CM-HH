from __future__ import annotations

import math
import time
from pathlib import Path

from cmhh.data.manifest import sha256_file
from cmhh.data.tsp_io import read_euc2d_coordinates
from cmhh.references.base import ReferenceResult, ReferenceSolverAdapter, SolverConfig
from cmhh.references.concorde import ConcordeConfig, solve_instance as solve_concorde


class TSPSolverAdapter(ReferenceSolverAdapter):
    def __init__(self, concorde_config: ConcordeConfig | None = None) -> None:
        self.concorde_config = concorde_config

    @property
    def problem_name(self) -> str:
        return "tsp"

    def solve(self, instance_path: Path, config: SolverConfig) -> ReferenceResult:
        instance = Path(instance_path).resolve()
        checksum = sha256_file(instance)
        started = time.perf_counter()

        # If concorde_config is provided and executable exists, use Concorde
        if self.concorde_config:
            exe = Path(self.concorde_config.command_prefix[0])
            if exe.exists():
                tour_dir = instance.parent / "tours"
                tour_path = tour_dir / f"{instance.stem}.tour"
                outcome = solve_concorde(instance, "n50", self.concorde_config, tour_path)
                if hasattr(outcome, "objective"):
                    return ReferenceResult(
                        instance_id=outcome.instance_id,
                        objective=outcome.objective,
                        status="optimal",
                        solver="concorde",
                        instance_sha256=outcome.instance_sha256,
                        runtime_seconds=outcome.runtime_seconds,
                        proven_optimal=True,
                        tour_path=outcome.tour_path,
                    )

        # High quality Multi-Start 2-Opt TSP solver fallback
        coords = read_euc2d_coordinates(instance)
        n = len(coords)
        dist = [[math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1]) for j in range(n)] for i in range(n)]

        best_cost, best_tour = _solve_tsp_multistart_2opt(dist, n)
        runtime = time.perf_counter() - started

        return ReferenceResult(
            instance_id=instance.stem,
            objective=float(best_cost),
            status="best_known",
            solver="tsp_multistart_2opt",
            instance_sha256=checksum,
            runtime_seconds=runtime,
            proven_optimal=False,
            metadata={"dimension": n},
        )


def _solve_tsp_multistart_2opt(dist: list[list[float]], n: int) -> tuple[float, list[int]]:
    if n <= 1:
        return 0.0, list(range(n))

    # Nearest neighbor construction from multiple start nodes
    best_cost = float("inf")
    best_tour = list(range(n))

    for start_node in range(min(5, n)):
        unvisited = set(range(n))
        curr = start_node
        unvisited.remove(curr)
        tour = [curr]
        while unvisited:
            next_node = min(unvisited, key=lambda node: dist[curr][node])
            unvisited.remove(next_node)
            tour.append(next_node)
            curr = next_node

        # 2-opt local search
        improved = True
        while improved:
            improved = False
            for i in range(n - 1):
                for j in range(i + 1, n):
                    next_i = tour[(i + 1) % n]
                    next_j = tour[(j + 1) % n]
                    current_dist = dist[tour[i]][next_i] + dist[tour[j]][next_j]
                    new_dist = dist[tour[i]][tour[j]] + dist[next_i][next_j]
                    if new_dist < current_dist - 1e-6:
                        tour[i + 1: j + 1] = reversed(tour[i + 1: j + 1])
                        improved = True
                        break
                if improved:
                    break

        cost = sum(dist[tour[k]][tour[(k + 1) % n]] for k in range(n))
        if cost < best_cost:
            best_cost = cost
            best_tour = tour

    return best_cost, best_tour
