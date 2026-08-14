from __future__ import annotations

import hashlib
from pathlib import Path

from cmhh.models import HeuristicArtifact
from cmhh.tasks import TaskSpec


def baseline_artifacts(task: TaskSpec, repo_root: str | Path) -> list[HeuristicArtifact]:
    root = Path(repo_root).resolve()
    if not task.implemented_in_heuragenix:
        raise ValueError(f"No HeurAgenix adapter for {task.problem}")
    directory = root / "src" / "problems" / task.problem / "heuristics" / task.baseline_pool["heuristic_dir"]
    artifacts = []
    for heuristic_id in task.baseline_pool.get("seed_heuristics", []):
        path = directory / f"{heuristic_id}.py"
        if not path.exists():
            raise FileNotFoundError(f"Configured baseline does not exist: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifacts.append(HeuristicArtifact(
            heuristic_id=heuristic_id,
            problem=task.problem,
            code_path=path,
            code_hash=digest,
            strategy="HeurAgenix built-in baseline",
            task_id=task.task_id,
        ))
    return artifacts
