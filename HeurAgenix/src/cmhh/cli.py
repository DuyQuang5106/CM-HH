from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from cmhh.agents.eoh_generator import EOHGenerator
from cmhh.agents.generator import BaselineGenerator
from cmhh.agents.heuragenix_generator import HeurAgenixGenerator
from cmhh.audit import audit_run
from cmhh.baselines import baseline_artifacts
from cmhh.config import (
    ExperimentConfig,
    TrackingConfig,
    WandbConfig,
    load_experiment_config,
    load_stream_config,
)
from cmhh.data import generate_data_for_tasks
from cmhh.data.manifest import load_json, sha256_file, write_json_atomic
from cmhh.evaluation.evaluator import Evaluator
from cmhh.references.concorde import load_concorde_config, validate_solver_command
from cmhh.references.pipeline import generate_task_references
from cmhh.references.verification import verify_task_references
from cmhh.reporting import print_evaluation_summary, write_evaluation
from cmhh.reproducibility import create_run_manifest
from cmhh.runner import StreamRunner
from cmhh.runtime import (
    CONDITION_EXPERIMENTS,
    DEFAULT_CONDITIONS,
    DEFAULT_STREAMS,
    MODE_CHOICES,
    PILOT_STREAMS,
    apply_runtime_overrides,
    mode_default_generator,
    mode_default_timeout,
    normalize_conditions,
    parse_int_values,
    parse_string_values,
    resolve_stream_path,
    write_resolved_config,
)
from cmhh.tasks import load_task_registry
from cmhh.validation import validate_configuration

DEFAULT_EXPERIMENT = "cmhh/configs/experiments/phase0_tsp.yaml"
DEFAULT_STREAM = "cmhh/configs/streams/tsp_size_ascending.yaml"


