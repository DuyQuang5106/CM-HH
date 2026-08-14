from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_TASK_REGISTRY = Path("cmhh/configs/tasks/task_registry.yaml")


@dataclass(frozen=True)
class TaskSplits:
    train: Path
    validation: Path
    test: Path
    smoke: Path | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, str], repo_root: Path) -> "TaskSplits":
        return cls(
            train=_resolve_repo_path(raw["train"], repo_root),
            validation=_resolve_repo_path(raw["validation"], repo_root),
            test=_resolve_repo_path(raw["test"], repo_root),
            smoke=_resolve_repo_path(raw["smoke"], repo_root) if raw.get("smoke") else None,
        )


@dataclass(frozen=True)
class TaskReference:
    type: str
    path: Path | None = None
    status: str = "pending"

    @classmethod
    def from_dict(cls, raw: dict[str, str], repo_root: Path) -> "TaskReference":
        return cls(
            type=raw["type"],
            path=_resolve_repo_path(raw["path"], repo_root) if raw.get("path") else None,
            status=raw.get("status", "pending"),
        )


@dataclass(frozen=True)
class TaskMetric:
    name: str
    objective: str
    aggregation: str = "mean"

    @classmethod
    def from_dict(cls, raw: dict[str, str]) -> "TaskMetric":
        return cls(
            name=raw["name"],
            objective=raw["objective"],
            aggregation=raw.get("aggregation", "mean"),
        )


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    problem: str
    size_tier: str
    distribution: str
    splits: TaskSplits
    reference: TaskReference
    metric: TaskMetric
    implemented_in_heuragenix: bool
    baseline_pool: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], repo_root: Path) -> "TaskSpec":
        return cls(
            task_id=raw["task_id"],
            problem=raw["problem"],
            size_tier=raw["size_tier"],
            distribution=raw["distribution"],
            splits=TaskSplits.from_dict(raw["splits"], repo_root),
            reference=TaskReference.from_dict(raw["reference"], repo_root),
            metric=TaskMetric.from_dict(raw["metric"]),
            implemented_in_heuragenix=bool(raw.get("implemented_in_heuragenix", False)),
            baseline_pool=raw.get("baseline_pool", {}),
            metadata=raw.get("metadata", {}),
        )

    @property
    def objective_is_minimize(self) -> bool:
        return self.metric.objective == "minimize"

    def validate_artifact_paths(self) -> list[Path]:
        missing = []
        for path in [self.splits.train, self.splits.validation, self.splits.test, self.splits.smoke]:
            if path is not None and not path.exists():
                missing.append(path)
        if self.reference.path is not None and not self.reference.path.exists():
            missing.append(self.reference.path)
        return missing


class TaskRegistry:
    def __init__(self, tasks: list[TaskSpec]) -> None:
        self._tasks = {task.task_id: task for task in tasks}

    def __iter__(self):
        return iter(self._tasks.values())

    def __len__(self) -> int:
        return len(self._tasks)

    def get(self, task_id: str) -> TaskSpec:
        return self._tasks[task_id]

    def list_task_ids(self, problem: str | None = None, size_tier: str | None = None) -> list[str]:
        tasks = self._tasks.values()
        if problem is not None:
            tasks = [task for task in tasks if task.problem == problem]
        if size_tier is not None:
            tasks = [task for task in tasks if task.size_tier == size_tier]
        return [task.task_id for task in tasks]

    def validate_artifact_paths(self) -> dict[str, list[Path]]:
        return {
            task.task_id: missing
            for task in self._tasks.values()
            if (missing := task.validate_artifact_paths())
        }


def load_task_registry(
    registry_path: str | Path = DEFAULT_TASK_REGISTRY,
    repo_root: str | Path | None = None,
) -> TaskRegistry:
    root = Path(repo_root).resolve() if repo_root else _find_repo_root(Path.cwd())
    path = _resolve_repo_path(registry_path, root)
    with path.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp)
    tasks = [TaskSpec.from_dict(item, root) for item in raw["tasks"]]
    return TaskRegistry(tasks)


def _resolve_repo_path(path: str | Path, repo_root: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else repo_root / path


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / DEFAULT_TASK_REGISTRY).exists():
            return candidate
        if (candidate / ".git").exists() and (candidate / "src").exists():
            return candidate
    return start

