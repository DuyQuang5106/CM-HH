from __future__ import annotations

import argparse
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
    run_stream.add_argument("--run-id")
    run_stream.add_argument("--resume", action="store_true")
    run_stream.add_argument("--generator", choices=("baseline", "heuragenix", "eoh"), default="baseline")
    run_stream.add_argument("--llm-config")
    run_stream.add_argument("--evolution-timeout", type=float, default=3600)
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
    isolated.add_argument("--run-id")
    isolated.add_argument("--generator", choices=("baseline", "heuragenix", "eoh"), default="baseline")
    isolated.add_argument("--llm-config")
    isolated.add_argument("--evolution-timeout", type=float, default=3600)
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
    references.add_argument("--solver-config", default="cmhh/configs/solvers/concorde.yaml")
    references.add_argument("--split", action="append", choices=("validation", "test"), default=None)
    references.add_argument("--task", action="append")
    references.add_argument("--pilot-count", type=int)

    verify = subparsers.add_parser("verify-references")
    _add_config_arguments(verify)
    verify.add_argument("--split", action="append", choices=("validation", "test"), default=None)
    verify.add_argument("--task", action="append")
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
    return root / value


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.repo_root).resolve()
    experiment = load_experiment_config(_resolve(args.experiment, root), root)
    stream = load_stream_config(_resolve(args.stream, root))
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
        solver = load_concorde_config(_resolve(args.solver_config, root), root)
        try:
            validate_solver_command(solver)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        task_ids = tuple(args.task) if args.task else stream.task_ids
        splits = tuple(args.split) if args.split else ("test",)
        total_failures = 0
        for task_id in task_ids:
            task = registry.get(task_id)
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
        seed = args.seed if args.seed is not None else experiment.seeds[0]
        run_id = args.run_id or datetime.now(timezone.utc).strftime("phase0_%Y%m%dT%H%M%SZ")
        run_dir = experiment.output_root / run_id
        checkpoint_path = run_dir / "checkpoints/latest.json"

        if not args.resume and checkpoint_path.exists():
            print(f"ERROR: Run directory {run_dir} exists; pass --resume to continue", file=sys.stderr)
            return 1

        evaluator = Evaluator(root, experiment.evaluation)
        if args.generator in {"heuragenix", "eoh"}:
            if not args.llm_config:
                print(f"ERROR: --llm-config is required for --generator {args.generator}", file=sys.stderr)
                return 1
            generator_cls = HeurAgenixGenerator if args.generator == "heuragenix" else EOHGenerator
            generator = generator_cls(
                repo_root=root,
                llm_config_path=_resolve(args.llm_config, root),
                output_root=run_dir / "generator",
                timeout_seconds=args.evolution_timeout,
            )
        else:
            generator = BaselineGenerator(root)

        cold_start_scores = (
            load_json(_resolve(args.cold_start_scores, root)) if args.cold_start_scores else None
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

        manifest = create_run_manifest(
            path=run_dir / "manifest.json",
            repo_root=root,
            run_id=run_id,
            seed=seed,
            config_paths=[_resolve(args.experiment, root), _resolve(args.stream, root)],
            extra={"task_ids": list(stream.task_ids)},
        )
        matrix = runner.run()

        print(f"Completed run {run_id}:")
        for after_idx, row in sorted(matrix.items()):
            row_str = ", ".join(f"T{j}={score:.4f}" for j, score in sorted(row.items()))
            print(f"  After task {after_idx} ({stream.task_ids[after_idx]}): {row_str}")
        return 0

    if args.command == "run-isolated":
        experiment = _apply_tracking_overrides(experiment, args)
        seed = args.seed if args.seed is not None else experiment.seeds[0]
        run_id = args.run_id or datetime.now(timezone.utc).strftime("isolated_%Y%m%dT%H%M%SZ")
        run_dir = experiment.output_root / run_id
        evaluator = Evaluator(root, experiment.evaluation)
        if args.generator in {"heuragenix", "eoh"}:
            if not args.llm_config:
                print(f"ERROR: --llm-config is required for --generator {args.generator}", file=sys.stderr)
                return 1
            generator_cls = HeurAgenixGenerator if args.generator == "heuragenix" else EOHGenerator
            generator = generator_cls(
                repo_root=root,
                llm_config_path=_resolve(args.llm_config, root),
                output_root=run_dir / "generator",
                timeout_seconds=args.evolution_timeout,
            )
        else:
            generator = BaselineGenerator(root)

        runner = StreamRunner(
            registry=registry,
            stream=stream,
            experiment=experiment,
            evaluator=evaluator,
            generator=generator,
            run_dir=run_dir,
            seed=seed,
        )
        matrix = runner.run()
        print(f"Completed isolated run {run_id}:")
        for after_idx, row in sorted(matrix.items()):
            print(f"  Task {after_idx} ({stream.task_ids[after_idx]}): T{after_idx}={row.get(after_idx, 0.0):.4f}")
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
