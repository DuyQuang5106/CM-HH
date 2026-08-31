from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Iterable

import yaml

from cmhh.config import ExperimentConfig, StreamConfig
from cmhh.models import SearchBudget


MODE_CHOICES = ("smoke", "quick-smoke", "pilot", "full")


MODE_PRESETS: dict[str, dict[str, Any]] = {
    "smoke": {
        "description": "zero-LLM smoke run using built-in baseline heuristics",
        "generator": "baseline",
        "generations": 1,
        "candidates_per_generation": 1,
        "max_llm_calls": 1,
        "evolution_timeout_seconds": 60.0,
    },
    "quick-smoke": {
        "description": "minimal LLM smoke run",
        "generator": "heuragenix",
        "generations": 1,
        "candidates_per_generation": 1,
        "max_llm_calls": 2,
        "evolution_timeout_seconds": 120.0,
    },
    "pilot": {
        "description": "mini-pilot run",
        "generator": "heuragenix",
        "generations": 2,
        "candidates_per_generation": 1,
        "max_llm_calls": 5,
        "evolution_timeout_seconds": 300.0,
    },
    "full": {
        "description": "full benchmark budget from experiment YAML",
        "generator": "heuragenix",
        "evolution_timeout_seconds": 21600.0,
    },
}


CONDITION_EXPERIMENTS: dict[str, str] = {
    "isolated": "cmhh/configs/experiments/h1_isolated.yaml",
    "population": "cmhh/configs/experiments/h1_population_carryover.yaml",
    "naive-bounded": "cmhh/configs/experiments/h1_naive_sequential.yaml",
    "naive-unbounded": "cmhh/configs/experiments/h1_naive_unbounded.yaml",
    "managed": "cmhh/configs/experiments/archivist_managed.yaml",
}


CONDITION_ALIASES: dict[str, str] = {
    "isolated": "isolated",
    "population": "population",
    "population-carryover": "population",
    "naivebounded": "naive-bounded",
    "naive-bounded": "naive-bounded",
    "naive_bounded": "naive-bounded",
    "naiveunbounded": "naive-unbounded",
    "naive-unbounded": "naive-unbounded",
    "naive_unbounded": "naive-unbounded",
    "managed": "managed",
    "archivist-managed": "managed",
    "archivist_managed": "managed",
}


DEFAULT_CONDITIONS = (
    "isolated",
    "population",
    "naive-bounded",
    "naive-unbounded",
    "managed",
)


DEFAULT_STREAMS = (
    "tsp_size_ascending",
    "tsp_size_descending",
    "tsp_random_perm_1",
    "tsp_random_perm_2",
    "cvrp_size_ascending",
    "cvrp_size_descending",
    "jssp_size_ascending",
    "jssp_size_descending",
    "cross_problem_tsp_cvrp_jssp",
    "tsp_revisit",
    "tsp_stationary",
    "related_pair_tsp_cvrp_tsp",
    "unrelated_pair_tsp_jssp_tsp",
)


PILOT_STREAMS = (
    "tsp_size_ascending",
    "cvrp_size_ascending",
    "jssp_size_ascending",
    "cross_problem_tsp_cvrp_jssp",
    "tsp_stationary",
)


def parse_int_values(values: Iterable[str | int] | None) -> tuple[int, ...]:
    if not values:
        return ()
    parsed: list[int] = []
    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                parsed.append(int(item))
    return tuple(parsed)


def parse_string_values(values: Iterable[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    parsed: list[str] = []
    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                parsed.append(item)
    return tuple(parsed)


def normalize_conditions(values: Iterable[str] | None) -> tuple[str, ...]:
    requested = parse_string_values(values) or DEFAULT_CONDITIONS
    normalized: list[str] = []
    for value in requested:
        key = value.strip().lower()
        condition = CONDITION_ALIASES.get(key)
        if condition is None:
            choices = ", ".join(DEFAULT_CONDITIONS)
            raise ValueError(f"Unknown condition '{value}'. Choose from: {choices}")
        if condition not in normalized:
            normalized.append(condition)
    return tuple(normalized)


def resolve_stream_path(stream: str, root: Path) -> Path:
    value = Path(stream)
    if value.is_absolute():
        return value
    if value.exists():
        return value.resolve()
    candidates = [
        root / value,
        root / "cmhh" / "configs" / "streams" / f"{stream}.yaml",
        root / "cmhh" / "configs" / "streams" / stream,
        root / "HeurAgenix" / value,
        root / "HeurAgenix" / "cmhh" / "configs" / "streams" / f"{stream}.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return root / value


def apply_runtime_overrides(
    experiment: ExperimentConfig,
    *,
    mode: str,
    generations: int | None = None,
    candidates_per_generation: int | None = None,
    max_llm_calls: int | None = None,
) -> ExperimentConfig:
    preset = MODE_PRESETS[mode]
    search = experiment.search
    if mode != "full":
        search = SearchBudget(
            generations=int(preset["generations"]),
            candidates_per_generation=int(preset["candidates_per_generation"]),
            max_llm_calls=int(preset["max_llm_calls"]),
        )
    search = SearchBudget(
        generations=int(generations if generations is not None else search.generations),
        candidates_per_generation=int(
            candidates_per_generation
            if candidates_per_generation is not None
            else search.candidates_per_generation
        ),
        max_llm_calls=int(max_llm_calls if max_llm_calls is not None else search.max_llm_calls),
    )
    return replace(experiment, search=search)


def mode_default_generator(mode: str) -> str:
    return str(MODE_PRESETS[mode]["generator"])


def mode_default_timeout(mode: str) -> float:
    return float(MODE_PRESETS[mode]["evolution_timeout_seconds"])


def dataclass_to_plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: dataclass_to_plain(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [dataclass_to_plain(item) for item in value]
    if isinstance(value, list):
        return [dataclass_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): dataclass_to_plain(item) for key, item in value.items()}
    return value


def write_resolved_config(
    path: str | Path,
    *,
    repo_root: Path,
    experiment_path: Path,
    stream_path: Path,
    experiment: ExperimentConfig,
    stream: StreamConfig,
    run_id: str,
    seed: int,
    mode: str,
    generator: str,
    llm_config: Path | None,
    evolution_timeout_seconds: float,
    resume: bool,
    cold_start_scores: Path | None = None,
    command: str | None = None,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "repo_root": str(repo_root),
        "run_id": run_id,
        "seed": seed,
        "mode": mode,
        "generator": generator,
        "llm_config": str(llm_config) if llm_config else None,
        "evolution_timeout_seconds": evolution_timeout_seconds,
        "resume": resume,
        "cold_start_scores": str(cold_start_scores) if cold_start_scores else None,
        "experiment_path": str(experiment_path),
        "stream_path": str(stream_path),
        "experiment": dataclass_to_plain(experiment),
        "stream": dataclass_to_plain(stream),
        "command": command,
    }
    with target.open("w", encoding="utf-8") as fp:
        yaml.safe_dump(payload, fp, sort_keys=False)
