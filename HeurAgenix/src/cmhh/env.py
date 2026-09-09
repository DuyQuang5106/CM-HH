from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

VAR_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)(?::-([^}]*))?\}")

SENSITIVE_KEY_MARKERS = {
    "api_key",
    "apikey",
    "api_token",
    "access_token",
    "refresh_token",
    "authorization",
    "bearer_token",
    "password",
    "secret",
    "client_secret",
}

_ENV_LOADED_ONCE = False


class MissingEnvironmentVariableError(ValueError):
    """Raised when an explicit ${VAR} reference cannot be resolved."""

    def __init__(self, var_name: str, source_context: str = "", field_name: str = "") -> None:
        parts = [f"Required environment variable '{var_name}' is not set."]
        if source_context:
            parts.append(f"Referenced from: {source_context}")
        if field_name:
            parts.append(f"field: {field_name}")
        super().__init__("\n".join(parts))
        self.var_name = var_name
        self.source_context = source_context
        self.field_name = field_name


def find_repo_root(start_path: Path | str | None = None) -> Path:
    """Finds the root repository directory anchored by pyproject.toml or .git.
    
    Does NOT search upwards beyond the anchor root into parent user directories.
    """
    current = Path(start_path).resolve() if start_path else Path.cwd().resolve()
    for directory in [current, *current.parents]:
        if (directory / "pyproject.toml").is_file() or (directory / ".git").is_dir():
            return directory
    return current


def find_root_env_file(repo_root: Path | str | None = None) -> Path | None:
    """Discovers <repo_root>/.env. Strictly anchored to repo root."""
    root = Path(repo_root).resolve() if repo_root else find_repo_root()
    env_path = root / ".env"
    return env_path if env_path.is_file() else None


def load_environment(env_file: Path | str | None = None, *, override: bool = False) -> bool:
    """Loads environment variables into os.environ using python-dotenv.
    
    Defaults to override=False (Process Environment > .env).
    """
    target = Path(env_file).resolve() if env_file else find_root_env_file()
    if target is None or not target.is_file():
        return False
    return load_dotenv(dotenv_path=target, override=override)


def ensure_environment_loaded() -> None:
    """Idempotently loads .env once at application startup."""
    global _ENV_LOADED_ONCE
    if not _ENV_LOADED_ONCE:
        load_environment(override=False)
        _ENV_LOADED_ONCE = True


def expand_env_vars(
    data: Any,
    *,
    strict: bool = True,
    source_context: str = "",
    field_name: str = "",
) -> Any:
    """Recursively resolves ${VAR_NAME} or ${VAR_NAME:-default} in dictionaries, lists, and strings.
    
    When strict=True, raises MissingEnvironmentVariableError for unset variables without defaults.
    """
    if isinstance(data, str):
        def _replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default_val = match.group(2)
            if var_name in os.environ:
                return os.environ[var_name]
            if default_val is not None:
                return default_val
            if strict:
                raise MissingEnvironmentVariableError(
                    var_name=var_name,
                    source_context=source_context,
                    field_name=field_name,
                )
            return match.group(0)

        return VAR_PATTERN.sub(_replace, data)

    if isinstance(data, dict):
        return {
            key: expand_env_vars(
                value,
                strict=strict,
                source_context=source_context,
                field_name=str(key),
            )
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [
            expand_env_vars(
                item,
                strict=strict,
                source_context=source_context,
                field_name=field_name,
            )
            for item in data
        ]

    if isinstance(data, tuple):
        return tuple(
            expand_env_vars(
                item,
                strict=strict,
                source_context=source_context,
                field_name=field_name,
            )
            for item in data
        )

    return data


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_KEY_MARKERS or any(
        marker in normalized for marker in ["api_key", "secret", "token", "password", "authorization"]
    )


def sanitize_config(config: Any, mask: str = "<redacted>") -> Any:
    """Returns a deep-copied version of config with all sensitive secrets redacted.
    
    Guarantees that the runtime configuration object is NEVER mutated in-place.
    """
    copied = copy.deepcopy(config)

    def _sanitize(item: Any) -> Any:
        if isinstance(item, dict):
            sanitized_dict: dict[str, Any] = {}
            for k, v in item.items():
                if _is_sensitive_key(str(k)):
                    sanitized_dict[k] = mask
                else:
                    sanitized_dict[k] = _sanitize(v)
            return sanitized_dict

        if isinstance(item, list):
            return [_sanitize(elem) for elem in item]

        if isinstance(item, tuple):
            return tuple(_sanitize(elem) for elem in item)

        if isinstance(item, str):
            # Check for header-like Authorization: Bearer ... strings
            if item.lower().startswith("bearer ") or item.lower().startswith("basic "):
                return mask

        return item

    return _sanitize(copied)
