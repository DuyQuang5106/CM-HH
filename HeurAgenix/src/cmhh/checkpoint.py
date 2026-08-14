from __future__ import annotations

from pathlib import Path
from typing import Any

from cmhh.data.manifest import load_json, write_json_atomic


def save_checkpoint(path: str | Path, state: dict[str, Any]) -> None:
    write_json_atomic(path, state)


def load_checkpoint(path: str | Path) -> dict[str, Any] | None:
    target = Path(path)
    return load_json(target) if target.exists() else None

