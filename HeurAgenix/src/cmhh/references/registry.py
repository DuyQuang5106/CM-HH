from __future__ import annotations

from cmhh.references.base import ReferenceSolverAdapter
from cmhh.references.concorde import ConcordeConfig
from cmhh.references.cvrp_solver import CVRPSolverAdapter
from cmhh.references.jssp_solver import JSSPSolverAdapter
from cmhh.references.ortools_cpsat_solver import ORToolsCPSATSolverAdapter
from cmhh.references.pyvrp_solver import PyVRPSolverAdapter
from cmhh.references.tsp_solver import TSPSolverAdapter


class ReferenceSolverRegistry:
    _solvers: dict[str, ReferenceSolverAdapter] = {}

    @classmethod
    def get_solver(
        cls,
        problem_or_solver: str,
        concorde_config: ConcordeConfig | None = None,
    ) -> ReferenceSolverAdapter:
        key = problem_or_solver.lower()
        if key in ("tsp", "concorde"):
            return TSPSolverAdapter(concorde_config=concorde_config)
        elif key in ("cvrp", "pyvrp"):
            return PyVRPSolverAdapter()
        elif key in ("jssp", "ortools_cpsat", "cpsat"):
            return ORToolsCPSATSolverAdapter()
        elif key in cls._solvers:
            return cls._solvers[key]
        else:
            raise KeyError(f"No reference solver adapter registered for '{problem_or_solver}'")

    @classmethod
    def register_solver(cls, name: str, solver: ReferenceSolverAdapter) -> None:
        cls._solvers[name.lower()] = solver

