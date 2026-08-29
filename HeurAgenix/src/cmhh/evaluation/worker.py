from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
import traceback
import types
from pathlib import Path


def run(problem: str, instance: str, heuristic: str) -> dict:
    if problem != "tsp":
        raise ValueError(f"Phase 0 worker only supports TSP, received {problem}")
    if importlib.util.find_spec("tsplib95") is None:
        from cmhh.data.tsp_io import load_euc2d_graph
        import networkx as nx
        import numpy as np

        fallback = types.ModuleType("tsplib95")

        class FallbackProblem:
            def __init__(self, path: str) -> None:
                self._graph = nx.from_numpy_array(np.asarray(load_euc2d_graph(path), dtype=float))

            def get_graph(self):
                return self._graph

        fallback.load = lambda path: FallbackProblem(path)
        sys.modules["tsplib95"] = fallback

    from src.pipeline.hyper_heuristics.single import SingleHyperHeuristic
    from src.problems.tsp.env import Env

    started = time.perf_counter()
    env = Env(data_name=str(Path(instance).resolve()))
    env.reset()
    runner = SingleHyperHeuristic(heuristic=str(Path(heuristic).resolve()), problem=problem)
    valid = runner.run(env)
    objective = float(env.key_value) if valid else None
    if objective is not None and not math.isfinite(objective):
        raise ValueError("Heuristic produced a non-finite objective")
    return {
        "status": "ok" if valid else "invalid_solution",
        "objective": objective,
        "runtime_seconds": time.perf_counter() - started,
        "error": None if valid else "Heuristic did not produce a complete valid solution",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem", required=True)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--heuristic", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    try:
        result = run(args.problem, args.instance, args.heuristic)
    except Exception:
        result = {
            "status": "crashed",
            "objective": None,
            "runtime_seconds": 0.0,
            "error": traceback.format_exc(),
        }
    Path(args.result).write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
