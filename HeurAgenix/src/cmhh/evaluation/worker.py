from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path

from cmhh.evaluation.problem_adapter import ProblemRegistry
from src.pipeline.hyper_heuristics.single import SingleHyperHeuristic


def run(problem: str, instance: str, heuristic: str) -> dict:
    adapter = ProblemRegistry.get(problem)
    started = time.perf_counter()

    try:
        env = adapter.load_env(instance)
    except Exception as exc:
        return {
            "status": "environment_error",
            "objective": None,
            "runtime_seconds": time.perf_counter() - started,
            "error": f"Failed to load environment: {exc}",
        }

    try:
        runner = SingleHyperHeuristic(heuristic=str(Path(heuristic).resolve()), problem=problem)
        valid = runner.run(env)
    except Exception as exc:
        return {
            "status": "heuristic_error",
            "objective": None,
            "runtime_seconds": time.perf_counter() - started,
            "error": f"Heuristic execution error: {traceback.format_exc()}",
        }

    if not env.is_complete_solution:
        return {
            "status": "incomplete_solution",
            "objective": None,
            "runtime_seconds": time.perf_counter() - started,
            "error": "Heuristic did not produce a complete solution",
        }

    if hasattr(env, "is_valid_solution") and not env.is_valid_solution:
        return {
            "status": "invalid_solution",
            "objective": None,
            "runtime_seconds": time.perf_counter() - started,
            "error": "Heuristic produced an invalid solution violating constraints",
        }

    objective = float(env.key_value) if valid else None
    if objective is not None and not math.isfinite(objective):
        return {
            "status": "invalid_solution",
            "objective": None,
            "runtime_seconds": time.perf_counter() - started,
            "error": "Heuristic produced a non-finite objective",
        }

    return {
        "status": "ok" if valid else "invalid_solution",
        "objective": objective,
        "runtime_seconds": time.perf_counter() - started,
        "error": None if valid else "Heuristic validation failed",
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
