from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from cmhh.data.manifest import load_json, sha256_file
from cmhh.data.references import ReferenceRecord, load_reference_set
from cmhh.evaluation.problem_adapter import ProblemRegistry
from cmhh.references.tour import parse_concorde_tour, tour_objective
from cmhh.tasks import TaskSpec
from src.problems.cvrp.variant import profile_from_config


@dataclass
class ReferenceVerificationReport:
    task_id: str
    split: str
    optimal: int = 0
    best_known: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def verify_task_references(task: TaskSpec, split: str) -> ReferenceVerificationReport:
    report = ReferenceVerificationReport(task.task_id, split)
    split_path = getattr(task.splits, split)
    if split_path is None or not split_path.exists():
        report.errors.append(f"Missing split directory: {split_path}")
        return report
    if task.reference.path is None or not task.reference.path.exists():
        report.errors.append(f"Missing reference file: {task.reference.path}")
        return report
    references = load_reference_set(task.reference.path)
    adapter = ProblemRegistry.get(task.problem)
    instances = adapter.discover_instances(split_path)

    for instance in instances:
        record = references.get_optional(instance.stem)
        if record is None:
            report.errors.append(f"{instance.stem}: missing reference")
            continue
        if record.instance_sha256 != sha256_file(instance):
            report.errors.append(f"{instance.stem}: checksum mismatch")
            continue
        if record.objective is None or not math.isfinite(record.objective) or record.objective < 0:
            report.errors.append(f"{instance.stem}: non-finite or invalid objective")
            continue

        # If tour path exists (e.g. Concorde for TSP), verify recomputed tour
        if record.tour_path and Path(record.tour_path).exists() and task.problem == "tsp":
            try:
                dimension = int(task.metadata.get("nodes", 20))
                tour = parse_concorde_tour(record.tour_path, dimension)
                recomputed = tour_objective(instance, tour)
                if abs(recomputed - record.objective) > 1e-9:
                    report.errors.append(
                        f"{instance.stem}: objective mismatch ({record.objective} != {recomputed})"
                    )
                    continue
            except Exception as exc:
                report.errors.append(f"{instance.stem}: invalid tour: {exc}")
                continue

        vrp_errors = verify_vrp_reference_record(task, instance, record)
        if vrp_errors:
            report.errors.extend(vrp_errors)
            continue

        if record.status == "optimal":
            report.optimal += 1
        else:
            report.best_known += 1
    return report


def verify_vrp_reference_record(task: TaskSpec, instance: Path, record: ReferenceRecord) -> list[str]:
    if task.problem != "cvrp":
        return []
    if task.metadata.get("constraint_family") != "vrp" and not task.metadata.get("vrp_variant"):
        return []

    errors: list[str] = []
    instance_meta = _load_instance_meta(instance)
    expected_variant = str(
        instance_meta.get("variant")
        or task.metadata.get("vrp_variant")
        or task.metadata.get("variant")
        or "cvrp"
    ).lower()
    expected_profile = profile_from_config(
        instance_meta.get("constraints")
        or instance_meta.get("variant")
        or task.metadata.get("constraints")
        or task.metadata.get("vrp_variant")
        or "cvrp"
    )

    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    actual_variant = str(metadata.get("variant", "")).lower()
    if actual_variant != expected_variant:
        errors.append(
            f"{instance.stem}: VRP reference variant mismatch "
            f"({actual_variant or 'missing'} != {expected_variant})"
        )

    actual_constraints = metadata.get("constraints")
    if actual_constraints != expected_profile.to_dict():
        errors.append(f"{instance.stem}: VRP reference constraints mismatch")

    if metadata.get("internal_validation_feasible") is not True:
        errors.append(f"{instance.stem}: VRP reference missing successful internal validation")

    internal_objective = metadata.get("internal_objective")
    try:
        internal_objective_value = float(internal_objective)
    except (TypeError, ValueError):
        errors.append(f"{instance.stem}: VRP reference missing internal objective")
    else:
        tolerance = 1e-6 * max(1.0, abs(record.objective))
        if abs(internal_objective_value - record.objective) > tolerance:
            errors.append(
                f"{instance.stem}: VRP internal objective mismatch "
                f"({record.objective} != {internal_objective_value})"
            )

    return errors


def _load_instance_meta(instance: Path) -> dict:
    meta_path = instance.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    meta = load_json(meta_path)
    return meta if isinstance(meta, dict) else {}

