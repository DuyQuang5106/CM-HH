from __future__ import annotations

import src.pipeline.heuristic_evolver as heuristic_evolver
from cmhh.llm.budgeted_client import LLMBudgetExceeded
from src.pipeline.heuristic_evolver import HeuristicEvolver


def test_evolve_stops_immediately_when_llm_budget_is_exhausted(monkeypatch) -> None:
    evolver = HeuristicEvolver.__new__(HeuristicEvolver)
    evolver.problem = "tsp"
    evolver.evolution_cases = ["case_a", "case_b"]

    monkeypatch.setattr(heuristic_evolver, "_heuristic_docs", lambda *_args: "")

    calls = {"count": 0}

    def evolution_single(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return [("candidate.py", 2.0)]
        raise LLMBudgetExceeded("LLM call budget exhausted (200)")

    evolver.evolution_single = evolution_single

    result = evolver.evolve(
        "basic.py",
        "perturbation.py",
        filtered_num=2,
        evolution_round=10,
    )

    assert calls["count"] == 2
    assert result == [("candidate.py", 2.0), ("basic.py", 0)]


def test_identity_bottlenecks_skips_malformed_lines_and_preserves_reason_semicolons() -> None:
    class FakeLLMClient:
        def load(self, *_args, **_kwargs):
            pass

        def chat(self):
            return (
                "***bottleneck_operations:\n"
                "operation 12; InsertOperator(node=2); reason contains ; an extra semicolon\n"
                "operation x; SwapOperator(); missing numeric id\n"
                "not enough fields\n"
                "***"
            )

        def dump(self, *_args, **_kwargs):
            pass

    class FakeEnv:
        key_item = "current_cost"
        instance_data = {"node_num": 3}

        def reset(self):
            pass

    evolver = HeuristicEvolver.__new__(HeuristicEvolver)
    evolver.llm_client = FakeLLMClient()
    evolver.get_instance_problem_state = lambda _data: {}

    result = evolver.identity_bottlenecks(
        prompt_dict={},
        env=FakeEnv(),
        positive_result="-current_solution:\n[1, 2, 3]\n-current_cost: 10\n-trajectory:\noperation_id\toperator\n12\tInsertOperator(node=2)",
        negative_result="-current_solution:\n[1, 3, 2]\n-current_cost: 12\n-trajectory:\noperation_id\toperator\n12\tInsertOperator(node=1)",
    )

    assert result == [[12, "InsertOperator(node=2)", "reason contains ; an extra semicolon"]]


def test_get_improvement_handles_none_zero_and_short_results() -> None:
    class FakeEnv:
        def compare(self, result, baseline):
            return baseline - result

    evolver = HeuristicEvolver.__new__(HeuristicEvolver)

    assert evolver.get_improvement(
        FakeEnv(),
        baselines=[10.0, None, 0, 5.0, 7.0],
        results=[8.0, 1.0, 1.0, None],
    ) == [0.2, 0, 0, 0, 0]


def test_validation_uses_per_instance_timeout(monkeypatch) -> None:
    evolver = HeuristicEvolver.__new__(HeuristicEvolver)
    evolver.problem = "tsp"
    calls = []

    def fake_run(problem, data_name, heuristic_file, timeout_seconds):
        calls.append((problem, data_name, heuristic_file, timeout_seconds))
        return 123.0

    monkeypatch.setattr(heuristic_evolver, "_run_validation_case_with_timeout", fake_run)

    assert evolver.validation(["case_a", "case_b"], "heuristic.py", timeout_seconds=3.5) == [123.0, 123.0]
    assert calls == [
        ("tsp", "case_a", "heuristic.py", 3.5),
        ("tsp", "case_b", "heuristic.py", 3.5),
    ]
