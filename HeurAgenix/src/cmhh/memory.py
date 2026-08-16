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


class MemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_all(self) -> list[MemoryUnit]:
        if not self.path.exists():
            return []
        units = []
        with self.path.open("r", encoding="utf-8") as fp:
            for line in fp:
                if line.strip():
                    units.append(MemoryUnit.from_dict(json.loads(line)))
        return units

    def save_all(self, units: list[MemoryUnit]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(f".{self.path.name}.tmp")
        with temp.open("w", encoding="utf-8") as fp:
            for unit in units:
                fp.write(json.dumps(unit.to_dict(), sort_keys=True) + "\n")
        os.replace(temp, self.path)

    def upsert(self, unit: MemoryUnit) -> None:
        units = self.load_all()
        for index, existing in enumerate(units):
            if existing.id == unit.id:
                units[index] = unit
                self.save_all(units)
                return
        units.append(unit)
        self.save_all(units)

    def update_validation_evidence(
        self,
        memory_id: str,
        *,
        split: str,
        validation_before: dict[str, Any] | None = None,
        validation_after: dict[str, Any] | None = None,
    ) -> MemoryUnit:
        if split != "validation":
            raise ValueError("Memory evidence updates must come from the validation split")
        units = self.load_all()
        for index, unit in enumerate(units):
            if unit.id != memory_id:
                continue
            evidence = replace(
                unit.evidence,
                validation_before=validation_before if validation_before is not None else unit.evidence.validation_before,
                validation_after=validation_after if validation_after is not None else unit.evidence.validation_after,
            )
            updated = replace(unit, evidence=evidence)
            units[index] = updated
            self.save_all(units)
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
) -> MemoryUnit:
    evidence = evidence or MemoryEvidence()
    return MemoryUnit(
        id=deterministic_memory_id(scope, key, value, evidence),
        created_at=created_at or utc_now(),
        scope=scope,
        key=key,
        value=value,
        evidence=evidence,
        policy=policy or MemoryPolicyState(),
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
