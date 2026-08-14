from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cmhh.data.manifest import sha256_file
from cmhh.data.references import load_reference_set
from cmhh.references.tour import parse_concorde_tour, tour_objective
from cmhh.tasks import TaskSpec


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
    for instance in sorted(split_path.glob("*.tsp")):
        record = references.get_optional(instance.stem)
        if record is None:
            report.errors.append(f"{instance.stem}: missing reference")
            continue
        if record.instance_sha256 != sha256_file(instance):
            report.errors.append(f"{instance.stem}: checksum mismatch")
            continue
        if not record.tour_path or not Path(record.tour_path).exists():
            report.errors.append(f"{instance.stem}: tour artifact is missing")
            continue
        try:
            dimension = int(task.metadata["nodes"])
            tour = parse_concorde_tour(record.tour_path, dimension)
            recomputed = tour_objective(instance, tour)
        except Exception as exc:
            report.errors.append(f"{instance.stem}: invalid tour: {exc}")
            continue
        if abs(recomputed - record.objective) > 1e-9:
            report.errors.append(
                f"{instance.stem}: objective mismatch ({record.objective} != {recomputed})"
            )
            continue
        if record.status == "optimal":
            report.optimal += 1
        else:
            report.best_known += 1
    return report
