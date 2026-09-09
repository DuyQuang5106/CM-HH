from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from cmhh.tracking.base import ExperimentTracker
from cmhh.tracking.console_formatter import ConsoleFormatter
from cmhh.tracking.context import (
    RunLogContext,
    context_from_env,
    context_to_env,
    get_current_context,
    set_current_context,
    update_current_context,
)
from cmhh.tracking.llm_call_logger import LLMCallLogger, LLMCallRecord, get_llm_call_logger
from cmhh.tracking.logging_config import configure_logging, shutdown_logging
from cmhh.tracking.noop_tracker import NoOpTracker
from cmhh.tracking.redaction import SecretRedactionFilter, redact_secrets
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


__all__ = [
    "ExperimentTracker",
    "NoOpTracker",
    "WandbTracker",
    "create_tracker",
    "configure_logging",
    "shutdown_logging",
    "ConsoleFormatter",
    "SecretRedactionFilter",
    "redact_secrets",
    "RunLogContext",
    "get_current_context",
    "set_current_context",
    "update_current_context",
    "context_to_env",
    "context_from_env",
    "LLMCallLogger",
    "LLMCallRecord",
    "get_llm_call_logger",
]

