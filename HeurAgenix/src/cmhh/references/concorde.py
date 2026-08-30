import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from cmhh.config import load_yaml
from cmhh.data.manifest import sha256_file
from cmhh.data.references import ReferenceRecord
from cmhh.data.tsp_io import read_euc2d_coordinates
from cmhh.references.tour import parse_concorde_tour, tour_objective, write_normalized_tour


class ConcordeNotFoundError(FileNotFoundError):
    """Raised when the Concorde executable cannot be located with actionable guidance."""
    pass


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


def resolve_concorde_executable(
    explicit_path: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> Path:
    """Resolves the Concorde executable path according to the resolution hierarchy:
    
    1. Explicit config path (`executable:` or `command_prefix[0]`)
    2. CONCORDE_PATH / CONCORDE_EXECUTABLE environment variable
    3. System PATH lookup (`shutil.which("concorde")`)
    4. Known local tools directory (`tools/concorde/concorde.exe`)
    5. Actionable ConcordeNotFoundError if missing.
    """
    root = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
    checked_locations: list[str] = []

    # 1. Explicit config path
    if explicit_path and str(explicit_path).strip() and str(explicit_path).lower() != "null":
        p = Path(explicit_path)
        if p.is_absolute() and p.exists():
            return p.resolve()
        candidate = root / p
        checked_locations.append(f"explicit config: {p} (resolved: {candidate})")
        if candidate.exists():
            return candidate.resolve()
        if p.exists():
            return p.resolve()
    else:
        checked_locations.append("explicit config: <not specified>")

    # 2. Environment variable
    env_path = os.environ.get("CONCORDE_PATH") or os.environ.get("CONCORDE_EXECUTABLE")
    if env_path:
        checked_locations.append(f"CONCORDE_PATH: {env_path}")
        ep = Path(env_path)
        if ep.exists():
            return ep.resolve()
        if (root / ep).exists():
            return (root / ep).resolve()
    else:
        checked_locations.append("CONCORDE_PATH: <not set>")

    # 3. System PATH lookup
    which_names = ["concorde", "concorde.exe"] if os.name == "nt" else ["concorde"]
    found_in_path = None
    for name in which_names:
        w = shutil.which(name)
        if w:
            found_in_path = Path(w).resolve()
            return found_in_path
    checked_locations.append(f"system PATH: {', '.join(which_names)} (not found in PATH)")

    # 4. Known local tools directory
    local_candidates = [
        root / "tools" / "concorde" / "concorde.exe",
        root / "tools" / "concorde" / "concorde",
        root / "HeurAgenix" / "tools" / "concorde" / "concorde.exe",
        root / "HeurAgenix" / "tools" / "concorde" / "concorde",
        Path.cwd() / "tools" / "concorde" / "concorde.exe",
        Path.cwd() / "tools" / "concorde" / "concorde",
    ]
    for lc in local_candidates:
        checked_locations.append(f"local tool: {lc}")
        if lc.exists() and lc.is_file():
            return lc.resolve()

    # 5. Build actionable error message
    details = "\n".join(f"  - {loc}" for loc in checked_locations)
    error_msg = (
        "Concorde executable was not found.\n\n"
        "TSP reference generation requires Concorde to compute proven optimal reference solutions.\n\n"
        "Checked:\n"
        f"{details}\n\n"
        "To fix this:\n"
        "  1. Install or download Concorde (https://www.math.uwaterloo.ca/tsp/concorde.html).\n"
        "  2. Set the CONCORDE_PATH environment variable:\n"
        "     PowerShell:  $env:CONCORDE_PATH=\"C:\\path\\to\\concorde.exe\"\n"
        "     Bash / Unix: export CONCORDE_PATH=\"/usr/local/bin/concorde\"\n"
        "  3. Or configure `executable:` in cmhh/configs/solvers/concorde.yaml.\n\n"
        "CVRP (PyVRP) and JSSP (OR-Tools CP-SAT) reference solvers do not require external binaries;\n"
        "they are installed automatically through `uv sync`."
    )
    raise ConcordeNotFoundError(error_msg)


def load_concorde_config(path: str | Path, repo_root: str | Path | None = None) -> ConcordeConfig:
    raw = load_yaml(path)["solver"]
    root = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
    
    explicit_exe = raw.get("executable")
    prefix = list(raw.get("command_prefix", []))
    candidate = explicit_exe or (prefix[0] if prefix else None)

    try:
        resolved_exe = resolve_concorde_executable(candidate, root)
        if prefix:
            prefix[0] = str(resolved_exe)
        else:
            prefix = [str(resolved_exe)]
    except ConcordeNotFoundError:
        if prefix:
            first = Path(prefix[0])
            if not first.is_absolute() and (root / first).exists():
                prefix[0] = str(root / first)
            elif first.exists():
                prefix[0] = str(first.resolve())
            else:
                prefix[0] = str(candidate or "concorde.exe")
        else:
            prefix = [str(candidate or "concorde.exe")]

    return ConcordeConfig(
        command_prefix=tuple(prefix),
        arguments=tuple(str(item) for item in raw.get("arguments", ["-x", "-o", "{tour_path}", "{instance_path}"])),
        max_workers=max(1, int(raw.get("max_workers", 1))),
        timeouts={key: float(value) for key, value in raw.get("timeouts", {"n20": 60, "n50": 300, "n100": 900, "n200": 1800}).items()},
    )


def validate_solver_command(config: ConcordeConfig, repo_root: str | Path | None = None) -> None:
    if not config.command_prefix:
        resolve_concorde_executable(None, repo_root)
    executable = Path(config.command_prefix[0])
    if not executable.exists():
        resolve_concorde_executable(config.command_prefix[0], repo_root)



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
