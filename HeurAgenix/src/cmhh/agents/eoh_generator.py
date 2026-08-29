from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

from cmhh.data.manifest import sha256_file
from cmhh.llm.config import load_llm_config, write_sanitized_snapshot
from cmhh.memory import MemoryUnit
from cmhh.models import HeuristicArtifact, SearchBudget
from cmhh.tasks import TaskSpec


class EOHGenerator:
    """Official FeiLiu36/EoH cold-start generator used as a no-memory baseline."""

    def __init__(
        self,
        repo_root: str | Path,
        llm_config_path: str | Path,
        output_root: str | Path,
        timeout_seconds: float = 3600,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.llm_config_path = Path(llm_config_path).resolve()
        self.output_root = Path(output_root).resolve()
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        task: TaskSpec,
        seed_population: list[HeuristicArtifact],
        budget: SearchBudget,
        seed: int,
        memory_context: list[MemoryUnit] | None = None,
    ) -> list[HeuristicArtifact]:
        del seed_population, memory_context
        llm_config = load_llm_config(self.llm_config_path)
        invocation_root = self.output_root / task.task_id / f"seed_{seed}"
        invocation_root.mkdir(parents=True, exist_ok=True)
        write_sanitized_snapshot(invocation_root / "llm_config.snapshot.json", llm_config)
        result_path = invocation_root / "generator_result.json"
        max_candidates = max(1, budget.generations * budget.candidates_per_generation)
        command = [
            sys.executable, "-m", "cmhh.agents.eoh_worker",
            "--repo-root", str(self.repo_root),
            "--problem", task.problem,
            "--train-dir", str(task.splits.train),
            "--llm-config", str(self.llm_config_path),
            "--output-root", str(invocation_root),
            "--result", str(result_path),
            "--seed", str(seed),
            "--generations", str(budget.generations),
            "--pop-size", str(budget.candidates_per_generation),
            "--max-llm-calls", str(budget.max_llm_calls),
            "--max-candidates", str(max_candidates),
            "--evaluation-timeout", os.environ.get("CMHH_EOH_EVALUATION_TIMEOUT_SECONDS", "180"),
        ]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join([
            str(self.repo_root),
            str(self.repo_root / "src"),
            environment.get("PYTHONPATH", ""),
        ])
        try:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"EOH generation exceeded {self.timeout_seconds}s") from exc
        if not result_path.exists():
            detail = (completed.stderr or completed.stdout or "worker produced no result")[-4000:]
            raise RuntimeError(f"EOH worker failed: {detail}")
        raw = json.loads(result_path.read_text(encoding="utf-8"))
        if raw["status"] != "ok":
            raise RuntimeError(raw.get("error", "EOH worker failed"))
        artifacts: list[HeuristicArtifact] = []
        for index, candidate in enumerate(raw["candidates"]):
            path = Path(candidate["path"])
            code = path.read_text(encoding="utf-8")
            ast.parse(code)
            artifacts.append(HeuristicArtifact(
                heuristic_id=path.stem,
                problem=task.problem,
                code_path=path,
                code_hash=sha256_file(path),
                strategy="Official EOH cold-start candidate",
                parent_ids=(),
                generation=max(1, index // max(1, budget.candidates_per_generation) + 1),
                task_id=task.task_id,
                prompt_hash=raw["prompt_hash"],
                model=raw["model"],
                llm_call_index=raw.get("calls_used_estimate"),
            ))
        if not artifacts:
            raise RuntimeError(f"EOH worker produced no usable candidates for {task.task_id}")
        return artifacts
