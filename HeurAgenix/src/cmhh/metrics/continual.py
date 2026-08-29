from __future__ import annotations

from collections.abc import Mapping


PerformanceMatrix = Mapping[int, Mapping[int, float]]
ScoreMap = Mapping[int, float | None]


def average_final_performance(matrix: PerformanceMatrix, task_count: int) -> float:
    final = matrix[task_count - 1]
    return sum(final[j] for j in range(task_count)) / task_count


def backward_transfer(matrix: PerformanceMatrix, task_count: int) -> float:
    if task_count < 2:
        raise ValueError("BWT requires at least two tasks")
    final = matrix[task_count - 1]
    return sum(final[j] - matrix[j][j] for j in range(task_count - 1)) / (task_count - 1)


def forward_transfer(
    matrix: PerformanceMatrix,
    cold_start_scores: Mapping[int, float],
    task_count: int,
) -> float:
    if task_count < 2:
        raise ValueError("FWT requires at least two tasks")
    return sum(matrix[k][k] - cold_start_scores[k] for k in range(1, task_count)) / (task_count - 1)


def zero_shot_forward_transfer(
    pre_learning_scores: ScoreMap,
    cold_start_scores: Mapping[int, float],
    task_count: int,
) -> float | None:
    """FWT from executable pre-learning probes Z_k, skipping unavailable probes."""
    if task_count < 2:
        raise ValueError("FWT requires at least two tasks")
    deltas = []
    for k in range(1, task_count):
        zero_shot = pre_learning_scores.get(k)
        cold_start = cold_start_scores.get(k)
        if zero_shot is None or cold_start is None:
            continue
        deltas.append(float(zero_shot) - float(cold_start))
    return sum(deltas) / len(deltas) if deltas else None