def _apply_tracking_overrides(experiment: ExperimentConfig, args: argparse.Namespace) -> ExperimentConfig:
    tracking = experiment.tracking
    if (
        getattr(args, "wandb", None) is not None
        or getattr(args, "wandb_project", None)
        or getattr(args, "wandb_mode", None)
        or getattr(args, "wandb_entity", None)
        or getattr(args, "wandb_tags", None)
        or getattr(args, "wandb_run_name", None)
    ):
        enabled = args.wandb if getattr(args, "wandb", None) is not None else tracking.wandb.enabled
        if getattr(args, "wandb_mode", None):
            enabled = args.wandb_mode != "disabled"
        tracking = TrackingConfig(
            wandb=WandbConfig(
                enabled=enabled,
                project=args.wandb_project or tracking.wandb.project,
                entity=args.wandb_entity or tracking.wandb.entity,
                mode=args.wandb_mode or tracking.wandb.mode,
                tags=tuple(args.wandb_tags) if args.wandb_tags else tracking.wandb.tags,
                run_name=args.wandb_run_name or tracking.wandb.run_name,
            )
        )
        return ExperimentConfig(
            name=experiment.name,
            condition=experiment.condition,
            output_root=experiment.output_root,
            seeds=experiment.seeds,
            data=experiment.data,
            search=experiment.search,
            evaluation=experiment.evaluation,
            archive=experiment.archive,
            tracking=tracking,
        )
    return experiment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CM-HH experimental tooling")
    parser.add_argument("--repo-root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config")
    _add_config_arguments(validate)

    generate = subparsers.add_parser("generate-data")
    _add_config_arguments(generate)
    generate.add_argument("--seed", type=int)

    baselines = subparsers.add_parser("evaluate-baselines")
    _add_config_arguments(baselines)
    baselines.add_argument("--task", action="append")
    baselines.add_argument("--split", choices=("smoke", "validation", "test"), default="smoke")

    run_stream = subparsers.add_parser("run-stream")
    _add_config_arguments(run_stream)
    run_stream.add_argument("--seed", type=int)
    run_stream.add_argument("--seeds", nargs="+", help="One or more seeds, e.g. --seeds 1 2 3 or --seeds 1,2,3")
    run_stream.add_argument("--run-id")
    run_stream.add_argument("--resume", action="store_true")
    run_stream.add_argument("--mode", choices=MODE_CHOICES, default="full")
    run_stream.add_argument("--generator", choices=("baseline", "heuragenix", "eoh"), default="baseline")
    run_stream.add_argument("--llm-config")
    run_stream.add_argument("--evolution-timeout", type=float)
    run_stream.add_argument("--override-generations", type=int)
    run_stream.add_argument("--override-candidates-per-generation", type=int)
    run_stream.add_argument("--override-max-llm-calls", type=int)
    run_stream.add_argument("--cold-start-scores")
    run_stream.add_argument("--wandb", dest="wandb", action="store_true", default=None, help="Enable Weights & Biases tracking")
    run_stream.add_argument("--no-wandb", dest="wandb", action="store_false", help="Disable Weights & Biases tracking")
    run_stream.add_argument("--wandb-project", help="W&B project name override")
    run_stream.add_argument("--wandb-entity", help="W&B entity name override")
    run_stream.add_argument("--wandb-mode", choices=("online", "offline", "disabled"), help="W&B tracking mode override")
    run_stream.add_argument("--wandb-tags", action="append", help="W&B run tags")
    run_stream.add_argument("--wandb-run-name", help="W&B run name override")

    isolated = subparsers.add_parser("run-isolated")
    _add_config_arguments(isolated)
    isolated.add_argument("--seed", type=int)
    isolated.add_argument("--seeds", nargs="+", help="One or more seeds, e.g. --seeds 1 2 3 or --seeds 1,2,3")
    isolated.add_argument("--run-id")
    isolated.add_argument("--mode", choices=MODE_CHOICES, default="full")
    isolated.add_argument("--generator", choices=("baseline", "heuragenix", "eoh"), default="baseline")
    isolated.add_argument("--llm-config")
    isolated.add_argument("--evolution-timeout", type=float)
    isolated.add_argument("--override-generations", type=int)
    isolated.add_argument("--override-candidates-per-generation", type=int)
    isolated.add_argument("--override-max-llm-calls", type=int)
    isolated.add_argument("--wandb", dest="wandb", action="store_true", default=None, help="Enable Weights & Biases tracking")
    isolated.add_argument("--no-wandb", dest="wandb", action="store_false", help="Disable Weights & Biases tracking")
    isolated.add_argument("--wandb-project", help="W&B project name override")
    isolated.add_argument("--wandb-entity", help="W&B entity name override")
    isolated.add_argument("--wandb-mode", choices=("online", "offline", "disabled"), help="W&B tracking mode override")
    isolated.add_argument("--wandb-tags", action="append", help="W&B run tags")
    isolated.add_argument("--wandb-run-name", help="W&B run name override")

    evolve = subparsers.add_parser("evolve-task")
    _add_config_arguments(evolve)
    evolve.add_argument("--task", required=True)
    evolve.add_argument("--llm-config", required=True)
    evolve.add_argument("--seed", type=int, default=42)
    evolve.add_argument("--max-llm-calls", type=int)
    evolve.add_argument("--run-id")
    evolve.add_argument("--evolution-timeout", type=float, default=3600)

    audit = subparsers.add_parser("audit-run")
    audit.add_argument("--run-id", required=True)
    audit.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    audit.add_argument("--stream", default=DEFAULT_STREAM)

    references = subparsers.add_parser("generate-references")
    _add_config_arguments(references)
    references.add_argument("--solver-config", default=None, help="Path to solver config YAML (concorde.yaml, pyvrp.yaml, ortools_cpsat.yaml)")
    references.add_argument("--split", action="append", choices=("validation", "test"), default=None)
    references.add_argument("--task", action="append")
    references.add_argument("--pilot-count", type=int)

    verify = subparsers.add_parser("verify-references")
    _add_config_arguments(verify)
    verify.add_argument("--split", action="append", choices=("validation", "test"), default=None)
    verify.add_argument("--task", action="append")

    suite = subparsers.add_parser("run-suite", help="Run one or more streams across standard CM-HH conditions")
    suite.add_argument("--streams", nargs="+", help="Stream names or paths. Defaults to the phase-1 stream suite.")
    suite.add_argument("--conditions", nargs="+", help="Conditions: isolated, population, naive-bounded, naive-unbounded, managed")
    suite.add_argument("--seeds", nargs="+", default=["1"], help="One or more seeds, e.g. --seeds 1 2 3 or --seeds 1,2,3")
    suite.add_argument("--run-prefix")
    suite.add_argument("--mode", choices=MODE_CHOICES, default="quick-smoke")
    suite.add_argument("--generator", choices=("baseline", "heuragenix", "eoh"))
    suite.add_argument("--llm-config", default="cmhh/configs/llm/llm_config.local.json")
    suite.add_argument("--skip-references", action="store_true")
    suite.add_argument("--prepare-only", action="store_true")
    suite.add_argument("--resume", action="store_true")
    suite.add_argument("--skip-isolated", action="store_true")
    suite.add_argument("--skip-managed", action="store_true")
    suite.add_argument("--include-eoh", action="store_true")
    suite.add_argument("--all-streams", action="store_true", help="Use all streams even in pilot mode")
    suite.add_argument("--eoh-evaluation-timeout", type=int, default=180)
    suite.add_argument("--evolution-timeout", type=float)
    suite.add_argument("--override-generations", type=int)
    suite.add_argument("--override-candidates-per-generation", type=int)
    suite.add_argument("--override-max-llm-calls", type=int)
    suite.add_argument("--wandb", dest="wandb", action="store_true", default=None)
    suite.add_argument("--no-wandb", dest="wandb", action="store_false")
    suite.add_argument("--wandb-project")
    suite.add_argument("--wandb-entity")
    suite.add_argument("--wandb-mode", choices=("online", "offline", "disabled"))
    suite.add_argument("--wandb-tags", action="append")
    suite.add_argument("--wandb-run-name")
    return parser


