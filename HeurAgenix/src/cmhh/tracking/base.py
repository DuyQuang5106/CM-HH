from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExperimentTracker(Protocol):
    """Protocol defining the experiment tracking interface in CM-HH."""

    def log_config(self, config: dict[str, Any]) -> None:
        """Log run-level configuration metadata."""
        ...

    def log_metrics(self, metrics: dict[str, Any], step: int | None = None) -> None:
        """Log point-in-time metrics for a given step/epoch/task index."""
        ...

    def log_event(self, event: str, payload: dict[str, Any] | None = None, step: int | None = None) -> None:
        """Log a notable event during stream execution."""
        ...

    def log_performance_matrix(
        self,
        matrix: dict[int, dict[int, float]],
        task_ids: tuple[str, ...] | list[str],
    ) -> None:
        """Log the continual learning performance matrix A[k, j]."""
        ...

    def log_summary(self, summary: dict[str, Any]) -> None:
        """Log final run summary metrics (BWT, FWT, average performance, etc.)."""
        ...

    def finish(self, exit_code: int = 0) -> None:
        """Close the tracking session and flush any pending telemetry."""
        ...
