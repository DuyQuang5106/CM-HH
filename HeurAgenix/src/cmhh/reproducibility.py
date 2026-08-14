from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from cmhh.data.manifest import sha256_file, write_json_atomic


def _git_value(repo_root: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def create_run_manifest(
    path: str | Path,
    repo_root: str | Path,
    run_id: str,
    seed: int,
    config_paths: list[str | Path],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    status = _git_value(root, "status", "--porcelain")
    manifest: dict[str, Any] = {
        "version": 1,
        "run_id": run_id,
        "seed": seed,
        "git_commit": _git_value(root, "rev-parse", "HEAD"),
        "git_dirty": bool(status),
        "python_version": sys.version,
        "platform": platform.platform(),
        "configs": {
            str(Path(item)): sha256_file(item) for item in config_paths
        },
    }
    if extra:
        manifest.update(extra)
    write_json_atomic(path, manifest)
    return manifest

