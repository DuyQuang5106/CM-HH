from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MemoryValueType = str


@dataclass(frozen=True)
class MemoryScope:
    problem: str
    task_id: str
    heuristic_family: str | None = None
    generation: int | None = None


@dataclass(frozen=True)
class MemoryKey:
    applicability: str
    task_signature: dict[str, Any] = field(default_factory=dict)
    state_signature: dict[str, Any] = field(default_factory=dict)
    bottleneck_type: str | None = None


@dataclass(frozen=True)
class MemoryValue:
    type: MemoryValueType
    content: str


@dataclass(frozen=True)
class MemoryEvidence:
    source_artifacts: tuple[str, ...] = ()
    validation_before: dict[str, Any] = field(default_factory=dict)
    validation_after: dict[str, Any] = field(default_factory=dict)
    code_hashes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryPolicyState:
    confidence: float = 0.0
    retrieval_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    protected: bool = False


@dataclass(frozen=True)
class MemoryUnit:
    id: str
    created_at: str
    scope: MemoryScope
    key: MemoryKey
    value: MemoryValue
    evidence: MemoryEvidence = field(default_factory=MemoryEvidence)
    policy: MemoryPolicyState = field(default_factory=MemoryPolicyState)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MemoryUnit":
        return cls(
            id=raw["id"],
            created_at=raw["created_at"],
            scope=MemoryScope(**raw["scope"]),
            key=MemoryKey(**raw["key"]),
            value=MemoryValue(**raw["value"]),
            evidence=MemoryEvidence(
                source_artifacts=tuple(raw.get("evidence", {}).get("source_artifacts", ())),
                validation_before=raw.get("evidence", {}).get("validation_before", {}),
                validation_after=raw.get("evidence", {}).get("validation_after", {}),
                code_hashes=tuple(raw.get("evidence", {}).get("code_hashes", ())),
            ),
            policy=MemoryPolicyState(**raw.get("policy", {})),
        )


# =====================================================================
# 3-Layer Formal Memory Models (schema_version = 1)
# =====================================================================

@dataclass(frozen=True)
class ApplicabilityDescriptor:
    problem_family: str
    task_id: str
    size_tier: str | None = None
    distribution: str | None = None
    heuristic_interface: str = "tsp_constructive_v1"
    task_signature: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeAbstraction:
    abstraction_type: str = "procedural_skill"
    summary: str = ""
    prompt_hint: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryMetadata:
    origin_task_id: str
    origin_generation: int = 0
    parent_ids: tuple[str, ...] = ()
    validation_score: float = 0.0
    validation_summary: dict[str, Any] = field(default_factory=dict)
    retrieval_count: int = 0
    success_count: int = 0
    protected: bool = False
    created_at: str = ""


