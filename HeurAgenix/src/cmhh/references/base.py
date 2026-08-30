from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cmhh.data.manifest import sha256_file
from cmhh.data.references import ReferenceRecord


@dataclass(frozen=True)
class SolverConfig:
    timeout_seconds: float = 300.0
    max_workers: int = 4
    solver_name: str = "default"
    proven_optimal: bool = False
    seed: int = 1
    num_workers: int = 1
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReferenceResult:
    instance_id: str
    objective: float | None
    status: str  # "optimal" | "best_known" | "failed"
    solver: str
    instance_sha256: str
    runtime_seconds: float
    proven_optimal: bool = False
    best_bound: float | None = None
    tour_path: str | None = None
    solver_exit_code: int | None = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_reference_record(self) -> ReferenceRecord:
        if self.proven_optimal:
            status = "optimal"
        elif self.status in ("optimal", "best_known", "failed"):
            status = self.status
        elif self.status == "proven_optimal":
            status = "optimal"
        elif self.objective is not None and self.status not in ("failed", "timeout", "crash", "error"):
            status = "best_known"
        else:
            status = "failed"

        return ReferenceRecord(
            instance_id=self.instance_id,
            objective=float(self.objective) if self.objective is not None else float("nan"),
            status=status,
            solver=self.solver,
            instance_sha256=self.instance_sha256,
            runtime_seconds=self.runtime_seconds,
            tour_path=self.tour_path,
            solver_exit_code=self.solver_exit_code,
            metadata=self.metadata,
        )


class ReferenceSolverAdapter(ABC):
    @property
    @abstractmethod
    def problem_name(self) -> str:
        ...

    @abstractmethod
    def solve(self, instance_path: Path, config: SolverConfig) -> ReferenceResult:
        ...

