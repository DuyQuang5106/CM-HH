import importlib
import json
import logging
import math
import multiprocessing
import os
import queue as queue_module
import re
import sys
import time
import traceback
from io import StringIO
import pandas as pd
from src.problems.base.env import BaseEnv
from src.pipeline.heuristic_generator import HeuristicGenerator
from src.pipeline.hyper_heuristics.single import SingleHyperHeuristic
from src.pipeline.hyper_heuristics.perturbation import PerturbationHyperHeuristic
from src.util.util import df_to_str, extract, filter_dict_to_str, parse_text_to_dict, load_function, extract_function_with_short_docstring, search_file
from src.util.llm_client.base_llm_client import BaseLLMClient

try:
    from cmhh.llm.budgeted_client import LLMBudgetExceeded
except Exception:
    class LLMBudgetExceeded(RuntimeError):
        pass


class InvalidValidationResult(ValueError):
    """Raised when an invalid or incomplete validation result reaches fitness calculation."""
    pass


_LOGGER = logging.getLogger("heuragenix.evolver")

_MP_CONTEXT = multiprocessing.get_context("spawn")
DEFAULT_VALIDATION_CASE_TIMEOUT_SECONDS = float(os.getenv("CMHH_VALIDATION_CASE_TIMEOUT_SECONDS", "15.0"))
DEFAULT_VALIDATION_CANDIDATE_TIMEOUT_SECONDS = float(os.getenv("CMHH_VALIDATION_CANDIDATE_TIMEOUT_SECONDS", "60.0"))
DEFAULT_MAX_ATTEMPTS_PER_SLOT = int(os.getenv("CMHH_MAX_ATTEMPTS_PER_SLOT", "3"))
DEFAULT_MAX_FAILED_ATTEMPTS_PER_GENERATION = int(os.getenv("CMHH_MAX_FAILED_ATTEMPTS_PER_GENERATION", "10"))


def _dump_termination_metadata(output_dir: str, stats: dict) -> None:
    try:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "termination_metadata.json")
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(stats, fp, indent=2)
        _LOGGER.info("[EVOLVE] saved termination metadata -> %s", path)
    except Exception as exc:
        _LOGGER.warning("[EVOLVE] failed to save termination metadata: %s", exc)


def _data_files(directory: str, problem: str | None = None) -> list[str]:
    valid_exts = {
        "tsp": (".tsp",),
        "cvrp": (".vrp",),
        "jssp": (".txt",),
    }
    allowed = valid_exts.get(problem.lower(), None) if problem else None
    files = []
    for name in sorted(os.listdir(directory)):
        if name.startswith(".") or name.endswith(".meta.json") or name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        if allowed is not None:
            if any(name.lower().endswith(ext) for ext in allowed):
                files.append(path)
        else:
            files.append(path)
    return files


def _heuristic_docs(heuristic_dir: str, problem: str) -> str:
    docs = []
    for name in sorted(os.listdir(heuristic_dir)):
        if name.startswith(".") or not name.endswith(".py"):
            continue
        local_path = os.path.join(heuristic_dir, name)
        heuristic_path = local_path if os.path.exists(local_path) else search_file(name, problem)
        if heuristic_path is None:
            continue
        function_name = os.path.splitext(os.path.basename(heuristic_path))[0]
        doc = extract_function_with_short_docstring(
            open(heuristic_path, encoding="utf-8").read(),
            function_name,
        )
        if doc:
            docs.append(doc)
    return "\n".join(docs)


def _run_validation_worker(problem: str, data_name: str, heuristic_file: str, result_queue: multiprocessing.Queue) -> None:
    try:
        from cmhh.evaluation.problem_adapter import ProblemRegistry

        adapter = ProblemRegistry.get(problem)
        env = adapter.load_env(data_name)
        hyper_heuristic = SingleHyperHeuristic(heuristic_file, problem=problem)
        is_complete = hyper_heuristic.run(env)
        is_feasible = getattr(env, "is_feasible", lambda: True)()
        val = env.key_value
        if is_complete and is_feasible and val is not None and math.isfinite(float(val)):
            result_queue.put(("ok", float(val)))
        else:
            result_queue.put(("invalid", None))
    except Exception:
        trace = traceback.format_exc()[:4096]
        result_queue.put(("error", trace))


