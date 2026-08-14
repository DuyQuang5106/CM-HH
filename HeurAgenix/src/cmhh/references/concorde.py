from __future__ import annotations

import subprocess
import tempfile
import time
import shutil
import re
from dataclasses import dataclass
from pathlib import Path

from cmhh.config import load_yaml
from cmhh.data.manifest import sha256_file
from cmhh.data.references import ReferenceRecord
from cmhh.data.tsp_io import read_euc2d_coordinates
from cmhh.references.tour import parse_concorde_tour, tour_objective, write_normalized_tour


@dataclass(frozen=True)
class ConcordeConfig:
    command_prefix: tuple[str, ...]
    arguments: tuple[str, ...]
    max_workers: int
    timeouts: dict[str, float]


@dataclass(frozen=True)
class SolverFailure:
    instance_id: str
    status: str
    error: str
    runtime_seconds: float


def load_concorde_config(path: str | Path, repo_root: str | Path) -> ConcordeConfig:
    raw = load_yaml(path)["solver"]
    root = Path(repo_root).resolve()
    prefix = list(raw["command_prefix"])
    first = Path(prefix[0])
    if not first.is_absolute():
        prefix[0] = str(root / first)
    return ConcordeConfig(
        command_prefix=tuple(prefix),
        arguments=tuple(str(item) for item in raw["arguments"]),
        max_workers=max(1, int(raw.get("max_workers", 1))),
        timeouts={key: float(value) for key, value in raw["timeouts"].items()},
    )


def validate_solver_command(config: ConcordeConfig) -> None:
    executable = Path(config.command_prefix[0])
    if not executable.exists():
        raise FileNotFoundError(
            f"Concorde executable was not found: {executable}. "
            "Update command_prefix in the solver config."
        )


def solve_instance(
    instance_path: str | Path,
    size_tier: str,
    config: ConcordeConfig,
    normalized_tour_path: str | Path,
) -> ReferenceRecord | SolverFailure:
    instance = Path(instance_path).resolve()
    dimension = len(read_euc2d_coordinates(instance))
    timeout = config.timeouts[size_tier]
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="cmhh_concorde_") as directory:
        staged_instance = Path(directory) / "problem.tsp"
        shutil.copy2(instance, staged_instance)
        raw_tour = Path(directory) / "solution.sol"
        replacements = {
            # Relative paths work for native binaries and the official Cygwin
            # build, which does not understand Windows drive-letter paths.
            "{tour_path}": raw_tour.name,
            "{instance_path}": staged_instance.name,
        }
        arguments = [replacements.get(argument, argument) for argument in config.arguments]
        command = [*config.command_prefix, *arguments]
        try:
            completed = subprocess.run(
                command,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return SolverFailure(instance.stem, "timeout", str(exc), time.perf_counter() - started)
        runtime = time.perf_counter() - started
        proof_match = re.search(r"Optimal Solution:\s*([0-9]+(?:\.[0-9]+)?)", completed.stdout)
        diff_match = re.search(r"DIFF:\s*([0-9]+(?:\.[0-9]+)?)", completed.stdout)
        legacy_proof_success = (
            raw_tour.exists()
            and proof_match is not None
            and diff_match is not None
            and abs(float(diff_match.group(1))) <= 1e-9
        )
        if completed.returncode != 0 and not legacy_proof_success:
            error = (completed.stderr or completed.stdout or "Concorde failed")[-4000:]
            return SolverFailure(instance.stem, "solver_failure", error, runtime)
        if not raw_tour.exists():
            return SolverFailure(instance.stem, "missing_tour", "Solver produced no tour file", runtime)
        try:
            tour = parse_concorde_tour(raw_tour, dimension)
            objective = tour_objective(instance, tour)
            if proof_match is not None and abs(objective - float(proof_match.group(1))) > 1e-9:
                raise ValueError(
                    f"Concorde objective {proof_match.group(1)} does not match recomputed {objective}"
                )
        except Exception as exc:
            return SolverFailure(instance.stem, "invalid_tour", str(exc), runtime)
        output_tour = Path(normalized_tour_path)
        write_normalized_tour(output_tour, tour)
        return ReferenceRecord(
            instance_id=instance.stem,
            objective=objective,
            status="optimal",
            solver="concorde",
            instance_sha256=sha256_file(instance),
            runtime_seconds=runtime,
            tour_path=str(output_tour),
            solver_exit_code=completed.returncode,
        )
