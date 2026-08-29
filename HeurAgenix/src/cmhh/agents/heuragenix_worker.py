from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import traceback
import types
from pathlib import Path

from cmhh.llm.budgeted_client import BudgetedLLMClient
from cmhh.llm.config import load_llm_config


def _prompt_hash(repo_root: Path, problem: str) -> str:
    digest = hashlib.sha256()
    paths = [repo_root / "src/problems/base/prompt", repo_root / f"src/problems/{problem}/prompt"]
    for directory in paths:
        for path in sorted(directory.glob("*.txt")):
            digest.update(str(path.relative_to(repo_root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _format_memory_context(path: str | None) -> str:
    if not path:
        return ""
    memory_path = Path(path)
    if not memory_path.exists():
        return ""
    units = json.loads(memory_path.read_text(encoding="utf-8"))
    if not units:
        return ""
    lines = ["External memory units retrieved for this task:"]
    for unit in units:
        lines.append(_format_memory_unit(unit))
    return "\n".join(lines)


def _format_memory_unit(unit: dict) -> str:
    if "value" in unit and "key" in unit:
        value_type = unit["value"].get("type", "memory")
        content = unit["value"].get("content", "")
        applicability = unit["key"].get("applicability", "")
    else:
        abstraction = unit.get("abstraction", {})
        applicability_data = unit.get("applicability", {})
        value_type = abstraction.get("abstraction_type", "memory")
        content = abstraction.get("summary", "")
        applicability = " ".join(
            str(value)
            for value in (
                applicability_data.get("problem_family"),
                applicability_data.get("task_id"),
                applicability_data.get("size_tier"),
                applicability_data.get("distribution"),
            )
            if value
        )
    return f"- {unit.get('id', '<unknown>')} [{value_type}]: {content} Applicability: {applicability}"


def _ensure_tsplib95_fallback() -> None:
    if "tsplib95" in sys.modules:
        return
    try:
        __import__("tsplib95")
        return
    except ModuleNotFoundError:
        pass

    import networkx as nx
    import numpy as np

    from cmhh.data.tsp_io import load_euc2d_graph

    fallback = types.ModuleType("tsplib95")

    class FallbackProblem:
        def __init__(self, path: str) -> None:
            self._graph = nx.from_numpy_array(np.asarray(load_euc2d_graph(path), dtype=float))

        def get_graph(self):
            return self._graph

    fallback.load = lambda path: FallbackProblem(path)
    sys.modules["tsplib95"] = fallback


def run(args) -> dict:
    if args.problem == "tsp":
        _ensure_tsplib95_fallback()

    from src.pipeline.heuristic_evolver import HeuristicEvolver
    from src.util.llm_client.get_llm_client import get_llm_client

    repo_root = Path(args.repo_root).resolve()
    config = load_llm_config(args.llm_config)
    config["seed"] = args.seed
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fp:
        json.dump(config, fp)
        temporary_config = fp.name
    try:
        delegate = get_llm_client(
            temporary_config,
            str(repo_root / "src/problems/base/prompt"),
            None,
        )
        client = BudgetedLLMClient(delegate, args.max_llm_calls)
        evolver = HeuristicEvolver(
            client,
            args.problem,
            args.train_dir,
            args.validation_dir,
            output_root=args.output_root,
        )
        perturbations = sorted(
            path for path in (repo_root / f"src/problems/{args.problem}/heuristics/basic_heuristics").glob("random_????.py")
        )
        if not perturbations:
            raise FileNotFoundError(f"No random perturbation heuristic for {args.problem}")
        evolved = evolver.evolve(
            args.seed_heuristic,
            str(perturbations[0]),
            perturbation_time=args.perturbation_time,
            filtered_num=args.candidates_per_generation,
            evolution_round=args.generations,
            max_refinement_round=max(1, args.candidates_per_generation),
            smoke_test=False,
            external_memory_context=_format_memory_context(args.memory_context),
        )
        candidates = []
        for item in evolved or []:
            path = Path(item[0]).resolve()
            if path.exists():
                candidates.append({"path": str(path), "evolver_improvement": item[1]})
        return {
            "status": "ok",
            "candidates": candidates,
            "calls_used": client.calls_used,
            "model": delegate.name,
            "prompt_hash": _prompt_hash(repo_root, args.problem),
        }
    finally:
        Path(temporary_config).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--train-dir", required=True)
    parser.add_argument("--validation-dir", required=True)
    parser.add_argument("--seed-heuristic", required=True)
    parser.add_argument("--llm-config", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--memory-context")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--generations", required=True, type=int)
    parser.add_argument("--candidates-per-generation", required=True, type=int)
    parser.add_argument("--max-llm-calls", required=True, type=int)
    parser.add_argument("--perturbation-time", type=int, default=100)
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception:
        result = {"status": "failed", "error": traceback.format_exc(), "candidates": []}
    Path(args.result).write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

