from __future__ import annotations

from typing import Any


class NoOpTracker:
    """Safe no-op implementation of ExperimentTracker when tracking is disabled."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def log_config(self, config: dict[str, Any]) -> None:
        pass

    def log_metrics(self, metrics: dict[str, Any], step: int | None = None) -> None:
        pass

    def log_event(self, event: str, payload: dict[str, Any] | None = None, step: int | None = None) -> None:
        pass

    def log_performance_matrix(
        self,
        matrix: dict[int, dict[int, float]],
        task_ids: tuple[str, ...] | list[str],
    ) -> None:
        pass

    def log_summary(self, summary: dict[str, Any]) -> None:
        pass

    def finish(self, exit_code: int = 0) -> None:
        pass
