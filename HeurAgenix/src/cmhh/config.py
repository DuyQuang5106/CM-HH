from __future__ import annotations

from dataclasses import dataclass, field
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
class ArchiveConfig:
    policy: str = "naive_overwrite"
    capacity: int | None = 20
    top_k: int = 5


@dataclass(frozen=True)
class WandbConfig:
    enabled: bool = False
    project: str = "cmhh"
    entity: str | None = None
    mode: str = "online"
    tags: tuple[str, ...] = ()
    run_name: str | None = None


@dataclass(frozen=True)
class TrackingConfig:
    wandb: WandbConfig = field(default_factory=WandbConfig)


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    condition: str
    output_root: Path
    seeds: tuple[int, ...]
    data: DataConfig
    search: SearchBudget
    evaluation: EvaluationBudget
    archive: ArchiveConfig = field(default_factory=ArchiveConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)


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

    archive_raw = raw.get("archive", {})
    capacity = archive_raw.get("capacity", 20)
    if isinstance(capacity, str) and capacity.lower() in {"unbounded", "none", "null", "inf", "infinite"}:
        capacity = None
    elif capacity is not None:
        capacity = int(capacity)
        if capacity <= 0:
            capacity = None

    archive = ArchiveConfig(
        policy=archive_raw.get("policy", "naive_overwrite"),
        capacity=capacity,
        top_k=int(archive_raw.get("top_k", 5)),
    )

    tracking_raw = raw.get("tracking", {})
    wandb_raw = tracking_raw.get("wandb", {}) if isinstance(tracking_raw, dict) else {}
    tracking = TrackingConfig(
        wandb=WandbConfig(
            enabled=bool(wandb_raw.get("enabled", False)),
            project=str(wandb_raw.get("project", "cmhh")),
            entity=wandb_raw.get("entity"),
            mode=str(wandb_raw.get("mode", "online")),
            tags=tuple(wandb_raw.get("tags", ())),
            run_name=wandb_raw.get("run_name"),
        )
    )

    return ExperimentConfig(
        name=experiment["name"],
        condition=experiment.get("condition", "independent_seed"),
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
        archive=archive,
        tracking=tracking,
    )


def load_stream_config(path: str | Path) -> StreamConfig:
    raw = load_yaml(path)
    return StreamConfig(
        stream_id=raw["stream_id"],
        task_ids=tuple(raw["task_ids"]),
        description=raw.get("description", ""),
    )
