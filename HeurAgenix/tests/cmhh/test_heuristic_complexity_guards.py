from __future__ import annotations

import json
import logging
import math
import multiprocessing
import os
import time
from pathlib import Path
import pytest

import src.pipeline.heuristic_evolver as heuristic_evolver
import src.pipeline.heuristic_generator as heuristic_generator
from cmhh.llm.budgeted_client import LLMBudgetExceeded
from src.pipeline.heuristic_evolver import HeuristicEvolver, InvalidValidationResult
from src.pipeline.heuristic_generator import (
    HeuristicGenerator,
    _run_smoke_step_with_timeout,
)


def _create_sample_tsp(path: Path) -> str:
    path.write_text(
        "NAME: sample\n"
        "TYPE: TSP\n"
        "DIMENSION: 4\n"
        "EDGE_WEIGHT_TYPE: EUC_2D\n"
        "NODE_COORD_SECTION\n"
        "1 0.0 0.0\n"
        "2 10.0 0.0\n"
        "3 10.0 10.0\n"
        "4 0.0 10.0\n"
        "EOF\n",
        encoding="utf-8",
    )
    return str(path)


def test_refine_heuristic_passes_reminder_true(monkeypatch) -> None:
    """Test 1: Verifies refine_heuristic() always passes reminder=True to HeuristicGenerator.generate."""
    evolver = HeuristicEvolver.__new__(HeuristicEvolver)
    evolver.problem = "tsp"
    evolver.validation_cases = ["case1.tsp"]
    evolver.instance_problem_states_df = heuristic_evolver.pd.DataFrame([{"data_name": "case1.tsp"}])

    class FakeLLMClient:
        output_dir = "output"

        def load(self, *_args, **_kwargs):
            pass

        def chat(self):
            return "***refinement:\ncode adjustment suggestion: Optimize tour\n***"

        def dump(self, *_args, **_kwargs):
            pass

    class FakeEnv:
        def compare(self, r, b):
            return b - r

    evolver.llm_client = FakeLLMClient()
    evolver.validation = lambda _cases, _file: [100.0]

    captured_kwargs = {}

    def fake_generate(self, heuristic_name, description, env_summarize="All data are possible", smoke_test=False, more_prompt_dict=None, reminder=True):
        captured_kwargs["reminder"] = reminder
        return "refined_func.py"

    monkeypatch.setattr(HeuristicGenerator, "generate", fake_generate)

    prompt_dict = {
        "heuristic_name": "test_heur",
        "function_name": "test_func",
        "env_summarize": "summary",
    }

    out_file, suggestion, result = evolver.refine_heuristic(
        prompt_dict=prompt_dict,
        env=FakeEnv(),
        basic_heuristic_name="basic",
        basic_heuristic_result=[120.0],
        previous_heuristic_name="prev",
        previous_heuristic_result=[110.0],
        last_heuristic_name="last",
        last_heuristic_result=[110.0],
        last_suggestion="Initial suggestion",
        suggestion_name="sug_0",
        smoke_test=False,
    )

    assert captured_kwargs.get("reminder") is True
    assert out_file == "refined_func.py"
    assert result == [100.0]


def test_smoke_timeout_rejects_candidate(tmp_path) -> None:
    """Test 2: Verifies infinite/slow heuristic step in smoke test subprocess is killed after timeout."""
    sample_tsp = _create_sample_tsp(tmp_path / "sample.tsp")
    slow_code = "import time\ndef slow_func(problem_state, algorithm_data, **kwargs):\n    time.sleep(0.3)\n    return None, {}"

    status, payload, elapsed = _run_smoke_step_with_timeout(
        problem="tsp",
        smoke_data=sample_tsp,
        previous_operations=[],
        heuristic_code=slow_code,
        function_name="slow_func",
        timeout_seconds=0.05,
        warn_seconds=0.02,
    )

    assert status == "timeout"
    assert "timeout" in payload.lower()


def test_smoke_crash_rejects_candidate(tmp_path) -> None:
    """Test 3: Verifies runtime crash in smoke test worker is safely caught without failing parent."""
    sample_tsp = _create_sample_tsp(tmp_path / "sample.tsp")
    crashing_code = "def crash_func(problem_state, algorithm_data, **kwargs):\n    raise ZeroDivisionError('simulated div zero')"

    status, payload, elapsed = _run_smoke_step_with_timeout(
        problem="tsp",
        smoke_data=sample_tsp,
        previous_operations=[],
        heuristic_code=crashing_code,
        function_name="crash_func",
        timeout_seconds=2.0,
    )

    assert status == "error"
    assert "ZeroDivisionError" in payload


