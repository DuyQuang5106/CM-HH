from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from cmhh.data.manifest import write_json_atomic
from cmhh.models import EvaluationResult


def write_evaluation(path: str | Path, result: EvaluationResult) -> None:
    write_json_atomic(path, {
        "heuristic_id": result.heuristic_id,
        "task_id": result.task_id,
        "split": result.split,
        "mean_relative_gap": result.mean_relative_gap,
        "mean_score": result.mean_score,
        "failure_rate": result.failure_rate,
        "instances": [asdict(item) for item in result.instances],
    })


def print_evaluation_summary(result: EvaluationResult) -> None:
    print(json.dumps({
        "task_id": result.task_id,
        "heuristic_id": result.heuristic_id,
        "split": result.split,
        "mean_relative_gap": result.mean_relative_gap,
        "failure_rate": result.failure_rate,
    }, sort_keys=True))
