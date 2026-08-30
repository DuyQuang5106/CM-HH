from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from cmhh.memory import MemoryItem, MemoryUnit
from cmhh.models import HeuristicArtifact
from cmhh.tasks import TaskSpec
from cmhh.transfer import TransferPlan, TransferRecord


@dataclass(frozen=True)
class PopulationBuildResult:
    seed_population: list[HeuristicArtifact]
    memory_context: list[MemoryUnit]
    transfer_records: list[TransferRecord]

    def to_dict(self) -> dict:
        return {
            "seed_population": [artifact.to_dict() for artifact in self.seed_population],
            "memory_context_ids": [unit.id for unit in self.memory_context],
            "transfer_records": [record.to_dict() for record in self.transfer_records],
        }


class MemoryAwarePopulationBuilder:
    """Build P0 from explicit transfer plans plus existing fresh/carryover seeds."""

    def __init__(self, memory_seed_quota: int = 1) -> None:
        if memory_seed_quota < 0:
            raise ValueError("memory_seed_quota must be >= 0")
        self.memory_seed_quota = memory_seed_quota

    def build(
        self,
        *,
        task: TaskSpec,
        transfer_plans: Sequence[TransferPlan],
        retrieved_memory: Sequence[MemoryItem],
        base_seed_population: Sequence[HeuristicArtifact],
    ) -> PopulationBuildResult:
        memory_by_id = {item.id: item for item in retrieved_memory}
        seed_population: list[HeuristicArtifact] = []
        memory_context: list[MemoryUnit] = []
        records: list[TransferRecord] = []
        memory_seed_count = 0

        for plan in transfer_plans:
            unit = memory_by_id.get(plan.memory_id)
            if unit is None:
                records.append(self._record(plan))
                continue

            if plan.action == "direct_reuse" and memory_seed_count < self.memory_seed_quota:
                artifact = self._artifact_from_memory(unit, task)
                if artifact is None:
                    records.append(self._record(plan))
                    continue
                seed_population.append(artifact)
                memory_context.append(unit)
                memory_seed_count += 1
                records.append(
                    self._record(
                        plan,
                        inserted_as_seed=True,
                        included_in_context=True,
                    )
                )
            elif plan.action == "refine":
                memory_context.append(unit)
                records.append(self._record(plan, included_in_context=True))
            else:
                records.append(self._record(plan))

        existing_ids = {artifact.heuristic_id for artifact in seed_population}
        for artifact in base_seed_population:
            if artifact.heuristic_id not in existing_ids:
                seed_population.append(artifact)
                existing_ids.add(artifact.heuristic_id)

        return PopulationBuildResult(
            seed_population=seed_population,
            memory_context=memory_context,
            transfer_records=records,
        )

    def _artifact_from_memory(self, unit: MemoryItem, task: TaskSpec) -> HeuristicArtifact | None:
        code_path = Path(unit.code_path or "")
        if not code_path.exists():
            return None
        return HeuristicArtifact(
            heuristic_id=unit.artifact_id or code_path.stem,
            problem=task.problem,
            code_path=code_path,
            code_hash=unit.code_hash,
            strategy="memory_direct_reuse",
            parent_ids=(unit.id,),
            generation=0,
            task_id=task.task_id,
        )

    def _record(
        self,
        plan: TransferPlan,
        *,
        inserted_as_seed: bool = False,
        included_in_context: bool = False,
    ) -> TransferRecord:
        return TransferRecord(
            memory_id=plan.memory_id,
            artifact_id=plan.artifact_id,
            action=plan.action,
            inserted_as_seed=inserted_as_seed,
            included_in_context=included_in_context,
        )
