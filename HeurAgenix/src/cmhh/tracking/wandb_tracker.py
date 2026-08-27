from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_git_commit_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


class WandbTracker:
    """Weights & Biases (wandb) experiment tracker with graceful error fallback."""

    def __init__(
        self,
        project: str = "cmhh",
        entity: str | None = None,
        mode: str = "online",
        tags: tuple[str, ...] | list[str] = (),
        run_name: str | None = None,
        run_id: str | None = None,
        run_dir: str | Path | None = None,
        notes: str | None = None,
        extra_config: dict[str, Any] | None = None,
    ) -> None:
        self.project = project
        self.entity = entity
        self.mode = mode
        self.tags = list(tags)
        self.run_name = run_name or run_id
        self.run_id = run_id
        self.run_dir = Path(run_dir) if run_dir else None
        self._wandb = None
        self._run = None
        self._enabled = False

        if mode == "disabled":
            return

        try:
            import wandb

            self._wandb = wandb
            init_kwargs: dict[str, Any] = {
                "project": self.project,
                "mode": self.mode,
                "name": self.run_name,
                "tags": self.tags,
                "reinit": True,
            }
            if self.entity:
                init_kwargs["entity"] = self.entity
            if self.run_id:
                init_kwargs["id"] = self.run_id
                init_kwargs["resume"] = "allow"
            if notes:
                init_kwargs["notes"] = notes

            initial_config = {
                "local_run_id": self.run_id,
                "git_commit": _get_git_commit_hash(),
            }
            if extra_config:
                initial_config.update(extra_config)
            init_kwargs["config"] = initial_config

            self._run = wandb.init(**init_kwargs)
            self._enabled = True
        except Exception as exc:
            logger.warning(
                "Weights & Biases initialization failed (%s). Continuing run without W&B tracking.",
                exc,
            )
            self._enabled = False

    def log_config(self, config: dict[str, Any]) -> None:
        if not self._enabled or not self._run:
            return
        try:
            self._run.config.update(config, allow_val_change=True)
        except Exception as exc:
            logger.warning("W&B log_config failed: %s", exc)

    def log_metrics(self, metrics: dict[str, Any], step: int | None = None) -> None:
        if not self._enabled or not self._wandb:
            return
        try:
            payload = {}
            for key, val in metrics.items():
                if isinstance(val, (int, float, bool, str)) or val is None:
                    payload[key] = val
            if payload:
                if step is not None:
                    self._wandb.log(payload, step=step)
                else:
                    self._wandb.log(payload)
        except Exception as exc:
            logger.warning("W&B log_metrics failed: %s", exc)

    def log_event(self, event: str, payload: dict[str, Any] | None = None, step: int | None = None) -> None:
        if not self._enabled or not self._wandb:
            return
        try:
            data = {"event": event}
            if payload:
                for k, v in payload.items():
                    if isinstance(v, (int, float, bool, str)):
                        data[f"event/{k}"] = v
            if step is not None:
                self._wandb.log(data, step=step)
            else:
                self._wandb.log(data)
        except Exception as exc:
            logger.warning("W&B log_event failed: %s", exc)

    def log_performance_matrix(
        self,
        matrix: dict[int, dict[int, float]],
        task_ids: tuple[str, ...] | list[str],
    ) -> None:
        if not self._enabled or not self._wandb:
            return
        try:
            columns = ["evaluated_after_task", *task_ids]
            data = []
            for row_idx in range(len(task_ids)):
                row_data = [task_ids[row_idx]]
                for col_idx in range(len(task_ids)):
                    val = matrix.get(row_idx, {}).get(col_idx)
                    row_data.append(val if val is not None else float("nan"))
                data.append(row_data)

            table = self._wandb.Table(columns=columns, data=data)
            self._wandb.log({"continual/performance_matrix_table": table})
        except Exception as exc:
            logger.warning("W&B log_performance_matrix failed: %s", exc)

    def log_summary(self, summary: dict[str, Any]) -> None:
        if not self._enabled or not self._run:
            return
        try:
            for key, value in summary.items():
                if isinstance(value, (int, float, bool, str)):
                    self._run.summary[key] = value
        except Exception as exc:
            logger.warning("W&B log_summary failed: %s", exc)

    def finish(self, exit_code: int = 0) -> None:
        if not self._enabled or not self._wandb:
            return
        try:
            self._wandb.finish(exit_code=exit_code)
        except Exception as exc:
            logger.warning("W&B finish failed: %s", exc)
        finally:
            self._enabled = False
            self._run = None