def _add_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--stream", default=DEFAULT_STREAM)


def _resolve(path: str, root: Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    if value.exists():
        return value.resolve()
    if (root / value).exists():
        return (root / value).resolve()
    if (root / "HeurAgenix" / value).exists():
        return (root / "HeurAgenix" / value).resolve()
    return root / value


def _select_seeds(args: argparse.Namespace, experiment: ExperimentConfig) -> tuple[int, ...]:
    seed = getattr(args, "seed", None)
    seeds = parse_int_values(getattr(args, "seeds", None))
    if seed is not None and seeds:
        raise ValueError("Use either --seed or --seeds, not both.")
    if seeds:
        return seeds
    if seed is not None:
        return (int(seed),)
    return (int(experiment.seeds[0]),)


def _run_id_for_seed(
    *,
    requested: str | None,
    prefix: str,
    seed: int,
    multiple_seeds: bool,
) -> str:
    if requested:
        return f"{requested}_seed{seed}" if multiple_seeds else requested
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}_seed{seed}" if multiple_seeds else f"{prefix}_{stamp}"


def _build_generator(
    *,
    args: argparse.Namespace,
    root: Path,
    run_dir: Path,
    generator_name: str,
    evolution_timeout: float,
):
    if generator_name in {"heuragenix", "eoh"}:
        if not args.llm_config:
            raise ValueError(f"--llm-config is required for --generator {generator_name}")
        generator_cls = HeurAgenixGenerator if generator_name == "heuragenix" else EOHGenerator
        return generator_cls(
            repo_root=root,
            llm_config_path=_resolve(args.llm_config, root),
            output_root=run_dir / "generator",
            timeout_seconds=evolution_timeout,
        )
    return BaselineGenerator(root)


def _resolve_evolution_timeout(args: argparse.Namespace, mode: str, *, fallback: float = 3600.0) -> float:
    value = getattr(args, "evolution_timeout", None)
    if value is not None:
        return float(value)
    return mode_default_timeout(mode) if mode else fallback


def _apply_run_overrides(experiment: ExperimentConfig, args: argparse.Namespace) -> ExperimentConfig:
    return apply_runtime_overrides(
        experiment,
        mode=getattr(args, "mode", "full"),
        generations=getattr(args, "override_generations", None),
        candidates_per_generation=getattr(args, "override_candidates_per_generation", None),
        max_llm_calls=getattr(args, "override_max_llm_calls", None),
    )


