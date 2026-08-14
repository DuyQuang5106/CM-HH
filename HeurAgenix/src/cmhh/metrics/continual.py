from __future__ import annotations

from collections.abc import Mapping


PerformanceMatrix = Mapping[int, Mapping[int, float]]


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
