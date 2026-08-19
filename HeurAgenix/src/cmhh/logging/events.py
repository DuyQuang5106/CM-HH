from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EventRecord:
    """Standardized event-sourced log record in CMHH (schema_version = 1)."""
    event: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    task_id: str | None = None
    run_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        result = {
            "timestamp": self.timestamp,
            "event": self.event,
            "schema_version": self.schema_version,
        }
        if self.task_id is not None:
            result["task_id"] = self.task_id
        if self.run_id is not None:
            result["run_id"] = self.run_id
        result.update(self.payload)
        return result

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EventRecord":
        raw_copy = dict(raw)
        event = raw_copy.pop("event")
        timestamp = raw_copy.pop("timestamp", datetime.now(timezone.utc).isoformat())
        task_id = raw_copy.pop("task_id", None)
        run_id = raw_copy.pop("run_id", None)
        schema_version = raw_copy.pop("schema_version", 1)
        return cls(
            event=event,
            timestamp=timestamp,
            task_id=task_id,
            run_id=run_id,
            payload=raw_copy,
            schema_version=schema_version,
        )


class EventWriter:
    """Atomic line-delimited JSON writer for CMHH event records."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write_event(self, record: EventRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