def _create_runner_run(
    *,
    root: Path,
    registry,
    experiment_path: Path,
    stream_path: Path,
    experiment: ExperimentConfig,
    stream: StreamConfig,
    args: argparse.Namespace,
    run_id: str,
    seed: int,
    generator_name: str,
    evolution_timeout: float,
    cold_start_scores_path: Path | None = None,
    write_cold_start_scores: bool = False,
    command_name: str = "run-stream",
) -> dict[int, dict[int, float]]:
    run_dir = experiment.output_root / run_id
    checkpoint_path = run_dir / "checkpoints/latest.json"

    if not getattr(args, "resume", False) and checkpoint_path.exists():
        raise RuntimeError(f"Run directory {run_dir} exists; pass --resume to continue")

    evaluator = Evaluator(root, experiment.evaluation)
    generator = _build_generator(
        args=args,
        root=root,
        run_dir=run_dir,
        generator_name=generator_name,
        evolution_timeout=evolution_timeout,
    )
    cold_start_scores = (
        load_json(cold_start_scores_path)
        if cold_start_scores_path is not None and cold_start_scores_path.exists()
        else None
    )

    runner = StreamRunner(
        registry=registry,
        stream=stream,
        experiment=experiment,
        evaluator=evaluator,
        generator=generator,
        run_dir=run_dir,
        seed=seed,
        cold_start_scores=cold_start_scores,
    )

    llm_config = (
        _resolve(args.llm_config, root)
        if generator_name in {"heuragenix", "eoh"} and getattr(args, "llm_config", None)
        else None
    )
    write_resolved_config(
        run_dir / "resolved_config.yaml",
        repo_root=root,
        experiment_path=experiment_path,
        stream_path=stream_path,
        experiment=experiment,
        stream=stream,
        run_id=run_id,
        seed=seed,
        mode=getattr(args, "mode", "full"),
        generator=generator_name,
        llm_config=llm_config,
        evolution_timeout_seconds=evolution_timeout,
        resume=bool(getattr(args, "resume", False)),
        cold_start_scores=cold_start_scores_path,
        command=command_name,
    )
    create_run_manifest(
        path=run_dir / "manifest.json",
        repo_root=root,
        run_id=run_id,
        seed=seed,
        config_paths=[experiment_path, stream_path],
        extra={
            "task_ids": list(stream.task_ids),
            "mode": getattr(args, "mode", "full"),
            "generator": generator_name,
            "resolved_config": str(run_dir / "resolved_config.yaml"),
        },
    )

    matrix = runner.run()
    if write_cold_start_scores:
        cold_start_scores = {
            index: matrix[index][index]
            for index in range(len(stream.task_ids))
            if index in matrix and index in matrix[index]
        }
        write_json_atomic(run_dir / "cold_start_scores.json", cold_start_scores)
    return matrix


def _print_matrix_summary(run_id: str, stream: StreamConfig, matrix: dict[int, dict[int, float]], *, isolated: bool = False) -> None:
    print(f"Completed {'isolated ' if isolated else ''}run {run_id}:")
    for after_idx, row in sorted(matrix.items()):
        if isolated:
            print(f"  Task {after_idx} ({stream.task_ids[after_idx]}): T{after_idx}={row.get(after_idx, 0.0):.4f}")
        else:
            row_str = ", ".join(f"T{j}={score:.4f}" for j, score in sorted(row.items()))
            print(f"  After task {after_idx} ({stream.task_ids[after_idx]}): {row_str}")


