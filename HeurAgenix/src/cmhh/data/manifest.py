from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json_atomic(path: str | Path, content: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    unique_suffix = f"{os.getpid()}_{threading.get_ident()}_{time.time_ns()}"
    temp = target.with_name(f".{target.name}.{unique_suffix}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as fp:
            json.dump(content, fp, indent=2, sort_keys=True)
            fp.write("\n")
        
        # Windows-safe atomic replace with retry on transient file locks
        max_retries = 10
        for attempt in range(max_retries):
            try:
                os.replace(temp, target)
                break
            except PermissionError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if temp.exists():
            try:
                temp.unlink(missing_ok=True)
            except Exception:
                pass
