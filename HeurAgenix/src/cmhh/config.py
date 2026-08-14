from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cmhh.models import EvaluationBudget, SearchBudget


@dataclass(frozen=True)
class DataConfig:
    seed: int
    coordinate_min: int
    coordinate_max: int
    splits: dict[str, int]


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    output_root: Path
    seeds: tuple[int, ...]
    data: DataConfig
    search: SearchBudget
    evaluation: EvaluationBudget


@dataclass(frozen=True)
class StreamConfig:
    stream_id: str
    task_ids: tuple[str, ...]
    description: str = ""


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return raw


def load_experiment_config(path: str | Path, repo_root: str | Path) -> ExperimentConfig:
    raw = load_yaml(path)
    root = Path(repo_root).resolve()
    experiment = raw["experiment"]
    data = raw["data"]
    search = raw["search"]
    evaluation = raw["evaluation"]
    output_root = Path(experiment["output_root"])
    if not output_root.is_absolute():
        output_root = root / output_root
    return ExperimentConfig(
        name=experiment["name"],
        output_root=output_root,
        seeds=tuple(int(seed) for seed in experiment["seeds"]),
        data=DataConfig(
            seed=int(data["seed"]),
            coordinate_min=int(data["coordinate_min"]),
            coordinate_max=int(data["coordinate_max"]),
            splits={name: int(count) for name, count in data["splits"].items()},
        ),
        search=SearchBudget(**search),
        evaluation=EvaluationBudget(**evaluation),
    )


def load_stream_config(path: str | Path) -> StreamConfig:
    raw = load_yaml(path)
    return StreamConfig(
        stream_id=raw["stream_id"],
        task_ids=tuple(raw["task_ids"]),
        description=raw.get("description", ""),
    )
