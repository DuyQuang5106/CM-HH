from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HeuristicArtifact:
    heuristic_id: str
    problem: str
    code_path: Path
    code_hash: str
    strategy: str | None = None
    parent_ids: tuple[str, ...] = ()
    generation: int = 0
    task_id: str | None = None
    prompt_hash: str | None = None
    model: str | None = None
    llm_call_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["code_path"] = str(self.code_path)
        return raw


@dataclass(frozen=True)
class InstanceEvaluation:
    instance_id: str
    status: str
    objective: float | None
    reference_objective: float | None
    reference_status: str | None
    relative_gap: float | None
    runtime_seconds: float
    error: str | None = None


@dataclass(frozen=True)
class EvaluationResult:
    heuristic_id: str
    task_id: str
    split: str
    instances: tuple[InstanceEvaluation, ...]

    @property
    def successful(self) -> tuple[InstanceEvaluation, ...]:
        return tuple(item for item in self.instances if item.status == "ok")

    @property
    def failure_rate(self) -> float:
        if not self.instances:
            return 0.0
        return 1.0 - len(self.successful) / len(self.instances)

    @property
    def mean_relative_gap(self) -> float | None:
        gaps = [item.relative_gap for item in self.successful if item.relative_gap is not None]
        return sum(gaps) / len(gaps) if gaps else None

    @property
    def mean_score(self) -> float | None:
        gap = self.mean_relative_gap
        return -gap if gap is not None else None


@dataclass(frozen=True)
class SearchBudget:
    generations: int
    candidates_per_generation: int
    max_llm_calls: int


@dataclass(frozen=True)
class EvaluationBudget:
    instance_timeout_seconds: float
    batch_timeout_seconds: float
    invalid_policy: str = "fail_batch"


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    seed: int
    task_ids: tuple[str, ...]
    search: SearchBudget
    evaluation: EvaluationBudget
    metadata: dict[str, Any] = field(default_factory=dict)