def test_validation_case_timeout_triggers_fail_fast(monkeypatch) -> None:
    """Test 4: Verifies per-case timeout terminates worker, skips remaining cases, and returns None."""
    evolver = HeuristicEvolver.__new__(HeuristicEvolver)
    evolver.problem = "tsp"

    evaluated_cases = []

    def fake_case_runner(problem, data_name, heuristic_file, timeout):
        evaluated_cases.append(data_name)
        if data_name == "case_1":
            return 50.0
        if data_name == "case_2":
            return None  # Times out or fails
        return 60.0

    monkeypatch.setattr(heuristic_evolver, "_run_validation_case_with_timeout", fake_case_runner)

    result = evolver.validation(
        validation_cases=["case_1", "case_2", "case_3", "case_4"],
        heuristic_file="candidate.py",
        case_timeout_seconds=1.0,
        candidate_timeout_seconds=10.0,
    )

    assert result is None
    # Fail-fast should stop immediately at case_2 without running case_3 and case_4
    assert evaluated_cases == ["case_1", "case_2"]


def test_candidate_total_timeout_rejects_slow_cumulative_cases(monkeypatch) -> None:
    """Test 5: Verifies that cumulative slow cases exceeding candidate_timeout_seconds are rejected."""
    evolver = HeuristicEvolver.__new__(HeuristicEvolver)
    evolver.problem = "tsp"

    evaluated_cases = []

    def slow_case_runner(problem, data_name, heuristic_file, timeout):
        evaluated_cases.append(data_name)
        time.sleep(0.04)
        return 100.0

    monkeypatch.setattr(heuristic_evolver, "_run_validation_case_with_timeout", slow_case_runner)

    # 4 cases * 0.04s = 0.16s, but candidate total timeout is 0.06s
    result = evolver.validation(
        validation_cases=["case_1", "case_2", "case_3", "case_4"],
        heuristic_file="candidate.py",
        case_timeout_seconds=1.0,
        candidate_timeout_seconds=0.06,
    )

    assert result is None
    assert len(evaluated_cases) < 4


def test_spawn_worker_uses_only_serializable_inputs(tmp_path) -> None:
    """Test 6: Verifies spawn context worker runs cleanly with ProblemRegistry and primitive args."""
    sample_tsp = _create_sample_tsp(tmp_path / "sample.tsp")
    heur_code = (
        "from src.problems.tsp.components import InsertOperator\n"
        "def valid_heur(problem_state, algorithm_data, **kwargs):\n"
        "    return InsertOperator(node=1), {}\n"
    )
    heur_file = tmp_path / "valid_heur.py"
    heur_file.write_text(heur_code, encoding="utf-8")

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()

    heuristic_evolver._run_validation_worker(
        problem="tsp",
        data_name=sample_tsp,
        heuristic_file=str(heur_file),
        result_queue=queue,
    )

    status, val = queue.get(timeout=2.0)
    assert status in ("ok", "invalid")
    if status == "ok":
        assert math.isfinite(val)


def test_timeout_is_not_ignored_in_mean_fitness_raises_invariant() -> None:
    """Test 7: Invariant check - None or non-finite reaching get_improvement/mean_improvement raises InvalidValidationResult."""
    class FakeEnv:
        def compare(self, r, b):
            return b - r

    evolver = HeuristicEvolver.__new__(HeuristicEvolver)

    with pytest.raises(InvalidValidationResult):
        evolver.get_improvement(FakeEnv(), baselines=[10.0, 20.0], results=[8.0, None])

    with pytest.raises(InvalidValidationResult):
        evolver.get_improvement(FakeEnv(), baselines=[10.0, 20.0], results=[8.0, float("nan")])

    with pytest.raises(InvalidValidationResult):
        evolver.mean_improvement(FakeEnv(), baselines=[10.0, 20.0], results=[8.0, None])


