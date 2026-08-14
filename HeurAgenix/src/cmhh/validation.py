from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cmhh.config import ExperimentConfig, StreamConfig, load_yaml
from cmhh.tasks import TaskRegistry


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def validate_configuration(
    registry: TaskRegistry,
    stream: StreamConfig,
    experiment: ExperimentConfig,
    repo_root: str | Path,
) -> ValidationReport:
    report = ValidationReport()
    root = Path(repo_root).resolve()

    if len(stream.task_ids) != len(set(stream.task_ids)):
        report.errors.append(f"Stream {stream.stream_id} contains duplicate task IDs")

    known_ids = set(registry.list_task_ids())
    for task_id in stream.task_ids:
        if task_id not in known_ids:
            report.errors.append(f"Unknown task in stream: {task_id}")

    required_splits = {"train", "validation", "test", "smoke"}
    if set(experiment.data.splits) != required_splits:
        report.errors.append("Experiment data splits must be train/validation/test/smoke")
    for split, count in experiment.data.splits.items():
        if count <= 0:
            report.errors.append(f"Split {split} must contain at least one instance")
    if experiment.data.coordinate_max <= experiment.data.coordinate_min:
        report.errors.append("coordinate_max must be greater than coordinate_min")
    if experiment.evaluation.instance_timeout_seconds <= 0:
        report.errors.append("instance timeout must be positive")

    defaults_path = root / "cmhh/configs/tasks/problem_defaults.yaml"
    tiers_path = root / "cmhh/configs/tasks/size_tiers.yaml"
    defaults = load_yaml(defaults_path)["problems"]
    tiers = load_yaml(tiers_path)["size_tiers"]
    for task in registry:
        if task.problem not in defaults:
            report.errors.append(f"{task.task_id}: unknown problem {task.problem}")
        if task.size_tier not in tiers:
            report.errors.append(f"{task.task_id}: unknown size tier {task.size_tier}")
        elif task.problem not in tiers[task.size_tier]:
            report.errors.append(
                f"{task.task_id}: size tier {task.size_tier} has no {task.problem} definition"
            )
        if not task.implemented_in_heuragenix:
            report.warnings.append(f"{task.task_id}: adapter is not implemented")
        missing = task.validate_artifact_paths()
        if missing:
            report.warnings.append(f"{task.task_id}: {len(missing)} data/reference artifacts are pending")

    return report
