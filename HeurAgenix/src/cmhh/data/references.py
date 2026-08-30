from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from cmhh.data.manifest import load_json, write_json_atomic


@dataclass(frozen=True)
class ReferenceRecord:
    instance_id: str
    objective: float
    status: str
    solver: str
    instance_sha256: str
    runtime_seconds: float
    tour_path: str | None = None
    solver_exit_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ReferenceRecord":
        return cls(
            instance_id=raw["instance_id"],
            objective=float(raw["objective"]) if raw.get("objective") is not None else float("nan"),
            status=raw.get("status", "best_known"),
            solver=raw.get("solver", "unknown"),
            instance_sha256=raw.get("instance_sha256", ""),
            runtime_seconds=float(raw.get("runtime_seconds", 0.0)),
            tour_path=raw.get("tour_path"),
            solver_exit_code=raw.get("solver_exit_code"),
            metadata=raw.get("metadata", {}),
        )


@dataclass(frozen=True)
class ReferenceSet:
    task_id: str
    records: tuple[ReferenceRecord, ...]

    def get_optional(self, instance_id: str) -> ReferenceRecord | None:
        for record in self.records:
            if record.instance_id == instance_id:
                return record
        return None


def load_reference_set(path: str | Path) -> ReferenceSet:
    raw = load_json(path)
    if isinstance(raw, list):
        task_id = Path(path).stem
        records = raw
    else:
        task_id = raw.get("task_id", Path(path).stem)
        records = raw.get("records", [])
    return ReferenceSet(
        task_id=task_id,
        records=tuple(ReferenceRecord.from_dict(item) for item in records),
    )


def write_reference_set(
    path: str | Path,
    task_id: str,
    records: list[ReferenceRecord],
) -> None:
    ordered = sorted(records, key=lambda item: item.instance_id)
    write_json_atomic(path, {
        "task_id": task_id,
        "records": [asdict(record) for record in ordered],
    })
