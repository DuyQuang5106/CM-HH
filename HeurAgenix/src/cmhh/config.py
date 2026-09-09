from __future__ import annotations

from dataclasses import dataclass, field, replace
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
    candidate_top_k: int | None = None
    memory_seed_quota: int = 1
    direct_reuse_quota: int = 1
    refine_quota: int | None = None


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


@dataclass(frozen=True)
class ConditionSpec:
    name: str
    condition: str
    archive: ArchiveConfig


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return raw


def load_experiment_config(path: str | Path, repo_root: str | Path) -> ExperimentConfig:
    raw = load_yaml(path)
    root = Path(repo_root).resolve()
    experiment = raw.get("experiment", raw)
    data = raw.get("data", {
        "seed": 42,
        "coordinate_min": 0,
        "coordinate_max": 10000,
        "splits": {"train": 20, "validation": 10, "test": 30, "smoke": 2},
    })
    search = raw.get("search", {
        "generations": 100,
        "candidates_per_generation": 5,
        "max_llm_calls": 500,
    })
    evaluation = raw.get("evaluation", {
        "instance_timeout_seconds": 30,
        "batch_timeout_seconds": 900,
        "invalid_policy": "fail_batch",
    })
    output_root = Path(experiment.get("output_root", "cmhh/results"))
    if not output_root.is_absolute():
        output_root = root / output_root

    archive_raw = raw.get("archive", {})
    capacity = archive_raw.get("capacity", 20)
    if isinstance(capacity, str) and capacity.lower() in {"unbounded", "none", "null", "inf", "infinite"}:
        capacity = None
    elif capacity is not None:
        capacity = int(capacity)
        if capacity < 0:
            capacity = None

    archive = ArchiveConfig(
        policy=archive_raw.get("policy", "naive_overwrite"),
        capacity=capacity,
        top_k=int(archive_raw.get("top_k", 5)),
        candidate_top_k=(
            None if archive_raw.get("candidate_top_k") is None
            else int(archive_raw["candidate_top_k"])
        ),
        memory_seed_quota=int(archive_raw.get("memory_seed_quota", 1)),
        direct_reuse_quota=int(archive_raw.get("direct_reuse_quota", 1)),
        refine_quota=(
            None if archive_raw.get("refine_quota") is None
            else int(archive_raw["refine_quota"])
        ),
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
        name=experiment.get("name", "benchmark_default"),
        condition=experiment.get("condition", "independent_seed"),
        output_root=output_root,
        seeds=tuple(int(seed) for seed in experiment.get("seeds", [1, 2, 3])),
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


def load_base_experiment_config(repo_root: str | Path, path: str | Path | None = None) -> ExperimentConfig:
    root = Path(repo_root).resolve()
    if path is None:
        candidates = [
            root / "cmhh" / "configs" / "experiments" / "defaults.yaml",
            root / "HeurAgenix" / "cmhh" / "configs" / "experiments" / "defaults.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break
        if path is None:
            path = candidates[0]
    return load_experiment_config(path, root)


def load_conditions_registry(repo_root: str | Path, path: str | Path | None = None) -> dict[str, ConditionSpec]:
    root = Path(repo_root).resolve()
    if path is None:
        candidates = [
            root / "cmhh" / "configs" / "conditions.yaml",
            root / "HeurAgenix" / "cmhh" / "configs" / "conditions.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break
        if path is None:
            path = candidates[0]

    raw = load_yaml(path)
    conditions_dict = raw.get("conditions", raw)
    registry: dict[str, ConditionSpec] = {}
    for name, spec in conditions_dict.items():
        cond_str = spec.get("condition", name)
        arch_raw = spec.get("archive", {})
        capacity = arch_raw.get("capacity", 20)
        if isinstance(capacity, str) and capacity.lower() in {"unbounded", "none", "null", "inf", "infinite"}:
            capacity = None
        elif capacity is not None:
            capacity = int(capacity)
            if capacity < 0:
                capacity = None

        archive = ArchiveConfig(
            policy=arch_raw.get("policy", "naive_overwrite"),
            capacity=capacity,
            top_k=int(arch_raw.get("top_k", 5)),
            candidate_top_k=(
                None if arch_raw.get("candidate_top_k") is None
                else int(arch_raw["candidate_top_k"])
            ),
            memory_seed_quota=int(arch_raw.get("memory_seed_quota", 1)),
            direct_reuse_quota=int(arch_raw.get("direct_reuse_quota", 1)),
            refine_quota=(
                None if arch_raw.get("refine_quota") is None
                else int(arch_raw["refine_quota"])
            ),
        )
        registry[name] = ConditionSpec(name=name, condition=cond_str, archive=archive)
    return registry


def compose_experiment_config(
    *,
    base: ExperimentConfig,
    condition_spec: ConditionSpec | None = None,
    suite: SuiteConfig | None = None,
    condition_name: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> ExperimentConfig:
    cfg = base
    if condition_spec is not None:
        cfg = replace(
            cfg,
            name=f"{base.name}_{condition_spec.name}",
            condition=condition_spec.condition,
            archive=condition_spec.archive,
        )
    elif condition_name is not None:
        cfg = replace(cfg, condition=condition_name)

    if suite is not None:
        if suite.splits:
            new_splits = dict(cfg.data.splits)
            new_splits.update(suite.splits)
            cfg = replace(cfg, data=replace(cfg.data, splits=new_splits))
        if suite.seeds:
            cfg = replace(cfg, seeds=suite.seeds)
        if suite.llm_budget_per_task is not None:
            cfg = replace(cfg, search=replace(cfg.search, max_llm_calls=suite.llm_budget_per_task))

    if overrides:
        if "search" in overrides:
            cfg = replace(cfg, search=overrides["search"])
        if "evaluation" in overrides:
            cfg = replace(cfg, evaluation=overrides["evaluation"])
        if "data" in overrides:
            cfg = replace(cfg, data=overrides["data"])
        if "output_root" in overrides:
            cfg = replace(cfg, output_root=Path(overrides["output_root"]))
        if "seeds" in overrides:
            cfg = replace(cfg, seeds=tuple(overrides["seeds"]))
    return cfg


def load_stream_config(path: str | Path) -> StreamConfig:
    p = Path(path)
    raw = load_yaml(p)
    stream_id = raw.get("stream_id") or raw.get("id") or p.stem
    task_ids = raw.get("task_ids") or raw.get("tasks") or ()
    return StreamConfig(
        stream_id=stream_id,
        task_ids=tuple(task_ids),
        description=raw.get("description", ""),
    )


@dataclass(frozen=True)
class SuiteConfig:
    suite_id: str
    streams: tuple[str, ...]
    conditions: tuple[str, ...] = ()
    seeds: tuple[int, ...] = (1,)
    mode: str = "pilot"
    llm_budget_per_task: int | None = None
    description: str = ""
    splits: dict[str, int] = field(default_factory=dict)
    base_experiment: str | None = None


def load_suite_config(path: str | Path) -> SuiteConfig:
    raw = load_yaml(path)
    return SuiteConfig(
        suite_id=raw["suite_id"],
        streams=tuple(raw["streams"]),
        conditions=tuple(raw.get("conditions", ())),
        seeds=tuple(int(s) for s in raw.get("seeds", [1])),
        mode=raw.get("mode", "pilot"),
        llm_budget_per_task=raw.get("llm_budget_per_task"),
        description=raw.get("description", ""),
        splits={k: int(v) for k, v in raw.get("splits", {}).items()},
        base_experiment=raw.get("base_experiment"),
    )