def _prepare_stream(
    *,
    root: Path,
    registry,
    stream: StreamConfig,
    stream_path: Path,
    experiment_path: Path,
    experiment: ExperimentConfig,
    skip_references: bool,
) -> None:
    report = validate_configuration(registry, stream, experiment, root)
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if not report.valid:
        raise RuntimeError(f"Invalid configuration for {stream.stream_id}")

    for manifest in generate_data_for_tasks(registry, stream.task_ids, experiment, experiment.data.seed):
        print(manifest)

    if skip_references:
        return
    for task_id in stream.task_ids:
        task = registry.get(task_id)
        solver = _default_solver_config(task, root)
        for split in ("validation", "test"):
            records, failures = generate_task_references(task, split, solver)
            print(f"{task_id} {split}: cached/generated={len(records)} failures={len(failures)}")
            if failures:
                raise RuntimeError(f"Reference generation failed for {task_id} {split}")
    for task_id in stream.task_ids:
        task = registry.get(task_id)
        for split in ("validation", "test"):
            verification = verify_task_references(task, split)
            print(
                f"{task_id} {split}: optimal={verification.optimal} "
                f"best_known={verification.best_known} errors={len(verification.errors)}"
            )
            for error in verification.errors:
                print(f"ERROR: {error}", file=sys.stderr)
            if not verification.valid:
                raise RuntimeError(f"Reference verification failed for {task_id} {split}")


def _default_solver_config(task, root: Path):
    default_cfgs = {
        "tsp": "cmhh/configs/solvers/concorde.yaml",
        "cvrp": "cmhh/configs/solvers/pyvrp.yaml",
        "jssp": "cmhh/configs/solvers/ortools_cpsat.yaml",
    }
    cfg_rel = default_cfgs.get(task.problem.lower())
    cfg_path = _resolve(cfg_rel, root) if cfg_rel else None
    if not cfg_path or not cfg_path.exists():
        return None
    from cmhh.config import load_yaml

    raw_yaml = load_yaml(cfg_path)
    solver_dict = raw_yaml.get("solver", raw_yaml)
    if task.problem.lower() == "tsp":
        try:
            return load_concorde_config(cfg_path, root)
        except Exception:
            return solver_dict
    return solver_dict


