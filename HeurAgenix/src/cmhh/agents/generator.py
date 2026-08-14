from __future__ import annotations

from typing import Protocol

from cmhh.baselines import baseline_artifacts
from cmhh.models import HeuristicArtifact, SearchBudget
from cmhh.tasks import TaskSpec


class Generator(Protocol):
    def generate(
        self,
        task: TaskSpec,
        seed_population: list[HeuristicArtifact],
        budget: SearchBudget,
        seed: int,
    ) -> list[HeuristicArtifact]: ...


class BaselineGenerator:
    """No-LLM generator used to verify the Phase 0 orchestration path."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root

    def generate(
        self,
        task: TaskSpec,
        seed_population: list[HeuristicArtifact],
        budget: SearchBudget,
        seed: int,
    ) -> list[HeuristicArtifact]:
        del budget, seed
        return seed_population or baseline_artifacts(task, self.repo_root)


