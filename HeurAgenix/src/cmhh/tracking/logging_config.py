from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Iterable

from cmhh.tracking.console_formatter import ConsoleFormatter
from cmhh.tracking.redaction import SecretRedactionFilter

_CMHH_HANDLER_TAG = "_cmhh_managed_handler"
_NOISY_LOGGERS = (
    "urllib3",
    "requests.packages.urllib3",
    "httpx",
    "httpcore",
    "openai",
    "matplotlib",
    "wandb",
    "asyncio",
)


def _mute_noisy_loggers() -> None:
    for name in _NOISY_LOGGERS:
        noisy_logger = logging.getLogger(name)
        noisy_logger.setLevel(logging.WARNING)


def configure_logging(
    *,
    level: str = "INFO",
    console: bool = True,
    quiet: bool = False,
    run_dir: Path | str | None = None,
    log_dir: Path | str | None = None,
    log_file: Path | str | None = None,
    force_ascii: bool = False,
    extra_secrets: Iterable[str] | None = None,
) -> list[logging.Handler]:
    """Idempotently configure the root and CM-HH logging subsystems and return added handlers."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Clean up existing CM-HH managed handlers to guarantee idempotency
    existing_managed = [
        h for h in root.handlers
        if getattr(h, _CMHH_HANDLER_TAG, False) or getattr(h, "_cmhh_managed", False)
    ]
    for h in existing_managed:
        root.removeHandler(h)
        try:
            h.flush()
            h.close()
        except Exception:
            pass

    redaction_filter = SecretRedactionFilter(extra_secrets=extra_secrets)
    added_handlers: list[logging.Handler] = []

    # 1. Console handler (writes to stderr to keep stdout clean for machine output)
    if console and not quiet:
        console_handler = logging.StreamHandler(sys.stderr)
        setattr(console_handler, _CMHH_HANDLER_TAG, True)
        setattr(console_handler, "_cmhh_managed", True)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(ConsoleFormatter(force_ascii=force_ascii))
        console_handler.addFilter(redaction_filter)
        root.addHandler(console_handler)
        added_handlers.append(console_handler)

    # 2. File handler (run.log)
    resolved_file: Path | None = None
    target_dir = log_dir or run_dir
    if log_file is not None:
        resolved_file = Path(log_file)
    elif target_dir is not None:
        resolved_file = Path(target_dir) / "run.log"

    if resolved_file is not None:
        try:
            resolved_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(resolved_file, encoding="utf-8")
            setattr(file_handler, _CMHH_HANDLER_TAG, True)
            setattr(file_handler, "_cmhh_managed", True)
            file_handler.setLevel(numeric_level)
            file_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            file_handler.addFilter(redaction_filter)
            root.addHandler(file_handler)
            added_handlers.append(file_handler)
        except Exception as exc:
            # Observability Failure Isolation (Contract D9)
            sys.stderr.write(f" [CMHH OBS WARN] Could not open log file {resolved_file}: {exc}\n")

    _mute_noisy_loggers()
    return added_handlers


def shutdown_logging() -> None:
    """Flush and close all CM-HH managed file and stream logging handlers."""
    root = logging.getLogger()
    managed_handlers = [
        h for h in root.handlers
        if getattr(h, _CMHH_HANDLER_TAG, False) or getattr(h, "_cmhh_managed", False)
    ]
    for handler in managed_handlers:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root.removeHandler(handler)
