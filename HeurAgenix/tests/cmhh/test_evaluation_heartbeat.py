from __future__ import annotations

import logging
from unittest.mock import MagicMock
from cmhh.evaluation.evaluator import Evaluator
from cmhh.models import EvaluationBudget, HeuristicArtifact
from cmhh.tasks import TaskSpec, TaskSplits, TaskReference, TaskMetric


def test_evaluator_heartbeat_log_emitted(caplog) -> None:
    caplog.set_level(logging.INFO)
    budget = EvaluationBudget(instance_timeout_seconds=5.0, batch_timeout_seconds=10.0)
    evaluator = Evaluator(repo_root=".", budget=budget, heartbeat_interval=0.01)

    # Mock discover_instances to return 3 dummy paths
    mock_instance = MagicMock()
    mock_instance.stem = "inst_1"

    evaluator._load_references = MagicMock(return_value=None)
    evaluator._evaluate_instance = MagicMock(return_value=MagicMock(
        status="ok",
        instance_id="inst_1",
        objective=10.0,
        relative_gap=0.1,
    ))

    task = MagicMock()
    task.task_id = "test_task"
    task.problem = "tsp"
    task.splits.validation.exists.return_value = True

    from cmhh.evaluation.problem_adapter import ProblemRegistry
    mock_adapter = MagicMock()
    mock_adapter.discover_instances.return_value = [mock_instance, mock_instance]

    with unittest_mock_adapter(mock_adapter):
        artifact = MagicMock()
        artifact.heuristic_id = "heur_1"
        result = evaluator.evaluate(artifact, task, "validation")
        assert result.heuristic_id == "heur_1"

    log_text = caplog.text
    assert "[EVAL] started" in log_text
    assert "[EVAL] complete" in log_text


from contextlib import contextmanager
@contextmanager
def unittest_mock_adapter(adapter):
    from cmhh.evaluation.problem_adapter import ProblemRegistry
    orig = ProblemRegistry._adapters.get("tsp")
    ProblemRegistry._adapters["tsp"] = adapter
    try:
        yield
    finally:
        if orig:
            ProblemRegistry._adapters["tsp"] = orig
        else:
            ProblemRegistry._adapters.pop("tsp", None)