@dataclass(frozen=True)
class MemoryItem:
    """Formal 3-layer logical memory unit in CMHH.
    
    Encapsulates:
    - h_i: Procedural Artifact Reference (artifact_id, code_path, code_hash)
    - k_i: Applicability Descriptor (applicability)
    - z_i: Knowledge Abstraction (abstraction)
    - mu_i: Lifecycle Metadata (metadata)
    """
    id: str
    artifact_id: str
    code_path: str
    code_hash: str
    applicability: ApplicabilityDescriptor
    abstraction: KnowledgeAbstraction
    metadata: MemoryMetadata
    schema_version: int = 1

    @property
    def scope(self) -> MemoryScope:
        return MemoryScope(
            problem=self.applicability.problem_family,
            task_id=self.applicability.task_id,
            heuristic_family=self.artifact_id,
            generation=self.metadata.origin_generation,
        )

    @property
    def key(self) -> MemoryKey:
        return MemoryKey(
            applicability=f"{self.applicability.problem_family} {self.applicability.task_id}",
            task_signature=self.applicability.task_signature,
        )

    @property
    def value(self) -> MemoryValue:
        return MemoryValue(
            type=self.abstraction.abstraction_type,
            content=self.abstraction.summary,
        )

    @property
    def evidence(self) -> MemoryEvidence:
        return MemoryEvidence(
            source_artifacts=(self.code_path,),
            validation_after=self.metadata.validation_summary,
            code_hashes=(self.code_hash,),
        )

    @property
    def policy(self) -> MemoryPolicyState:
        return MemoryPolicyState(
            retrieval_count=self.metadata.retrieval_count,
            success_count=self.metadata.success_count,
            protected=self.metadata.protected,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MemoryItem":
        if raw.get("schema_version") == 1:
            return cls(
                id=raw["id"],
                artifact_id=raw["artifact_id"],
                code_path=raw["code_path"],
                code_hash=raw["code_hash"],
                applicability=ApplicabilityDescriptor(**raw["applicability"]),
                abstraction=KnowledgeAbstraction(
                    abstraction_type=raw["abstraction"]["abstraction_type"],
                    summary=raw["abstraction"]["summary"],
                    prompt_hint=raw["abstraction"].get("prompt_hint"),
                    tags=tuple(raw["abstraction"].get("tags", ())),
                ),
                metadata=MemoryMetadata(
                    origin_task_id=raw["metadata"]["origin_task_id"],
                    origin_generation=raw["metadata"].get("origin_generation", 0),
                    parent_ids=tuple(raw["metadata"].get("parent_ids", ())),
                    validation_score=raw["metadata"].get("validation_score", 0.0),
                    validation_summary=raw["metadata"].get("validation_summary", {}),
                    retrieval_count=raw["metadata"].get("retrieval_count", 0),
                    success_count=raw["metadata"].get("success_count", 0),
                    protected=raw["metadata"].get("protected", False),
                    created_at=raw["metadata"].get("created_at", ""),
                ),
                schema_version=1,
            )
        return cls.from_legacy_unit(MemoryUnit.from_dict(raw))

    @classmethod
    def from_legacy_unit(cls, unit: MemoryUnit) -> "MemoryItem":
        code_path = unit.evidence.source_artifacts[0] if unit.evidence.source_artifacts else ""
        code_hash = unit.evidence.code_hashes[0] if unit.evidence.code_hashes else ""
        val_summary = unit.evidence.validation_after
        val_score = float(val_summary.get("score", 0.0)) if isinstance(val_summary, dict) else 0.0
        return cls(
            id=unit.id,
            artifact_id=unit.scope.heuristic_family or unit.id,
            code_path=code_path,
            code_hash=code_hash,
            applicability=ApplicabilityDescriptor(
                problem_family=unit.scope.problem,
                task_id=unit.scope.task_id,
                task_signature=unit.key.task_signature,
            ),
            abstraction=KnowledgeAbstraction(
                abstraction_type=unit.value.type,
                summary=unit.value.content,
            ),
            metadata=MemoryMetadata(
                origin_task_id=unit.scope.task_id,
                origin_generation=unit.scope.generation or 0,
                validation_score=val_score,
                validation_summary=val_summary if isinstance(val_summary, dict) else {},
                retrieval_count=unit.policy.retrieval_count,
                success_count=unit.policy.success_count,
                protected=unit.policy.protected,
                created_at=unit.created_at,
            ),
            schema_version=1,
        )


# =====================================================================
# WorkingBuffer Class
# =====================================================================

class WorkingBuffer:
    """Short-term bounded memory buffer holding recent search experience.
    
    Acts as a transient stage between heuristic generation/evaluation and long-term memory.
    """

    def __init__(self, capacity: int = 50) -> None:
        self.capacity = capacity
        self._buffer: list[dict[str, Any]] = []

    def add_experience(
        self,
        artifact: Any,
        validation_summary: dict[str, Any],
        task: Any,
    ) -> None:
        record = {
            "artifact": artifact,
            "validation_summary": validation_summary,
            "task_id": task.task_id,
            "problem": task.problem,
            "timestamp": utc_now(),
        }
        self._buffer.append(record)
        if len(self._buffer) > self.capacity:
            self._buffer.pop(0)

    def get_experiences(self) -> list[dict[str, Any]]:
        return list(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()

    def size(self) -> int:
        return len(self._buffer)


# =====================================================================
# MemoryStore Engine
# =====================================================================

class MemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_all(self) -> list[MemoryItem]:
        if not self.path.exists():
            return []
        items = []
        with self.path.open("r", encoding="utf-8") as fp:
            for line in fp:
                if line.strip():
                    raw = json.loads(line)
                    items.append(MemoryItem.from_dict(raw))
        return items

    def save_all(self, items: list[MemoryItem]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(f".{self.path.name}.tmp")
        with temp.open("w", encoding="utf-8") as fp:
            for item in items:
                fp.write(json.dumps(item.to_dict(), sort_keys=True) + "\n")
        os.replace(temp, self.path)

    def upsert(self, item: MemoryItem) -> None:
        items = self.load_all()
        for index, existing in enumerate(items):
            if existing.id == item.id:
                items[index] = item
                self.save_all(items)
                return
        items.append(item)
        self.save_all(items)

    def update_validation_evidence(
        self,
        memory_id: str,
        *,
        split: str,
        validation_before: dict[str, Any] | None = None,
        validation_after: dict[str, Any] | None = None,
    ) -> MemoryItem:
        if split != "validation":
            raise ValueError("Memory evidence updates must come from the validation split")
        items = self.load_all()
        for index, item in enumerate(items):
            if item.id != memory_id:
                continue
            updated_summary = validation_after if validation_after is not None else item.metadata.validation_summary
            updated_metadata = replace(
                item.metadata,
                validation_summary=updated_summary,
                validation_score=float(updated_summary.get("score", item.metadata.validation_score)),
            )
            updated = replace(item, metadata=updated_metadata)
            items[index] = updated
            self.save_all(items)
            return updated
        raise KeyError(f"Unknown memory unit: {memory_id}")


@dataclass(frozen=True)
class RetrievedMemory:
    unit: MemoryUnit
    score: float
    rank: int


def retrieve_naive(
    units: list[MemoryUnit],
    *,
    problem: str,
    task_signature: dict[str, Any],
    top_k: int,
) -> list[RetrievedMemory]:
    scored = [
        (naive_retrieval_score(unit, problem=problem, task_signature=task_signature), unit)
        for unit in units
    ]
    ranked = [
        RetrievedMemory(unit=unit, score=score, rank=index + 1)
        for index, (score, unit) in enumerate(
            sorted(scored, key=lambda item: (-item[0], item[1].id))[:top_k]
        )
        if score > 0
    ]
    return ranked


def naive_retrieval_score(
    unit: MemoryUnit,
    *,
    problem: str,
    task_signature: dict[str, Any],
) -> float:
    score = 0.0
    if unit.scope.problem == problem:
        score += 1.0
    for key, value in task_signature.items():
        if unit.key.task_signature.get(key) == value:
            score += 0.5
    if problem.lower() in unit.key.applicability.lower():
        score += 0.25
    return score


def create_memory_unit(
    *,
    scope: MemoryScope,
    key: MemoryKey,
    value: MemoryValue,
    evidence: MemoryEvidence | None = None,
    policy: MemoryPolicyState | None = None,
    created_at: str | None = None,
) -> MemoryItem:
    evidence = evidence or MemoryEvidence()
    val_after = evidence.validation_after
    val_score = float(val_after.get("score", 0.0)) if isinstance(val_after, dict) else 0.0
    code_path = evidence.source_artifacts[0] if evidence.source_artifacts else ""
    code_hash = evidence.code_hashes[0] if evidence.code_hashes else ""
    policy_state = policy or MemoryPolicyState()
    
    item_id = deterministic_memory_id(scope, key, value, evidence)
    return MemoryItem(
        id=item_id,
        artifact_id=scope.heuristic_family or item_id,
        code_path=code_path,
        code_hash=code_hash,
        applicability=ApplicabilityDescriptor(
            problem_family=scope.problem,
            task_id=scope.task_id,
            task_signature=key.task_signature,
        ),
        abstraction=KnowledgeAbstraction(
            abstraction_type=value.type,
            summary=value.content,
        ),
        metadata=MemoryMetadata(
            origin_task_id=scope.task_id,
            origin_generation=scope.generation or 0,
            validation_score=val_score,
            validation_summary=val_after if isinstance(val_after, dict) else {},
            retrieval_count=policy_state.retrieval_count,
            success_count=policy_state.success_count,
            protected=policy_state.protected,
            created_at=created_at or utc_now(),
        ),
        schema_version=1,
    )


def deterministic_memory_id(
    scope: MemoryScope,
    key: MemoryKey,
    value: MemoryValue,
    evidence: MemoryEvidence | None = None,
) -> str:
    evidence = evidence or MemoryEvidence()
    stable_payload = {
        "scope": asdict(scope),
        "key": asdict(key),
        "value": asdict(value),
        "evidence": {
            "source_artifacts": list(evidence.source_artifacts),
            "code_hashes": list(evidence.code_hashes),
        },
    }
    encoded = json.dumps(stable_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "mem_" + hashlib.sha256(encoded).hexdigest()[:16]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
