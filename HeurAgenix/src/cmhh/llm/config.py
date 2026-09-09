from __future__ import annotations

import hashlib
import json
from pathlib import Path
from cmhh.env import ensure_environment_loaded, expand_env_vars, sanitize_config
from typing import Any


SECRET_KEYS = {"api_key", "token", "access_token", "client_secret", "password"}


def load_llm_config(path: str | Path) -> dict[str, Any]:
    ensure_environment_loaded()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "type" not in raw:
        raise ValueError("LLM config must be an object containing 'type'")
    return expand_env_vars(raw, strict=True, source_context=str(path))


def sanitized_llm_config(raw: dict[str, Any]) -> dict[str, Any]:
    return sanitize_config(raw, mask="<redacted>")


def llm_config_fingerprint(raw: dict[str, Any]) -> str:
    payload = json.dumps(sanitized_llm_config(raw), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def write_sanitized_snapshot(path: str | Path, raw: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(sanitized_llm_config(raw), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