def _run_suite(args: argparse.Namespace, root: Path) -> int:
    registry = load_task_registry(repo_root=root)
    mode = args.mode
    generator_name = args.generator or mode_default_generator(mode)
    evolution_timeout = _resolve_evolution_timeout(args, mode)
    seeds = parse_int_values(args.seeds)
    conditions = normalize_conditions(args.conditions)
    if args.skip_managed:
        conditions = tuple(item for item in conditions if item != "managed")

    stream_values = parse_string_values(args.streams)
    if not stream_values:
        stream_values = DEFAULT_STREAMS if (mode != "pilot" or args.all_streams) else PILOT_STREAMS

    if generator_name in {"heuragenix", "eoh"} and not _resolve(args.llm_config, root).exists():
        print(f"ERROR: Missing LLM config: {_resolve(args.llm_config, root)}", file=sys.stderr)
        return 1

    os.environ["CMHH_EOH_EVALUATION_TIMEOUT_SECONDS"] = str(args.eoh_evaluation_timeout)
    run_prefix = args.run_prefix or "cmhh_suite_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summary: list[str] = []

    print("CM-HH Python suite runner")
    print(f"Repo      : {root}")
    print(f"Mode      : {mode}")
    print(f"Generator : {generator_name}")
    print(f"Seeds     : {', '.join(str(seed) for seed in seeds)}")
    print(f"Streams   : {', '.join(stream_values)}")
    print(f"Conditions: {', '.join(conditions)}")
    print(f"RunPrefix : {run_prefix}")

    for stream_value in stream_values:
        stream_path = resolve_stream_path(stream_value, root)
        stream = load_stream_config(stream_path)
        print("")
        print(f"=== Stream {stream.stream_id} ===")

        condition_configs: dict[str, tuple[Path, ExperimentConfig]] = {}
        for condition, experiment_rel in CONDITION_EXPERIMENTS.items():
            if condition == "managed" and condition not in conditions:
                continue
            if condition == "isolated" and (condition not in conditions or args.skip_isolated):
                continue
            if condition not in conditions:
                continue
            experiment_path = _resolve(experiment_rel, root)
            experiment = load_experiment_config(experiment_path, root)
            experiment = _apply_tracking_overrides(experiment, args)
            experiment = _apply_run_overrides(experiment, args)
            condition_configs[condition] = (experiment_path, experiment)
            report = validate_configuration(registry, stream, experiment, root)
            print(f"Validated {condition}: valid={report.valid}")
            for warning in report.warnings:
                print(f"WARNING: {warning}")
            for error in report.errors:
                print(f"ERROR: {error}", file=sys.stderr)
            if not report.valid:
                return 1

        isolated_path = _resolve(CONDITION_EXPERIMENTS["isolated"], root)
        isolated_experiment = _apply_run_overrides(
            _apply_tracking_overrides(load_experiment_config(isolated_path, root), args),
            args,
        )
        _prepare_stream(
            root=root,
            registry=registry,
            stream=stream,
            stream_path=stream_path,
            experiment_path=isolated_path,
            experiment=isolated_experiment,
            skip_references=args.skip_references,
        )
        if args.prepare_only:
            continue

        single_stream = len(stream_values) == 1
        stream_part = "" if single_stream else f"{stream.stream_id}_"
        for seed in seeds:
            print("")
            print(f"--- Stream {stream.stream_id} / Seed {seed} ---")
            cold_run_id = f"{run_prefix}_{stream_part}{generator_name}_cold_seed{seed}"
            cold_start_scores = root / "cmhh" / "results" / cold_run_id / "cold_start_scores.json"

            if args.include_eoh:
                eoh_path = _resolve("cmhh/configs/experiments/eoh_cold_start.yaml", root)
                eoh_experiment = _apply_run_overrides(
                    _apply_tracking_overrides(load_experiment_config(eoh_path, root), args),
                    args,
                )
                eoh_run_id = f"{run_prefix}_{stream_part}eoh_cold_seed{seed}"
                matrix = _create_runner_run(
                    root=root,
                    registry=registry,
                    experiment_path=eoh_path,
                    stream_path=stream_path,
                    experiment=eoh_experiment,
                    stream=stream,
                    args=args,
                    run_id=eoh_run_id,
                    seed=seed,
                    generator_name="eoh",
                    evolution_timeout=evolution_timeout,
                    write_cold_start_scores=True,
                    command_name="run-suite",
                )
                _print_matrix_summary(eoh_run_id, stream, matrix, isolated=True)
                summary.append(eoh_run_id)

            if "isolated" in conditions and not args.skip_isolated:
                experiment_path, experiment = condition_configs.get(
                    "isolated",
                    (isolated_path, isolated_experiment),
                )
                matrix = _create_runner_run(
                    root=root,
                    registry=registry,
                    experiment_path=experiment_path,
                    stream_path=stream_path,
                    experiment=experiment,
                    stream=stream,
                    args=args,
                    run_id=cold_run_id,
                    seed=seed,
                    generator_name=generator_name,
                    evolution_timeout=evolution_timeout,
                    write_cold_start_scores=True,
                    command_name="run-suite",
                )
                _print_matrix_summary(cold_run_id, stream, matrix, isolated=True)
                summary.append(cold_run_id)

            for condition in ("population", "naive-bounded", "naive-unbounded", "managed"):
                if condition not in condition_configs:
                    continue
                experiment_path, experiment = condition_configs[condition]
                suffix = {
                    "population": "population_carryover",
                    "naive-bounded": "naive_bounded",
                    "naive-unbounded": "naive_unbounded",
                    "managed": "archivist_managed",
                }[condition]
                run_id = f"{run_prefix}_{stream_part}{suffix}_seed{seed}"
                matrix = _create_runner_run(
                    root=root,
                    registry=registry,
                    experiment_path=experiment_path,
                    stream_path=stream_path,
                    experiment=experiment,
                    stream=stream,
                    args=args,
                    run_id=run_id,
                    seed=seed,
                    generator_name=generator_name,
                    evolution_timeout=evolution_timeout,
                    cold_start_scores_path=cold_start_scores,
                    command_name="run-suite",
                )
                _print_matrix_summary(run_id, stream, matrix)
                audit = audit_run(experiment.output_root / run_id)
                for error in audit.errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                for warning in audit.warnings:
                    print(f"WARNING: {warning}")
                print(f"Audit {run_id}: valid={audit.valid} ({len(audit.errors)} errors, {len(audit.warnings)} warnings)")
                if not audit.valid:
                    return 1
                summary.append(run_id)

    if args.prepare_only:
        print("")
        print("PrepareOnly complete. Data and references are ready.")
        return 0

    print("")
    print("Completed runs:")
    for run_id in summary:
        print(f"  cmhh/results/{run_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.repo_root).resolve()
    if not (root / "cmhh" / "configs").exists() and (root / "HeurAgenix" / "cmhh" / "configs").exists():
        root = (root / "HeurAgenix").resolve()

    if args.command == "run-suite":
        return _run_suite(args, root)

    experiment_path = _resolve(args.experiment, root)
    stream_path = resolve_stream_path(args.stream, root)
    experiment = load_experiment_config(experiment_path, root)
    stream = load_stream_config(stream_path)
    registry = load_task_registry(repo_root=root)

    if args.command == "validate-config":
        report = validate_configuration(registry, stream, experiment, root)
        for warning in report.warnings:
            print(f"WARNING: {warning}")
        for error in report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Validated {len(registry)} tasks; stream has {len(stream.task_ids)} tasks")
        return 0 if report.valid else 1

    if args.command == "generate-data":
        seed = args.seed if args.seed is not None else experiment.data.seed
        for manifest in generate_data_for_tasks(registry, stream.task_ids, experiment, seed):
            print(manifest)
        return 0

    if args.command == "evaluate-baselines":
        evaluator = Evaluator(root, experiment.evaluation)
        task_ids = tuple(args.task) if args.task else stream.task_ids
        output = experiment.output_root / "phase0_baselines"
        for task_id in task_ids:
            task = registry.get(task_id)
            for artifact in baseline_artifacts(task, root):
                result = evaluator.evaluate(artifact, task, args.split)
                write_evaluation(output / task_id / f"{artifact.heuristic_id}.{args.split}.json", result)
                print_evaluation_summary(result)
        return 0

    if args.command == "generate-references":
        solver_cfg_path = _resolve(args.solver_config, root) if args.solver_config else None
        explicit_solver_config = None
        if solver_cfg_path and solver_cfg_path.exists():
            from cmhh.config import load_yaml
            raw_yaml = load_yaml(solver_cfg_path)
            solver_dict = raw_yaml.get("solver", raw_yaml)
            s_name = str(solver_dict.get("name", "")).lower()
            if s_name == "concorde" or solver_dict.get("command_prefix"):
                try:
                    explicit_solver_config = load_concorde_config(solver_cfg_path, root)
                except Exception:
                    explicit_solver_config = solver_dict
            else:
                explicit_solver_config = solver_dict

        task_ids = tuple(args.task) if args.task else stream.task_ids
        splits = tuple(args.split) if args.split else ("test",)
        total_failures = 0
        for task_id in task_ids:
            task = registry.get(task_id)
            # Determine solver config for task
            if explicit_solver_config is not None:
                solver = explicit_solver_config
            else:
                # Default problem-specific solver config
                default_cfgs = {
                    "tsp": "cmhh/configs/solvers/concorde.yaml",
                    "cvrp": "cmhh/configs/solvers/pyvrp.yaml",
                    "jssp": "cmhh/configs/solvers/ortools_cpsat.yaml",
                }
                cfg_rel = default_cfgs.get(task.problem.lower())
                cfg_path = _resolve(cfg_rel, root) if cfg_rel else None
                if cfg_path and cfg_path.exists():
                    from cmhh.config import load_yaml
                    raw_yaml = load_yaml(cfg_path)
                    solver_dict = raw_yaml.get("solver", raw_yaml)
                    if task.problem.lower() == "tsp":
                        try:
                            solver = load_concorde_config(cfg_path, root)
                        except Exception:
                            solver = solver_dict
                    else:
                        solver = solver_dict
                else:
                    solver = None

            for split in splits:
                records, failures = generate_task_references(
                    task, split, solver, pilot_count=args.pilot_count
                )
                total_failures += len(failures)
                print(
                    f"{task_id} {split}: cached/generated={len(records)} failures={len(failures)}"
                )
        return 1 if total_failures else 0

    if args.command == "verify-references":
        task_ids = tuple(args.task) if args.task else stream.task_ids
        splits = tuple(args.split) if args.split else ("test",)
        valid = True
        for task_id in task_ids:
            task = registry.get(task_id)
            for split in splits:
                report = verify_task_references(task, split)
                valid = valid and report.valid
                print(
                    f"{task_id} {split}: optimal={report.optimal} "
                    f"best_known={report.best_known} errors={len(report.errors)}"
                )
                for error in report.errors:
                    print(f"ERROR: {error}", file=sys.stderr)
        return 0 if valid else 1

    if args.command == "run-stream":
        experiment = _apply_tracking_overrides(experiment, args)
        try:
            seeds = _select_seeds(args, experiment)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        experiment = _apply_run_overrides(experiment, args)
        evolution_timeout = _resolve_evolution_timeout(args, args.mode)
        for seed in seeds:
            run_id = _run_id_for_seed(
                requested=args.run_id,
                prefix="phase0",
                seed=seed,
                multiple_seeds=len(seeds) > 1,
            )
            try:
                matrix = _create_runner_run(
                    root=root,
                    registry=registry,
                    experiment_path=experiment_path,
                    stream_path=stream_path,
                    experiment=experiment,
                    stream=stream,
                    args=args,
                    run_id=run_id,
                    seed=seed,
                    generator_name=args.generator,
                    evolution_timeout=evolution_timeout,
                    cold_start_scores_path=_resolve(args.cold_start_scores, root) if args.cold_start_scores else None,
                    command_name="run-stream",
                )
            except (RuntimeError, ValueError) as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
            _print_matrix_summary(run_id, stream, matrix)
        return 0

    if args.command == "run-isolated":
        experiment = _apply_tracking_overrides(experiment, args)
        try:
            seeds = _select_seeds(args, experiment)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        experiment = _apply_run_overrides(experiment, args)
        evolution_timeout = _resolve_evolution_timeout(args, args.mode)
        for seed in seeds:
            run_id = _run_id_for_seed(
                requested=args.run_id,
                prefix="isolated",
                seed=seed,
                multiple_seeds=len(seeds) > 1,
            )
            try:
                matrix = _create_runner_run(
                    root=root,
                    registry=registry,
                    experiment_path=experiment_path,
                    stream_path=stream_path,
                    experiment=experiment,
                    stream=stream,
                    args=args,
                    run_id=run_id,
                    seed=seed,
                    generator_name=args.generator,
                    evolution_timeout=evolution_timeout,
                    write_cold_start_scores=True,
                    command_name="run-isolated",
                )
            except (RuntimeError, ValueError) as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
            _print_matrix_summary(run_id, stream, matrix, isolated=True)
        return 0

    if args.command == "evolve-task":
        task = registry.get(args.task)
        evaluator = Evaluator(root, experiment.evaluation)
        run_id = args.run_id or datetime.now(timezone.utc).strftime("evolve_%Y%m%dT%H%M%SZ")
        generator = HeurAgenixGenerator(
            repo_root=root,
            llm_config_path=_resolve(args.llm_config, root),
            output_root=experiment.output_root / run_id / "generator",
            timeout_seconds=args.evolution_timeout,
        )
        seed_population = [
            artifact
            for artifact in baseline_artifacts(task, root)
        ]
        results = generator.generate(
            task=task,
            seed_population=seed_population,
            budget=experiment.search,
            seed=args.seed,
        )
        print(f"Generated {len(results)} candidates for {task.task_id}:")
        for candidate in results:
            eval_res = evaluator.evaluate(candidate, task, "validation")
            print(f"  {candidate.heuristic_id}: gap={eval_res.mean_relative_gap:.4f} failure_rate={eval_res.failure_rate:.2f}")
        return 0

    if args.command == "audit-run":
        run_dir = experiment.output_root / args.run_id
        report = audit_run(run_dir)
        for error in report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        for warning in report.warnings:
            print(f"WARNING: {warning}")
        print(f"Audit {run_dir.name}: valid={report.valid} ({len(report.errors)} errors, {len(report.warnings)} warnings)")
        return 0 if report.valid else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
