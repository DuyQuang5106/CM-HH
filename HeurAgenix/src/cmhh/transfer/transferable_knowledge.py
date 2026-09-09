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
    algorithmic_principles: tuple[str, ...]
    design_description: str
    source_performance: dict[str, Any] = field(default_factory=dict)
    source_heuristic_id: str = "unknown"
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_population_item(artifact: Any, source_problem: str) -> TransferableKnowledge:
    """Normalizes a final population heuristic artifact into TransferableKnowledge."""
    hid = getattr(artifact, "heuristic_id", "population_seed")
    desc = getattr(artifact, "description", "") or "High-performing population heuristic"
    principles = tuple(getattr(artifact, "principles", ()) or ("greedy_construction", "local_refinement"))
    perf = {"score": getattr(artifact, "score", None), "relative_gap": getattr(artifact, "relative_gap", None)}
    return TransferableKnowledge(
        source_problem=source_problem,
        algorithmic_principles=principles,
        design_description=desc,
        source_performance=perf,
        source_heuristic_id=hid,
        provenance={"source_memory_type": "population", "artifact_id": hid},
    )


def normalize_naive_archive_item(item: Any, source_problem: str) -> TransferableKnowledge:
    """Normalizes an item from a FIFO or unbounded sequential archive into TransferableKnowledge."""
    hid = getattr(item, "id", "archive_item")
    desc = getattr(item, "description", "") or "Retained archive heuristic candidate"
    principles = tuple(getattr(item, "principles", ()) or ("iterative_improvement", "edge_exchange"))
    return TransferableKnowledge(
        source_problem=source_problem,
        algorithmic_principles=principles,
        design_description=desc,
        source_performance={"validation_delta": getattr(item, "validation_delta", None)},
        source_heuristic_id=hid,
        provenance={"source_memory_type": "naive_archive", "unit_id": hid},
    )


def normalize_managed_ku(unit: Any, source_problem: str) -> TransferableKnowledge:
    """Normalizes an Archivist KnowledgeUnit into TransferableKnowledge."""
    hid = getattr(unit, "id", "managed_ku")
    scope = getattr(unit, "scope", None)
    prob = getattr(scope, "problem", source_problem) if scope else source_problem
    val = getattr(unit, "value", None)
    desc = getattr(val, "content", "") if val else "Archivist curated heuristic knowledge"
    evidence = getattr(unit, "evidence", None)
    perf = {}
    if evidence and hasattr(evidence, "validation_after") and isinstance(evidence.validation_after, dict):
        perf = evidence.validation_after
    return TransferableKnowledge(
        source_problem=prob,
        algorithmic_principles=("structured_heuristic_pattern", "modular_operator"),
        design_description=desc,
        source_performance=perf,
        source_heuristic_id=hid,
        provenance={"source_memory_type": "managed_ku", "unit_id": hid},
    )


class CrossProblemAdapter:
    """Adapts transferable knowledge across problem domains into structured prompt context."""

    def format_transferred_knowledge(self, knowledge: TransferableKnowledge, target_problem: str) -> str:
        principles_str = "\n".join(f"- {p}" for p in knowledge.algorithmic_principles) if knowledge.algorithmic_principles else "- Heuristic strategy"
        lines = [
            "<TRANSFERRED_KNOWLEDGE>",
            f"Source Domain: {knowledge.source_problem.upper()}",
            f"Target Domain: {target_problem.upper()}",
            "Algorithmic Principles:",
            principles_str,
            f"Design Strategy: {knowledge.design_description}",
            "Instruction: Adapt the core algorithmic concept above to solve the target problem efficiently while strictly adhering to the target problem constraints and signature.",
            "</TRANSFERRED_KNOWLEDGE>",
        ]
        return "\n".join(lines)
