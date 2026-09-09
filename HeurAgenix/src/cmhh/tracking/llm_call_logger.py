from __future__ import annotations

import json
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _fallback_warning(exc: Exception, message: str = "") -> None:
    """Fallback notification channel on non-fatal observability sink errors (Contract D9)."""
    try:
        prefix = f" [CMHH OBS FAIL] {message}: " if message else " [CMHH OBS FAIL] "
        sys.stderr.write(f"{prefix}{type(exc).__name__}: {exc}\n")
        sys.stderr.flush()
    except Exception:
        pass


@dataclass
class LLMCallRecord:
    """Structured record for a physical LLM request attempt (schema_version = 1)."""
    event: str = "llm_attempt"
    schema_version: int = 1
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    call_id: str | None = None
    worker_id: str | None = None
    attempt: int = 1
    model: str | None = None
    backend: str | None = None
    status_code: int | None = None
    reason: str | None = None
    latency_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    success: bool = True
    error_type: str | None = None
    error_message: str | None = None
    task_id: str | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        if self.prompt_tokens is not None and self.input_tokens is None:
            self.input_tokens = self.prompt_tokens
        elif self.input_tokens is not None and self.prompt_tokens is None:
            self.prompt_tokens = self.input_tokens

        if self.completion_tokens is not None and self.output_tokens is None:
            self.output_tokens = self.completion_tokens
        elif self.output_tokens is not None and self.completion_tokens is None:
            self.completion_tokens = self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMCallLogger:
    """Thread-safe and failure-isolated writer for llm_calls.jsonl."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def log_attempt(self, record: LLMCallRecord) -> None:
        """Write one physical attempt record under strict D9 failure isolation."""
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fp:
                    fp.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
        except Exception as exc:
            _fallback_warning(exc, f"Failed to write record to {self.path}")

    def load_all(self) -> list[dict[str, Any]]:
        """Load and return all recorded attempts from disk."""
        if not self.path.exists():
            return []
        try:
            with self._lock:
                with self.path.open("r", encoding="utf-8") as fp:
                    return [json.loads(line) for line in fp if line.strip()]
        except Exception as exc:
            _fallback_warning(exc, f"Failed to read records from {self.path}")
            return []

    def flush(self) -> None:
        # File open('a') within lock flushes per write, but method exists for shutdown protocol
        pass


_ACTIVE_LLM_LOGGERS: dict[str, LLMCallLogger] = {}
_ACTIVE_LLM_LOGGERS_LOCK = threading.Lock()


def get_llm_call_logger(path: str | Path | None) -> LLMCallLogger | None:
    if path is None:
        return None
    key = str(Path(path).resolve())
    with _ACTIVE_LLM_LOGGERS_LOCK:
        if key not in _ACTIVE_LLM_LOGGERS:
            _ACTIVE_LLM_LOGGERS[key] = LLMCallLogger(key)
        return _ACTIVE_LLM_LOGGERS[key]
