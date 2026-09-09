from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TransferableKnowledge:
    """Canonical intermediate representation of transferable heuristic knowledge.
    
    Decouples source memory backends (Population, Naive Archive, Archivist KUs)
    from the cross-problem adaptation and prompt generation pipeline.
    """
    source_problem: str
    algorithmic_principles: tuple[str, ...] | list[str]
    design_description: str
    source_performance: dict[str, Any] = field(default_factory=dict)
    source_heuristic_id: str = "unknown"
    source_task_id: str = "unknown"
    provenance: dict[str, Any] | str = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if isinstance(d["algorithmic_principles"], tuple):
            d["algorithmic_principles"] = list(d["algorithmic_principles"])
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferableKnowledge:
        principles = data.get("algorithmic_principles", ())
        if isinstance(principles, list):
            principles = tuple(principles)
        return cls(
            source_problem=data.get("source_problem", "unknown"),
            algorithmic_principles=principles,
            design_description=data.get("design_description", ""),
            source_performance=data.get("source_performance", {}),
            source_heuristic_id=data.get("source_heuristic_id", "unknown"),
            source_task_id=data.get("source_task_id", "unknown"),
            provenance=data.get("provenance", {}),
        )


def normalize_population_item(
    artifact: Any = None,
    source_problem: str = "unknown",
    source_task_id: str = "unknown",
    heuristic_id: str | None = None,
    thought: str | None = None,
    fitness: dict[str, Any] | None = None,
) -> TransferableKnowledge:
    """Normalizes a final population heuristic artifact into TransferableKnowledge."""
    hid = heuristic_id or getattr(artifact, "heuristic_id", "population_seed")
    desc = thought or getattr(artifact, "description", "") or "High-performing population heuristic"
    principles = tuple(getattr(artifact, "principles", ()) or ("greedy_construction", "local_refinement"))
    perf = fitness if fitness is not None else {
        "score": getattr(artifact, "score", None),
        "relative_gap": getattr(artifact, "relative_gap", None),
    }
    return TransferableKnowledge(
        source_problem=source_problem,
        source_task_id=source_task_id,
        algorithmic_principles=principles,
        design_description=desc,
        source_performance=perf,
        source_heuristic_id=hid,
        provenance="population_thought" if isinstance(thought, str) else {"source_memory_type": "population", "artifact_id": hid},
    )


def normalize_population_item_to_transferable(
    artifact: Any = None,
    source_problem: str = "unknown",
    source_task_id: str = "unknown",
    heuristic_id: str | None = None,
    thought: str | None = None,
    fitness: dict[str, Any] | None = None,
) -> TransferableKnowledge:
    return normalize_population_item(
        artifact=artifact,
        source_problem=source_problem,
        source_task_id=source_task_id,
        heuristic_id=heuristic_id,
        thought=thought,
        fitness=fitness,
    )


def normalize_naive_archive_item(
    item: Any = None,
    source_problem: str = "unknown",
    source_task_id: str = "unknown",
    heuristic_id: str | None = None,
    thought_or_summary: str | None = None,
    performance: dict[str, Any] | None = None,
) -> TransferableKnowledge:
    """Normalizes an item from a FIFO or unbounded sequential archive into TransferableKnowledge."""
    hid = heuristic_id or getattr(item, "id", "archive_item")
    desc = thought_or_summary or getattr(item, "description", "") or "Retained archive heuristic candidate"
    principles = tuple(getattr(item, "principles", ()) or ("iterative_improvement", "edge_exchange"))
    perf = performance if performance is not None else {"validation_delta": getattr(item, "validation_delta", None)}
    return TransferableKnowledge(
        source_problem=source_problem,
        source_task_id=source_task_id,
        algorithmic_principles=principles,
        design_description=desc,
        source_performance=perf,
        source_heuristic_id=hid,
        provenance="naive_archive" if isinstance(thought_or_summary, str) else {"source_memory_type": "naive_archive", "unit_id": hid},
    )


def normalize_archive_item_to_transferable(
    item: Any = None,
    source_problem: str = "unknown",
    source_task_id: str = "unknown",
    heuristic_id: str | None = None,
    thought_or_summary: str | None = None,
    performance: dict[str, Any] | None = None,
) -> TransferableKnowledge:
    return normalize_naive_archive_item(
        item=item,
        source_problem=source_problem,
        source_task_id=source_task_id,
        heuristic_id=heuristic_id,
        thought_or_summary=thought_or_summary,
        performance=performance,
    )


def normalize_managed_ku(unit: Any, source_problem: str = "unknown") -> TransferableKnowledge:
    """Normalizes an Archivist KnowledgeUnit into TransferableKnowledge."""
    hid = getattr(unit, "id", "managed_ku")
    scope = getattr(unit, "scope", None)
    prob = getattr(scope, "problem", source_problem) if scope else source_problem
    tid = getattr(scope, "task_id", "unknown") if scope else "unknown"
    val = getattr(unit, "value", None)
    desc = getattr(val, "content", "") if val else "Archivist curated heuristic knowledge"
    evidence = getattr(unit, "evidence", None)
    perf = {}
    if evidence and hasattr(evidence, "validation_after") and isinstance(evidence.validation_after, dict):
        perf = evidence.validation_after
    return TransferableKnowledge(
        source_problem=prob,
        source_task_id=tid,
        algorithmic_principles=("structured_heuristic_pattern", "modular_operator"),
        design_description=desc,
        source_performance=perf,
        source_heuristic_id=hid,
        provenance="managed_ku",
    )


def normalize_memory_unit_to_transferable(unit: Any, source_problem: str = "unknown") -> TransferableKnowledge:
    return normalize_managed_ku(unit=unit, source_problem=source_problem)


class CrossProblemAdapter:
    """Adapts transferable knowledge across problem domains into structured prompt context."""

    @classmethod
    def format_cross_problem_prompt_block(
        cls,
        knowledge_list: list[TransferableKnowledge],
        target_problem: str,
        target_task_id: str = "",
    ) -> str:
        blocks = []
        for k in knowledge_list:
            blocks.append(cls.format_transferred_knowledge(k, target_problem))
        return "\n\n".join(blocks)

    @classmethod
    def format_transferred_knowledge(cls, knowledge: TransferableKnowledge, target_problem: str) -> str:
        principles_str = "\n".join(f"- {p}" for p in knowledge.algorithmic_principles) if knowledge.algorithmic_principles else "- Heuristic strategy"
        lines = [
            "<TRANSFERRED_KNOWLEDGE>",
            f"Source Problem: {knowledge.source_problem}",
            f"Target Problem: {target_problem}",
            "Algorithmic Principles:",
            principles_str,
            f"Design Strategy: {knowledge.design_description}",
            "Instruction: DO NOT blindly copy data structures or executable signatures. Adapt only the core algorithmic concept above to solve the target problem efficiently while adhering to target problem constraints and signature.",
            "</TRANSFERRED_KNOWLEDGE>",
        ]
        return "\n".join(lines)
