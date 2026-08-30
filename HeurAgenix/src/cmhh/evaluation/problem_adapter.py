from __future__ import annotations

import importlib
import importlib.util
import math
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def ensure_tsplib95_fallback() -> None:
    """Provides a lightweight fallback for tsplib95 if not installed."""
    if "tsplib95" in sys.modules:
        return
    try:
        if importlib.util.find_spec("tsplib95") is not None:
            return
    except Exception:
        pass


    class FallbackProblem:
        def __init__(self, path: str | Path) -> None:
            self.path = Path(path)
            self.node_coords: dict[int, tuple[float, float]] = {}
            self.demands: dict[int, int] = {}
            self.depots: list[int] = [1]
            self.capacity: int = 100
            self.edge_weight_type: str = "EUC_2D"
            self.dimension: int = 0
            self._load(self.path)

        def _load(self, path: Path) -> None:
            section = None
            with path.open("r", encoding="utf-8") as fp:
                for raw_line in fp:
                    line = raw_line.strip()
                    if not line:
                        continue
                    if line.startswith("EDGE_WEIGHT_TYPE"):
                        self.edge_weight_type = line.split(":")[-1].strip()
                    elif line.startswith("CAPACITY"):
                        self.capacity = int(line.split(":")[-1].strip())
                    elif line.startswith("DIMENSION"):
                        self.dimension = int(line.split(":")[-1].strip())
                    elif line == "NODE_COORD_SECTION":
                        section = "coords"
                    elif line == "DEMAND_SECTION":
                        section = "demands"
                    elif line == "DEPOT_SECTION":
                        section = "depot"
                    elif line == "EOF":
                        break
                    elif section == "coords":
                        parts = line.split()
                        if len(parts) >= 3:
                            self.node_coords[int(parts[0])] = (float(parts[1]), float(parts[2]))
                    elif section == "demands":
                        parts = line.split()
                        if len(parts) >= 2:
                            self.demands[int(parts[0])] = int(float(parts[1]))
                    elif section == "depot":
                        val = int(line.split()[0])
                        if val != -1:
                            self.depots = [val]

        def get_graph(self):
            import networkx as nx
            import numpy as np
            coords = [self.node_coords[i + 1] for i in range(len(self.node_coords))]
            matrix = np.zeros((len(coords), len(coords)))
            for i in range(len(coords)):
                for j in range(len(coords)):
                    if i != j:
                        matrix[i][j] = math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
            return nx.from_numpy_array(matrix)

    fallback = types.ModuleType("tsplib95")
    fallback.load = lambda path: FallbackProblem(path)
    sys.modules["tsplib95"] = fallback


@dataclass(frozen=True)
class ProblemAdapter:
    problem_name: str
    instance_extensions: tuple[str, ...]
    env_class_path: str
    objective_sense: str = "minimize"

    def discover_instances(self, directory: Path) -> list[Path]:
        if not directory.exists():
            return []
        return sorted([
            p for p in directory.iterdir()
            if p.is_file() and any(p.name.lower().endswith(ext.lower()) for ext in self.instance_extensions)
        ])

    def load_env(self, instance_path: str | Path) -> Any:
        ensure_tsplib95_fallback()
        module_path, class_name = self.env_class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        env_cls = getattr(module, class_name)
        env = env_cls(data_name=str(Path(instance_path).resolve()))
        env.reset()
        return env


class ProblemRegistry:
    _adapters: dict[str, ProblemAdapter] = {}

    @classmethod
    def register(cls, adapter: ProblemAdapter) -> None:
        cls._adapters[adapter.problem_name.lower()] = adapter

    @classmethod
    def get(cls, problem: str) -> ProblemAdapter:
        key = problem.lower()
        if key not in cls._adapters:
            raise KeyError(f"No ProblemAdapter registered for problem '{problem}'. Available: {list(cls._adapters.keys())}")
        return cls._adapters[key]

    @classmethod
    def registered_problems(cls) -> list[str]:
        return list(cls._adapters.keys())


# Default built-in registrations for TSP, CVRP, JSSP
ProblemRegistry.register(ProblemAdapter(
    problem_name="tsp",
    instance_extensions=(".tsp",),
    env_class_path="src.problems.tsp.env.Env",
    objective_sense="minimize",
))

ProblemRegistry.register(ProblemAdapter(
    problem_name="cvrp",
    instance_extensions=(".vrp",),
    env_class_path="src.problems.cvrp.env.Env",
    objective_sense="minimize",
))

ProblemRegistry.register(ProblemAdapter(
    problem_name="jssp",
    instance_extensions=(".txt",),
    env_class_path="src.problems.jssp.env.Env",
    objective_sense="minimize",
))
