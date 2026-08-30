from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from cmhh.models import HeuristicArtifact
from cmhh.tasks import TaskSpec


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    artifact: HeuristicArtifact
    task_id: str
    validation_score: float
    validation_summary: dict[str, Any]
    source_generation: int
    parent_artifact_ids: tuple[str, ...]
    code_hash: str
    rank: int
    parent_memory_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["artifact"] = self.artifact.to_dict()
        return raw


class TopKCandidateExtractor:
    """V0 candidate extractor: deterministic top-k by validation score."""

    def __init__(self, top_k: int = 3) -> None:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        self.top_k = top_k

    def extract(
        self,
        *,
        task: TaskSpec,
        final_population: Sequence[HeuristicArtifact],
        validation_summaries: dict[str, dict[str, Any]],
        parent_memory_by_artifact: dict[str, tuple[str, ...]] | None = None,
    ) -> list[MemoryCandidate]:
        parent_memory_by_artifact = parent_memory_by_artifact or {}
        ranked: list[tuple[float, str, HeuristicArtifact, dict[str, Any]]] = []
        for artifact in final_population:
            summary = validation_summaries.get(artifact.heuristic_id)
            if not summary:
                continue
            score = float(summary.get("score", float("-inf")))
            ranked.append((score, artifact.heuristic_id, artifact, dict(summary)))

        selected = sorted(ranked, key=lambda item: (-item[0], item[1]))[: self.top_k]
        candidates: list[MemoryCandidate] = []
        for index, (score, _, artifact, summary) in enumerate(selected, start=1):
            candidates.append(
                MemoryCandidate(
                    candidate_id=f"{task.task_id}:{artifact.heuristic_id}",
                    artifact=artifact,
                    task_id=task.task_id,
                    validation_score=score,
                    validation_summary=summary,
                    source_generation=artifact.generation,
                    parent_artifact_ids=artifact.parent_ids,
                    code_hash=artifact.code_hash,
                    rank=index,
                    parent_memory_ids=self._parent_memory_ids(artifact, parent_memory_by_artifact),
                )
            )
        return candidates

    def _parent_memory_ids(
        self,
        artifact: HeuristicArtifact,
        parent_memory_by_artifact: dict[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        memory_ids: list[str] = []
        for artifact_id in (artifact.heuristic_id, *artifact.parent_ids):
            for memory_id in parent_memory_by_artifact.get(artifact_id, ()):
                if memory_id not in memory_ids:
                    memory_ids.append(memory_id)
        return tuple(memory_ids)
