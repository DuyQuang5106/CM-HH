from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from cmhh.retrieval import RetrievedItem
from cmhh.tasks import TaskSpec


TransferAction = Literal["direct_reuse", "refine", "ignore"]
TransferRole = Literal["seed", "prompt_context", "parent", "none"]


@dataclass(frozen=True)
class TransferPlan:
    memory_id: str
    artifact_id: str
    action: TransferAction
    reason: str
    retrieval_rank: int
    retrieval_score: float
    expected_role: TransferRole

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TransferRecord:
    memory_id: str
    artifact_id: str
    action: TransferAction
    inserted_as_seed: bool = False
    included_in_context: bool = False
    survived_selection: bool | None = None
    produced_child: bool | None = None
    produced_selected_child: bool | None = None
    validation_delta: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class DeterministicTransferPolicy:
    """V0 transfer policy with explicit, auditable actions.

    The first compatible retrieved executable is reused directly as a seed.
    Remaining retrieved items are included as refinement context until the
    configured quota is exhausted. Invalid items are ignored.
    """

    def __init__(self, direct_reuse_quota: int = 1, refine_quota: int | None = None) -> None:
        if direct_reuse_quota < 0:
            raise ValueError("direct_reuse_quota must be >= 0")
        if refine_quota is not None and refine_quota < 0:
            raise ValueError("refine_quota must be >= 0")
        self.direct_reuse_quota = direct_reuse_quota
        self.refine_quota = refine_quota

    def plan(self, *, task: TaskSpec, retrieved: list[RetrievedItem]) -> list[TransferPlan]:
        del task
        plans: list[TransferPlan] = []
        direct_used = 0
        refine_used = 0
        refine_limit = self.refine_quota if self.refine_quota is not None else len(retrieved)

        for item in retrieved:
            unit = item.unit
            artifact_id = unit.scope.heuristic_family or unit.id
            has_artifact = bool(unit.evidence.source_artifacts)

            if not has_artifact:
                action: TransferAction = "ignore"
                role: TransferRole = "none"
                reason = "no_executable_artifact"
            elif direct_used < self.direct_reuse_quota:
                direct_used += 1
                action = "direct_reuse"
                role = "seed"
                reason = "top_retrieved_executable"
            elif refine_used < refine_limit:
                refine_used += 1
                action = "refine"
                role = "prompt_context"
                reason = "retrieved_for_refinement_context"
            else:
                action = "ignore"
                role = "none"
                reason = "transfer_quota_exhausted"

            plans.append(
                TransferPlan(
                    memory_id=unit.id,
                    artifact_id=artifact_id,
                    action=action,
                    reason=reason,
                    retrieval_rank=item.rank,
                    retrieval_score=item.score,
                    expected_role=role,
                )
            )
        return plans
