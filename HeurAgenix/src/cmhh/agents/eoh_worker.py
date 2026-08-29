from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import traceback
from pathlib import Path
from urllib.parse import urlparse

from cmhh.data.tsp_io import load_euc2d_graph
from cmhh.llm.config import load_llm_config


TSP_TEMPLATE_PROGRAM = '''
from src.problems.tsp.components import AppendOperator, InsertOperator


def eoh_tsp_heuristic(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple:
    """Return one constructive TSP operator and an algorithm_data update dict."""
    distance_matrix = problem_state["distance_matrix"]
    current_solution = problem_state["current_solution"]
    unvisited_nodes = problem_state["unvisited_nodes"]
    if not unvisited_nodes:
        return None, {}
    if not current_solution.tour:
        return AppendOperator(int(unvisited_nodes[0])), {}
    last_node = current_solution.tour[-1]
    next_node = min(unvisited_nodes, key=lambda node: distance_matrix[last_node][node])
    return InsertOperator(int(next_node), len(current_solution.tour)), {}
'''


class CMHHTSPProblem:
    template_program = TSP_TEMPLATE_PROGRAM
    task_description = (
        "Design a constructive heuristic for Euclidean travelling salesman problem instances. "
        "The heuristic receives HeurAgenix TSP problem_state and algorithm_data, then returns "
        "one valid AppendOperator or InsertOperator plus an algorithm_data update dict. "
        "Minimise the mean completed tour length on the given training instances."
    )

    def __init__(self, instance_paths: list[str], timeout: int = 40, n_processes: int = 1):
        self.timeout = timeout
        self.n_processes = n_processes
        self.instance_paths = instance_paths

    def evaluate(self, code_string: str) -> float | None:
        from eoh import BaseProblem

        return BaseProblem.evaluate(self, code_string)

    def evaluate_program(self, program_str: str, callable_func) -> float | None:
        del program_str
        _ensure_tsplib95_fallback()
        from src.problems.base.components import BaseOperator
        from src.problems.tsp.env import Env

        objectives = []
        for instance_path in self.instance_paths:
            env = Env(data_name=str(Path(instance_path).resolve()))
            env.reset()
            operator = BaseOperator()
            max_steps = int(env.instance_data["node_num"]) + 5
            steps = 0
            while isinstance(operator, BaseOperator) and steps < max_steps:
                operator = env.run_heuristic(callable_func)
                steps += 1
                if env.is_complete_solution:
                    break
            if not env.is_complete_solution or not env.is_valid_solution:
                return None
            objective = float(env.key_value)
            if not math.isfinite(objective):
                return None
            objectives.append(objective)
        if not objectives:
            return None
        return sum(objectives) / len(objectives)


def _ensure_tsplib95_fallback() -> None:
    if "tsplib95" in sys.modules:
        return
    try:
        __import__("tsplib95")
        return
    except ModuleNotFoundError:
        pass

    import types
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


def _prompt_hash(repo_root: Path) -> str:
    digest = hashlib.sha256()
    digest.update(TSP_TEMPLATE_PROGRAM.encode("utf-8"))
    digest.update(CMHHTSPProblem.task_description.encode("utf-8"))
    return digest.hexdigest()


def _endpoint_from_config(config: dict) -> str:
    if config.get("api_endpoint"):
        return str(config["api_endpoint"]).removeprefix("https://").removeprefix("http://").split("/")[0]
    raw_url = config.get("base_url") or config.get("url")
    if not raw_url:
        raise ValueError("EOH requires 'api_endpoint', 'base_url', or 'url' in the LLM config")
    parsed = urlparse(str(raw_url))
    if parsed.netloc:
        return parsed.netloc
    return str(raw_url).removeprefix("https://").removeprefix("http://").split("/")[0]


def _latest_population(path: Path) -> list[dict]:
    pop_dir = path / "results" / "pops"
    files = sorted(
        pop_dir.glob("population_generation_*.json"),
        key=lambda item: int(re.search(r"(\d+)", item.stem).group(1)),
    )
    if not files:
        return []
    raw = json.loads(files[-1].read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else [raw]


def _write_candidate_files(population: list[dict], output_root: Path, max_candidates: int) -> list[dict]:
    candidate_dir = output_root / "candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidates = []
    for index, individual in enumerate(population[:max_candidates]):
        code = individual.get("code")
        if not code:
            continue
        function_name = f"official_eoh_candidate_{index:03d}"
        path = candidate_dir / f"{function_name}.py"
        wrapped_code = (
            code.rstrip()
            + "\n\n"
            + f"def {function_name}(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple:\n"
            + "    return eoh_tsp_heuristic(problem_state, algorithm_data, **kwargs)\n"
        )
        path.write_text(wrapped_code, encoding="utf-8")
        candidates.append({
            "path": str(path.resolve()),
            "objective": individual.get("objective"),
            "algorithm": individual.get("algorithm"),
        })
    return candidates


def run(args) -> dict:
    from eoh import EoH, LLMConfig

    repo_root = Path(args.repo_root).resolve()
    train_dir = Path(args.train_dir).resolve()
    output_root = Path(args.output_root).resolve()
    config = load_llm_config(args.llm_config)
    instances = sorted(str(path.resolve()) for path in train_dir.glob("*.tsp"))
    if not instances:
        raise FileNotFoundError(f"No TSP training instances found in {train_dir}")

    pop_size = max(1, args.pop_size)
    init_samples = 2 * pop_size
    connectivity_check_calls = 1
    evolution_samples = max(0, args.max_llm_calls - init_samples - connectivity_check_calls)

    task = CMHHTSPProblem(
        instance_paths=instances,
        timeout=args.evaluation_timeout,
        n_processes=args.num_evaluators,
    )
    llm = LLMConfig(
        api_endpoint=_endpoint_from_config(config),
        api_key=config.get("api_key"),
        model=config.get("model"),
        timeout=int(config.get("timeout", args.llm_timeout)),
    )
    eoh = EoH(
        llm=llm,
        problem=task,
        pop_size=pop_size,
        n_pop=max(1, args.generations),
        operators=["e1", "e2", "m1", "m2"],
        num_samplers=args.num_samplers,
        num_evaluators=args.num_evaluators,
        max_sample_nums=evolution_samples,
        output_dir=str(output_root),
    )
    eoh.run()
    population = _latest_population(output_root)
    candidates = _write_candidate_files(population, output_root, args.max_candidates)
    return {
        "status": "ok",
        "candidates": candidates,
        "calls_used_estimate": init_samples + evolution_samples + connectivity_check_calls,
        "model": config.get("name") or config.get("model"),
        "prompt_hash": _prompt_hash(repo_root),
        "official_eoh_repo": "https://github.com/FeiLiu36/EoH",
        "official_eoh_api": "LLMConfig/EoH/BaseProblem",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--train-dir", required=True)
    parser.add_argument("--llm-config", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--generations", required=True, type=int)
    parser.add_argument("--pop-size", required=True, type=int)
    parser.add_argument("--max-llm-calls", required=True, type=int)
    parser.add_argument("--max-candidates", required=True, type=int)
    parser.add_argument("--num-samplers", type=int, default=1)
    parser.add_argument("--num-evaluators", type=int, default=1)
    parser.add_argument("--llm-timeout", type=int, default=180)
    parser.add_argument("--evaluation-timeout", type=int, default=40)
    args = parser.parse_args()
    try:
        if args.problem != "tsp":
            raise ValueError(f"Official EOH baseline currently supports TSP only, got {args.problem}")
        result = run(args)
    except Exception:
        result = {"status": "failed", "error": traceback.format_exc(), "candidates": []}
    Path(args.result).write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
