from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from cmhh.tracking.base import ExperimentTracker
from cmhh.tracking.noop_tracker import NoOpTracker
from cmhh.tracking.wandb_tracker import WandbTracker

if TYPE_CHECKING:
    from cmhh.config import TrackingConfig


def create_tracker(
    config: TrackingConfig | None = None,
    run_id: str | None = None,
    run_dir: str | Path | None = None,
    stream_id: str = "",
    experiment_name: str = "",
    extra_config: dict[str, Any] | None = None,
) -> ExperimentTracker:
    """Factory creating an appropriate ExperimentTracker based on configuration."""
    if config is None or not config.wandb.enabled or config.wandb.mode == "disabled":
        return NoOpTracker()

    wb = config.wandb
    run_name = wb.run_name or (
        f"{experiment_name}__{stream_id}__{run_id}" if experiment_name and stream_id else run_id
    )

    return WandbTracker(
        project=wb.project,
        entity=wb.entity,
        mode=wb.mode,
        tags=wb.tags,
        run_name=run_name,
        run_id=run_id,
        run_dir=run_dir,
        extra_config=extra_config,
    )


__all__ = ["ExperimentTracker", "NoOpTracker", "WandbTracker", "create_tracker"]