def _run_validation_case_with_timeout(
    problem: str,
    data_name: str,
    heuristic_file: str,
    timeout_seconds: float,
) -> float | None:
    result_queue = _MP_CONTEXT.Queue()
    process = _MP_CONTEXT.Process(
        target=_run_validation_worker,
        args=(problem, data_name, heuristic_file, result_queue),
    )
    process.start()

    try:
        status, payload = result_queue.get(timeout=timeout_seconds)
        process.join(2.0)
    except queue_module.Empty:
        if process.is_alive():
            process.terminate()
            process.join(2.0)
            if process.is_alive():
                process.kill()
                process.join(2.0)
        _LOGGER.warning(
            "[EVOLVE] validation case timeout after %.1fs | heuristic=%s | data=%s",
            timeout_seconds,
            os.path.basename(heuristic_file),
            os.path.basename(data_name),
        )
        return None
    finally:
        try:
            result_queue.close()
            result_queue.join_thread()
        except Exception:
            pass

    if status == "ok":
        return payload
    _LOGGER.warning(
        "[EVOLVE] validation worker failed | heuristic=%s | data=%s | status=%s",
        os.path.basename(heuristic_file),
        os.path.basename(data_name),
        status,
    )
    return None


class HeuristicEvolver:
    def __init__(
        self,
        llm_client: BaseLLMClient,
        problem: str,
        evolution_dir: str,
        validation_dir: str,
        output_root: str="output",
    ) -> None:
        self.llm_client = llm_client
        self.problem = problem
        self.evolution_cases = _data_files(evolution_dir, problem=self.problem)
        self.validation_cases = _data_files(validation_dir, problem=self.problem)
        self.output_root = output_root
        self.get_instance_problem_state = load_function("problem_state.py", problem=self.problem, function_name="get_instance_problem_state")
        self.get_solution_problem_state = load_function("problem_state.py", problem=self.problem, function_name="get_solution_problem_state")

        # Load env
        module = importlib.import_module(f"src.problems.{problem}.env")
        globals()["Env"] = getattr(module, "Env")

        # Load components
        if os.path.exists(os.path.join("src", "problems", self.problem, "components.py")):
            module = importlib.import_module(f"src.problems.{self.problem}.components")
        else:
            module = importlib.import_module(f"src.problems.base.mdp_components")
        names_to_import = (name for name in dir(module) if not name.startswith('_'))
        for name in names_to_import:
            globals()[name] = getattr(module, name)
        
        # Ready for validation feature
        instance_problem_states = []
        for data in self.validation_cases:
            global_data = Env(data_name=data).instance_data
            instance_problem_state = {"data_name": data.split(os.sep)[-1]}
            instance_problem_state.update(self.get_instance_problem_state(global_data))
            instance_problem_states.append(instance_problem_state)
        self.instance_problem_states_df = pd.DataFrame(instance_problem_states)

    def evolve(
        self,
        basic_heuristic_file: str,
        perturbation_heuristic_file: str,
        perturbation_ratio: float = 0.1,
        perturbation_time: int = 100,
        filtered_num: int = 3,
        evolution_round: int = 3,
        max_refinement_round: int = 5,
        smoke_test: bool = True,
        external_memory_context: str = "",
        max_attempts_per_slot: int = DEFAULT_MAX_ATTEMPTS_PER_SLOT,
        max_failed_attempts_per_generation: int = DEFAULT_MAX_FAILED_ATTEMPTS_PER_GENERATION,
    ) -> list[tuple[str, float]]:
        # Prepare other heuristics' description for this evolution
        heuristic_dir = os.path.dirname(basic_heuristic_file)

        heuristic_introduction_docs = _heuristic_docs(heuristic_dir, self.problem)
        if external_memory_context:
            heuristic_introduction_docs += "\n\n" + external_memory_context

        output_root = getattr(self, "output_root", "output")
        metadata_output_dir = os.path.join(output_root, self.problem, "evolution_result")
        llm_client = getattr(self, "llm_client", None)
        stats = {
            "termination_reason": "completed",
            "completed_normally": True,
            "generation": 0,
            "llm_budget": getattr(llm_client, "max_calls", None),
            "llm_calls_used": getattr(llm_client, "call_count", 0),
            "valid_candidates": 0,
            "invalid_candidates": 0,
            "smoke_timeouts": 0,
            "smoke_crashes": 0,
            "validation_timeouts": 0,
            "validation_crashes": 0,
            "failed_generation_attempts": 0,
            "runtime_guards": {
                "smoke_warn_seconds": float(os.getenv("CMHH_SMOKE_STEP_WARN_SECONDS", "0.2")),
                "smoke_timeout_seconds": float(os.getenv("CMHH_SMOKE_STEP_TIMEOUT_SECONDS", "1.0")),
                "validation_case_timeout_seconds": DEFAULT_VALIDATION_CASE_TIMEOUT_SECONDS,
                "validation_candidate_timeout_seconds": DEFAULT_VALIDATION_CANDIDATE_TIMEOUT_SECONDS,
                "max_attempts_per_slot": max_attempts_per_slot,
                "max_failed_attempts_per_generation": max_failed_attempts_per_generation,
            },
            "platform": sys.platform,
            "python_version": sys.version,
        }

        total_heuristic_benchmarks = [(basic_heuristic_file, 0.0)]
        for round_idx in range(evolution_round):
            stats["generation"] = round_idx + 1
            _LOGGER.info(
                "[EVOLVE] generation=%d/%d started | pool_size=%d",
                round_idx + 1,
                evolution_round,
                len(total_heuristic_benchmarks),
            )
            # Filter the best heuristics
            filtered_heuristic_benchmarks = sorted(total_heuristic_benchmarks, key=lambda x: x[1], reverse=True)[: filtered_num]

            gen_failed_attempts = 0
            generation_new_heuristics = []

            for current_heuristic_file, _ in filtered_heuristic_benchmarks:
                slot_evolved = []
                for data_name in self.evolution_cases:
                    slot_failed_attempts = 0
                    while slot_failed_attempts < max_attempts_per_slot:
                        try:
                            evolved_heuristic_with_improvements = self.evolution_single(
                                evolution_data=data_name,
                                basic_heuristic_file=current_heuristic_file,
                                perturbation_heuristic_file=perturbation_heuristic_file,
                                all_heuristic_docs=heuristic_introduction_docs,
                                perturbation_ratio=perturbation_ratio,
                                perturbation_time=perturbation_time,
                                max_refinement_round=max_refinement_round,
                                smoke_test=smoke_test,
                            )
                        except LLMBudgetExceeded as exc:
                            _LOGGER.warning("[EVOLVE] LLM budget exhausted; stopping evolution early: %s", exc)
                            stats["termination_reason"] = "llm_budget_exhausted"
                            stats["completed_normally"] = False
                            stats["llm_calls_used"] = getattr(llm_client, "call_count", 0)
                            _dump_termination_metadata(metadata_output_dir, stats)
                            return sorted(total_heuristic_benchmarks, key=lambda x: x[1], reverse=True)[: filtered_num]

                        if evolved_heuristic_with_improvements:
                            slot_evolved.extend(evolved_heuristic_with_improvements)
                            total_heuristic_benchmarks.extend(evolved_heuristic_with_improvements)
                            stats["valid_candidates"] += len(evolved_heuristic_with_improvements)
                            break
                        else:
                            slot_failed_attempts += 1
                            gen_failed_attempts += 1
                            stats["failed_generation_attempts"] += 1
                            stats["invalid_candidates"] += 1

                        if gen_failed_attempts >= max_failed_attempts_per_generation:
                            _LOGGER.warning(
                                "[EVOLVE] max failed attempts reached for generation %d (%d failures); retaining last complete valid population",
                                round_idx + 1,
                                gen_failed_attempts,
                            )
                            stats["termination_reason"] = "failed_attempt_cap_exceeded"
                            stats["completed_normally"] = False
                            stats["llm_calls_used"] = getattr(llm_client, "call_count", 0)
                            _dump_termination_metadata(metadata_output_dir, stats)
                            return sorted(total_heuristic_benchmarks, key=lambda x: x[1], reverse=True)[: filtered_num]

                    if not slot_evolved:
                        _LOGGER.info(
                            "[EVOLVE] slot attempts exhausted for %s on %s; keeping incumbent parent unchanged",
                            os.path.basename(current_heuristic_file),
                            os.path.basename(data_name),
                        )

            if filtered_heuristic_benchmarks:
                best_file, best_imp = filtered_heuristic_benchmarks[0]
                _LOGGER.info(
                    "[EVOLVE] generation=%d complete | best=%s | improvement=%.4f",
                    round_idx + 1,
                    os.path.basename(best_file),
                    best_imp,
                )

        stats["llm_calls_used"] = getattr(llm_client, "call_count", 0)
        _dump_termination_metadata(metadata_output_dir, stats)
        return sorted(total_heuristic_benchmarks, key=lambda x: x[1], reverse=True)[: filtered_num]

    def evolution_single(
        self,
        evolution_data: str,
        basic_heuristic_file: str,
        perturbation_heuristic_file: str,
        all_heuristic_docs: str,
        perturbation_ratio: float = 0.1,
        perturbation_time: int = 100,
        max_refinement_round: int = 5,
        smoke_test: bool = True,
    ) -> list[tuple[str, float]]:
        refined_heuristic_benchmarks = []
        try:
            from cmhh.evaluation.problem_adapter import ProblemRegistry

            adapter = ProblemRegistry.get(self.problem)
            env = adapter.load_env(evolution_data)
            basic_heuristic_name = basic_heuristic_file.split(os.sep)[-1].split(".")[0]
            data_ref_name = getattr(env, "data_ref_name", os.path.splitext(os.path.basename(evolution_data))[0])
            output_dir = os.path.join(self.output_root, self.problem, "evolution_result", f"{basic_heuristic_name}.evolution", data_ref_name)
            self.llm_client.reset(output_dir)

            # Perturb for better solution
            negative_result, positive_result = self.perturbation(
                env,
                basic_heuristic_file,
                perturbation_heuristic_file,
                output_dir,
                perturbation_ratio,
                perturbation_time,
            )

            if positive_result:
                _LOGGER.info("[EVOLVE] evolving %s on %s", basic_heuristic_name, os.path.basename(evolution_data))

                prompt_dict = self.llm_client.load_background(self.problem, "background_with_code")
                prompt_dict["all_heuristic_docs"] = all_heuristic_docs
                self.load_function_code(basic_heuristic_file, prompt_dict)

                # Identify bottlenecks
                bottlenecks = self.identity_bottlenecks(
                    prompt_dict=prompt_dict,
                    env=env,
                    positive_result=positive_result,
                    negative_result=negative_result,
                )

                # Validate basic heuristic baseline
                basic_heuristic_result = self.validation(self.validation_cases, basic_heuristic_file)
                if basic_heuristic_result is None or any(r is None for r in basic_heuristic_result):
                    _LOGGER.warning("[EVOLVE] basic heuristic %s failed validation, skipping evolution", basic_heuristic_name)
                    return refined_heuristic_benchmarks

                for bottleneck_index, (bottleneck_operation_id, proposed_operation, reason) in enumerate(bottlenecks):
                    # Raise suggestion and provide evolved heuristics
                    suggestion_name = f"suggestion_{bottleneck_index}"
                    suggested_heuristic_file, suggestion, suggested_result = self.raise_suggestion(
                        prompt_dict=prompt_dict,
                        env=env,
                        bottleneck_operation_id=bottleneck_operation_id,
                        proposed_operation=proposed_operation,
                        reason=reason,
                        suggestion_name=suggestion_name,
                        smoke_test=smoke_test,
                    )
                    if suggested_heuristic_file and suggested_result is not None and not any(r is None for r in suggested_result):
                        output_heuristic_name = suggested_heuristic_file.split(os.sep)[-1].split(".")[0]
                        self.llm_client.dump(f"{basic_heuristic_name}_to_{output_heuristic_name}")

                        suggested_improvement = self.mean_improvement(env, basic_heuristic_result, suggested_result)
                        _LOGGER.info("[EVOLVE] candidate %s improvement=%.4f", os.path.basename(suggested_heuristic_file), suggested_improvement)
                        refined_heuristic_benchmarks.append((suggested_heuristic_file, suggested_improvement))

                        # Fine tune the evolved heuristics
                        previous_heuristic_name = basic_heuristic_name
                        previous_heuristic_result = basic_heuristic_result
                        last_heuristic_name = output_heuristic_name
                        last_heuristic_result = suggested_result
                        last_suggestion = suggestion
                        for refine_index in range(max_refinement_round):
                            suggestion_name = f"suggestion_{bottleneck_index}_refine_{refine_index}"
                            refined_heuristic_file, suggestion, refined_result = self.refine_heuristic(
                                prompt_dict=prompt_dict,
                                env=env,
                                basic_heuristic_name=basic_heuristic_name,
                                basic_heuristic_result=basic_heuristic_result,
                                previous_heuristic_name=previous_heuristic_name,
                                previous_heuristic_result=previous_heuristic_result,
                                last_heuristic_name=last_heuristic_name,
                                last_heuristic_result=last_heuristic_result,
                                last_suggestion=last_suggestion,
                                suggestion_name=suggestion_name,
                                smoke_test=smoke_test,
                            )
                            if refined_result is None or any(r is None for r in refined_result) or not refined_heuristic_file:
                                _LOGGER.warning("[EVOLVE] refinement produced invalid result, skipping (incumbent %s preserved)", last_heuristic_name)
                                continue

                            output_heuristic_name = refined_heuristic_file.split(os.sep)[-1].split(".")[0]
                            self.llm_client.dump(f"{last_heuristic_name}_to_{output_heuristic_name}")
                            refined_improvement = self.mean_improvement(env, basic_heuristic_result, refined_result)
                            _LOGGER.info("[EVOLVE] refined %s improvement=%.4f", os.path.basename(refined_heuristic_file), refined_improvement)
                            refined_heuristic_benchmarks.append((refined_heuristic_file, refined_improvement))
                            if suggestion is None:
                                break
                            previous_heuristic_name = last_heuristic_name
                            previous_heuristic_result = last_heuristic_result
                            last_suggestion = suggestion
                            last_heuristic_name = output_heuristic_name
                            last_heuristic_result = refined_result
        except LLMBudgetExceeded:
            raise
        except Exception as e:
            trace_string = traceback.format_exc()
            _LOGGER.error("[EVOLVE] exception in evolution_single: %s", trace_string)

        return refined_heuristic_benchmarks

    def perturbation(
            self,
            env: BaseEnv,
            basic_heuristic_file: str,
            perturbation_heuristic_file: str,
            output_dir: str,
            perturbation_ratio: float=0.1,
            perturbation_time: int=100,
        ) -> tuple[bool, str, str]:
        env.reset(output_dir)

        # Generate negative result from basic heuristic
        hyper_heuristic = SingleHyperHeuristic(basic_heuristic_file, problem=self.problem)
        hyper_heuristic.run(env)
        negative_result = env.dump_result(dump_records=["operation_id", "operator"], result_file="negative_solution.txt")
        negative_value = env.key_value

        # Generate positive result by perturbation heuristic
        positive_result = None
        for _ in range(perturbation_time):
            env.reset(output_dir)
            hyper_heuristic = PerturbationHyperHeuristic(basic_heuristic_file, perturbation_heuristic_file, self.problem, perturbation_ratio)
            hyper_heuristic.run(env)
            if env.compare(env.key_value, negative_value) > 0:
                positive_result = env.dump_result(dump_records=["operation_id", "operator"], result_file="positive_solution.txt")
                break
        return negative_result, positive_result

    def load_function_code(self, heuristic_file: str, prompt_dict: dict) -> str:
        heuristic_file = search_file(heuristic_file, problem=self.problem)
        function_name = heuristic_file.split(os.sep)[-1].split(".")[0]
        function_code = open(heuristic_file, encoding="utf-8").read()
        heuristic_name = function_name[:-5]
        prompt_dict["function_name"] = function_name
        prompt_dict["function_code"] = function_code
        prompt_dict["heuristic_name"] = heuristic_name
        return function_code

    def identity_bottlenecks(
            self,
            prompt_dict: dict,
            env: BaseEnv,
            positive_result: str,
            negative_result: str,
        ) -> list[list[int, str, str, str]]:
        env.reset()

        # Load data
        prompt_dict["instance_data"] = filter_dict_to_str(env.instance_data)
        prompt_dict["instance_problem_state"] = filter_dict_to_str(self.get_instance_problem_state(env.instance_data))

        # Load solution
        positive_result = parse_text_to_dict(positive_result)
        negative_result = parse_text_to_dict(negative_result)
        prompt_dict["positive_solution"] = positive_result["current_solution"]
        prompt_dict["negative_solution"] = negative_result["current_solution"]
        prompt_dict["positive_result"] = positive_result[env.key_item]
        prompt_dict["negative_result"] = negative_result[env.key_item]
        prompt_dict["positive_trajectory"] = positive_result["trajectory"]
        prompt_dict["negative_trajectory"] = negative_result["trajectory"]

        # Identify bottleneck operations
        self.llm_client.load("identify_bottleneck", prompt_dict)
        response = self.llm_client.chat()
        bottleneck_operation_strs = extract(response, key="bottleneck_operations", sep="\n")
        self.llm_client.dump("bottleneck_operations")

        bottlenecks = []
        for bottleneck_operation_str in bottleneck_operation_strs:
            # Reproduce the state before bottleneck
            parts = bottleneck_operation_str.split(";", maxsplit=2)
            if len(parts) != 3:
                _LOGGER.warning("[EVOLVE] skipping malformed bottleneck line: %s", bottleneck_operation_str)
                continue
            bottleneck_operation_id, proposed_operation, reason = [part.strip() for part in parts]
            match = re.search(r'\d+', bottleneck_operation_id)
            if match is None:
                _LOGGER.warning("[EVOLVE] skipping bottleneck line without operation id: %s", bottleneck_operation_str)
                continue
            bottleneck_operation_id = int(match.group())
            bottlenecks.append([bottleneck_operation_id, proposed_operation, reason])

        return bottlenecks

    def raise_suggestion(
        self,
        prompt_dict: dict,
        env: BaseEnv,
        bottleneck_operation_id: int,
        proposed_operation: str,
        reason: str,
        suggestion_name: str,
        smoke_test: bool,
    ) -> tuple[str, str, list[float] | None]:
        env.reset()
        self.llm_client.load_chat("bottleneck_operations")
        prompt_dict["bottleneck_operation_id"] = bottleneck_operation_id
        prompt_dict["proposed_operation"] = proposed_operation
        prompt_dict["reason"] = reason
        negative_trajectory_df = pd.read_csv(StringIO(prompt_dict["negative_trajectory"]), sep="\t")
        matching_operations = list(negative_trajectory_df[negative_trajectory_df["operation_id"] == bottleneck_operation_id]["operator"])
        if not matching_operations:
            _LOGGER.warning("[EVOLVE] bottleneck operation id %s not found in trajectory", bottleneck_operation_id)
            return None, None, None
        bottleneck_operation = matching_operations[0]

        for previous_operation in negative_trajectory_df[negative_trajectory_df["operation_id"] < bottleneck_operation_id]["operator"]:
            env.run_operator(eval(previous_operation))
        prompt_dict["bottleneck_operation"] = bottleneck_operation
        prompt_dict["solution_before_bottleneck"] = str(env.current_solution)
        prompt_dict["solution_problem_state_before_bottleneck"] = filter_dict_to_str(self.get_solution_problem_state(env.instance_data, env.current_solution))

        # Try to provide suggestion
        self.llm_client.load("extract_suggestion", prompt_dict)
        response = self.llm_client.chat()
        suggestion = extract(response, key="suggestion")
        if suggestion:
            self.llm_client.dump(suggestion_name)
            # Implement the new code
            heuristic_name = prompt_dict["heuristic_name"]
            origin_function_name = prompt_dict["function_name"]
            prompt_dict["suggestion"] = suggestion
            description = f"Now, based on these suggestions:\n{suggestion}\nUpdate the {origin_function_name}."
            env_summarize = prompt_dict["env_summarize"]
            output_heuristic_file = HeuristicGenerator(self.llm_client, self.problem).generate(heuristic_name, description, env_summarize, smoke_test)
            if output_heuristic_file:
                suggested_result = self.validation(self.validation_cases, output_heuristic_file)
                if suggested_result is None or any(r is None for r in suggested_result):
                    _LOGGER.warning("[EVOLVE] candidate %s failed validation, rejected", os.path.basename(output_heuristic_file))
                    return None, None, None
                return output_heuristic_file, suggestion, suggested_result
        return None, None, None

    def refine_heuristic(
        self,
        prompt_dict: dict,
        env: BaseEnv,
        basic_heuristic_name: str,
        basic_heuristic_result: list[float],
        previous_heuristic_name: str,
        previous_heuristic_result: list[float],
        last_heuristic_name: str,
        last_heuristic_result: list[float],
        last_suggestion: str,
        suggestion_name: str,
        smoke_test: bool = True,
    ) -> tuple[str, str, list[float] | None]:
        # Compare benchmark table
        benchmark_df = self.instance_problem_states_df.copy()
        benchmark_df[basic_heuristic_name] = basic_heuristic_result
        previous_improvement = self.get_improvement(env, basic_heuristic_result, previous_heuristic_result)
        benchmark_df[previous_heuristic_name] = [f"{previous_heuristic_result[index]}({previous_improvement[index]})" for index in range(len(basic_heuristic_result))]
        last_improvement = self.get_improvement(env, basic_heuristic_result, last_heuristic_result)
        benchmark_df[last_heuristic_name] = [f"{last_heuristic_result[index]}({last_improvement[index]})" for index in range(len(basic_heuristic_result))]
        # Compare the evolved result in validation data.
        problem_state_num = self.instance_problem_states_df.shape[-1]
        if env.compare(1, 2) > 0:
            compare = "lower"
        else:
            compare = "higher"
        prompt_dict["problem_state_num"] = problem_state_num
        prompt_dict["basic_heuristic_name"] = basic_heuristic_name
        prompt_dict["previous_heuristic_name"] = previous_heuristic_name
        prompt_dict["last_heuristic_name"] = last_heuristic_name
        prompt_dict["last_suggestion"] = last_suggestion
        prompt_dict["compare"] = compare
        prompt_dict["benchmark_result"] = df_to_str(benchmark_df)

        self.llm_client.load("refinement", prompt_dict)
        response = self.llm_client.chat()
        analysis_results = extract(response, key="refinement", sep="\n")
        self.llm_client.dump(suggestion_name)
        suggestion = None
        for analysis_result in analysis_results:
            if "code adjustment suggestion" in analysis_result:
                suggestion = analysis_result.split(":")[-1]

        if suggestion:
            # Implement the new code
            heuristic_name = prompt_dict["heuristic_name"]
            prompt_dict["suggestion"] = suggestion
            description = f"Now, based on these suggestions:\n{suggestion}\nUpdate the {last_heuristic_name}."
            env_summarize = prompt_dict["env_summarize"]
            output_heuristic_file = HeuristicGenerator(self.llm_client, self.problem).generate(heuristic_name, description, env_summarize, smoke_test, reminder=True)
            if output_heuristic_file:
                output_heuristic_name = output_heuristic_file.split(os.sep)[-1].split(".")[0]
                self.llm_client.dump(f"{previous_heuristic_name}_to_{output_heuristic_name}")
                suggested_heuristic_result = self.validation(self.validation_cases, output_heuristic_file)
                if suggested_heuristic_result is None or any(r is None for r in suggested_heuristic_result):
                    _LOGGER.warning("[EVOLVE] refined candidate %s failed validation, rejected", os.path.basename(output_heuristic_file))
                    return None, None, None
                return output_heuristic_file, suggestion, suggested_heuristic_result
        return None, None, None

    def validation(
        self,
        validation_cases: list[str],
        heuristic_file: str,
        case_timeout_seconds: float = DEFAULT_VALIDATION_CASE_TIMEOUT_SECONDS,
        candidate_timeout_seconds: float = DEFAULT_VALIDATION_CANDIDATE_TIMEOUT_SECONDS,
    ) -> list[float] | None:
        candidate_deadline = time.monotonic() + candidate_timeout_seconds
        validation_results = []
        for data_name in validation_cases:
            remaining = candidate_deadline - time.monotonic()
            if remaining <= 0:
                _LOGGER.warning(
                    "[EVOLVE] candidate %s total validation deadline reached (%.1fs)",
                    os.path.basename(heuristic_file),
                    candidate_timeout_seconds,
                )
                return None
            timeout = min(case_timeout_seconds, remaining)
            result = _run_validation_case_with_timeout(
                self.problem,
                data_name,
                heuristic_file,
                timeout,
            )
            if result is None:
                _LOGGER.warning(
                    "[EVOLVE] candidate %s failed validation case %s (fail-fast triggered)",
                    os.path.basename(heuristic_file),
                    os.path.basename(data_name),
                )
                return None
            validation_results.append(result)
        return validation_results

    def mean_improvement(self, env: BaseEnv, baselines: list[float], results: list[float]) -> float:
        improvements = self.get_improvement(env, baselines, results)
        return sum(improvements) / len(improvements) if improvements else 0.0

    def get_improvement(self, env: BaseEnv, baselines: list[float], results: list[float]) -> list[float]:
        if results is None or any(r is None or not math.isfinite(r) for r in results):
            raise InvalidValidationResult("Invalid validation result reached fitness calculation layer")
        if baselines is None or any(b is None or not math.isfinite(b) for b in baselines):
            raise InvalidValidationResult("Invalid baseline result reached fitness calculation layer")
        if len(results) != len(baselines):
            raise InvalidValidationResult(f"Length mismatch: {len(results)} results vs {len(baselines)} baselines")

        improvements = []
        for r, b in zip(results, baselines):
            if b == 0:
                improvements.append(0.0)
            else:
                diff = env.compare(r, b)
                improvements.append(round(diff / b, 4))
        return improvements