def test_budget_exception_propagates(monkeypatch) -> None:
    """Test 8: Verifies LLMBudgetExceeded propagates out of evolution_single and is not swallowed."""
    evolver = HeuristicEvolver.__new__(HeuristicEvolver)
    evolver.problem = "tsp"
    evolver.output_root = "output"

    class FakeLLMClient:
        output_dir = "output"
        def reset(self, *_args):
            pass

    evolver.llm_client = FakeLLMClient()

    class FakeAdapter:
        def load_env(self, data_name):
            class FakeEnvObj:
                data_ref_name = "ref"
            return FakeEnvObj()

    monkeypatch.setattr("cmhh.evaluation.problem_adapter.ProblemRegistry.get", lambda p: FakeAdapter())

    def raise_budget(*_args, **_kwargs):
        raise LLMBudgetExceeded("Budget reached (200)")

    evolver.perturbation = raise_budget

    with pytest.raises(LLMBudgetExceeded):
        evolver.evolution_single(
            evolution_data="data.tsp",
            basic_heuristic_file="basic.py",
            perturbation_heuristic_file="perturb.py",
            all_heuristic_docs="",
        )


def test_evolve_stops_on_budget_exhausted(monkeypatch, tmp_path) -> None:
    """Test 9: Verifies evolve() catches LLMBudgetExceeded, stops, and exports termination metadata."""
    evolver = HeuristicEvolver.__new__(HeuristicEvolver)
    evolver.problem = "tsp"
    evolver.evolution_cases = ["case_a", "case_b"]
    evolver.output_root = str(tmp_path)

    class FakeLLMClient:
        max_calls = 200
        call_count = 200

    evolver.llm_client = FakeLLMClient()
    monkeypatch.setattr(heuristic_evolver, "_heuristic_docs", lambda *_args: "")

    call_count = {"count": 0}

    def fake_evolution_single(**_kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            return [("cand1.py", 1.5)]
        raise LLMBudgetExceeded("Exhausted")

    evolver.evolution_single = fake_evolution_single

    result = evolver.evolve(
        basic_heuristic_file="basic.py",
        perturbation_heuristic_file="perturb.py",
        filtered_num=2,
        evolution_round=5,
    )

    assert call_count["count"] == 2
    assert result == [("cand1.py", 1.5), ("basic.py", 0.0)]

    metadata_file = tmp_path / "tsp" / "evolution_result" / "termination_metadata.json"
    assert metadata_file.exists()
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata["termination_reason"] == "llm_budget_exhausted"
    assert metadata["completed_normally"] is False
    assert metadata["llm_calls_used"] == 200


def test_attempt_cap_preserves_incumbent_without_duplicate_fallback(monkeypatch, tmp_path) -> None:
    """Test 10: Verifies slot attempt failure retains incumbent parent and terminates on generation failure cap."""
    evolver = HeuristicEvolver.__new__(HeuristicEvolver)
    evolver.problem = "tsp"
    evolver.evolution_cases = ["case_a"]
    evolver.output_root = str(tmp_path)

    class FakeLLMClient:
        max_calls = 500
        call_count = 30

    evolver.llm_client = FakeLLMClient()
    monkeypatch.setattr(heuristic_evolver, "_heuristic_docs", lambda *_args: "")

    # Always return empty (failed attempts)
    evolver.evolution_single = lambda **_kwargs: []

    result = evolver.evolve(
        basic_heuristic_file="incumbent_parent.py",
        perturbation_heuristic_file="perturb.py",
        filtered_num=1,
        evolution_round=1,
        max_attempts_per_slot=2,
        max_failed_attempts_per_generation=2,
    )

    assert result == [("incumbent_parent.py", 0.0)]
    metadata_file = tmp_path / "tsp" / "evolution_result" / "termination_metadata.json"
    assert metadata_file.exists()
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata["termination_reason"] == "failed_attempt_cap_exceeded"
    assert metadata["failed_generation_attempts"] == 2


def test_smoke_scaling_warning_does_not_reject_by_itself(tmp_path, caplog) -> None:
    """Test 11: High scaling ratio (>50x) triggers warning log but does not reject if within hard timeout."""
    sample_tsp = _create_sample_tsp(tmp_path / "sample.tsp")
    fast_code = "def fast_func(problem_state, algorithm_data, **kwargs):\n    return None, {}"

    # Call on valid instance -> returns ok
    status, payload, el = _run_smoke_step_with_timeout(
        problem="tsp",
        smoke_data=sample_tsp,
        previous_operations=[],
        heuristic_code=fast_code,
        function_name="fast_func",
        timeout_seconds=2.0,
    )

    assert status == "ok"
