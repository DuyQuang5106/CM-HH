from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from cmhh.config import ExperimentConfig, StreamConfig, load_yaml
from cmhh.tasks import TaskRegistry
from src.problems.cvrp.variant import constraint_vector, hamming_distance, profile_from_config


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

    repeated_task_ids = [
        task_id for task_id, count in Counter(stream.task_ids).items()
        if count > 1
    ]
    if repeated_task_ids:
        report.warnings.append(
            f"Stream {stream.stream_id} revisits task IDs: {', '.join(repeated_task_ids)}"
        )

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
    allowed_conditions = {
        "independent_seed",
        "isolated_task",
        "population_carryover",
        "naive_memory_sequential",
        "naive_sequential",
        "naive_memory_unbounded",
        "naive_unbounded",
        "archivist_managed",
        "managed_archivist",
    }
    if experiment.condition not in allowed_conditions:
        report.errors.append(f"Unknown experiment condition: {experiment.condition}")

    if stream.stream_id.startswith("vrp_constraint_graycode"):
        report.errors.extend(_validate_vrp_graycode_stream(registry, stream))

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
        if task.task_id not in stream.task_ids:
            continue
        if not task.implemented_in_heuragenix:
            report.warnings.append(f"{task.task_id}: adapter is not implemented")
        missing = task.validate_artifact_paths()
        if missing:
            report.warnings.append(f"{task.task_id}: {len(missing)} data/reference artifacts are pending")

    return report


def _validate_vrp_graycode_stream(registry: TaskRegistry, stream: StreamConfig) -> list[str]:
    errors = []
    profiles = []
    pair_family_ids = set()
    for task_id in stream.task_ids:
        task = registry.get(task_id)
        if task is None:
            continue
        if task.problem != "cvrp":
            errors.append(f"{stream.stream_id}: {task_id} must use shared cvrp problem adapter")
            continue
        if task.metadata.get("constraint_family") != "vrp":
            errors.append(f"{stream.stream_id}: {task_id} missing constraint_family=vrp")
        variant = task.metadata.get("vrp_variant")
        if not variant:
            errors.append(f"{stream.stream_id}: {task_id} missing vrp_variant metadata")
            continue
        profiles.append((task_id, profile_from_config(variant)))
        if task.metadata.get("pair_family_id"):
            pair_family_ids.add(task.metadata["pair_family_id"])

    if len(pair_family_ids) > 1:
        errors.append(f"{stream.stream_id}: tasks must share one pair_family_id, got {sorted(pair_family_ids)}")

    for (left_task_id, left_profile), (right_task_id, right_profile) in zip(profiles, profiles[1:]):
        distance = hamming_distance(constraint_vector(left_profile), constraint_vector(right_profile))
        if distance != 1:
            errors.append(
                f"{stream.stream_id}: {left_task_id} -> {right_task_id} changes {distance} constraint bits, expected 1"
            )
    return errors
