from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from cmhh.baselines import baseline_artifacts
from cmhh.agents.generator import BaselineGenerator
from cmhh.agents.heuragenix_generator import HeurAgenixGenerator
from cmhh.audit import audit_run
from cmhh.config import load_experiment_config, load_stream_config
from cmhh.data.tsp_generator import generate_tsp_datasets
from cmhh.data.manifest import load_json, sha256_file, write_json_atomic
from cmhh.evaluation.evaluator import Evaluator
from cmhh.reporting import print_evaluation_summary, write_evaluation
from cmhh.reproducibility import create_run_manifest
from cmhh.references.concorde import load_concorde_config, validate_solver_command
from cmhh.references.pipeline import generate_task_references
from cmhh.references.verification import verify_task_references
from cmhh.runner import StreamRunner
from cmhh.tasks import load_task_registry
from cmhh.validation import validate_configuration


DEFAULT_EXPERIMENT = "cmhh/configs/experiments/phase0_tsp.yaml"
DEFAULT_STREAM = "cmhh/configs/streams/tsp_size_ascending.yaml"


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
    run_stream.add_argument("--generator", choices=("baseline", "heuragenix"), default="baseline")
    run_stream.add_argument("--llm-config")
    run_stream.add_argument("--evolution-timeout", type=float, default=3600)
    run_stream.add_argument("--cold-start-scores")

    isolated = subparsers.add_parser("run-isolated")
    _add_config_arguments(isolated)
    isolated.add_argument("--seed", type=int)
    isolated.add_argument("--run-id")
    isolated.add_argument("--generator", choices=("baseline", "heuragenix"), default="baseline")
    isolated.add_argument("--llm-config")
    isolated.add_argument("--evolution-timeout", type=float, default=3600)

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
    return value if value.is_absolute() else root / value


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
        for manifest in generate_tsp_datasets(registry, stream.task_ids, experiment, seed):
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
        seed = args.seed if args.seed is not None else experiment.seeds[0]
        run_id = args.run_id or datetime.now(timezone.utc).strftime("phase0_%Y%m%dT%H%M%SZ")
        run_dir = experiment.output_root / run_id
        checkpoint_path = run_dir / "checkpoints/latest.json"
        if checkpoint_path.exists() and not args.resume:
            print(f"ERROR: run already has a checkpoint; pass --resume: {run_id}", file=sys.stderr)
            return 2
        if args.resume and not checkpoint_path.exists():
            print(f"ERROR: no checkpoint exists for resume: {run_id}", file=sys.stderr)
            return 2
        experiment_path = _resolve(args.experiment, root)
        stream_path = _resolve(args.stream, root)
        manifest_path = run_dir / "manifest.json"
        if args.resume:
            manifest = load_json(manifest_path)
            manifest.setdefault("resume_events", []).append(datetime.now(timezone.utc).isoformat())
            write_json_atomic(manifest_path, manifest)
        else:
            data_manifests = [registry.get(task_id).splits.train.parent / "manifest.json" for task_id in stream.task_ids]
            create_run_manifest(
                manifest_path,
                root,
                run_id,
                seed,
                [experiment_path, stream_path, root / "cmhh/configs/tasks/task_registry.yaml"],
                {
                    "condition": experiment.condition,
                    "generator": args.generator,
                    "stream_id": stream.stream_id,
                    "data_manifests": {str(path): sha256_file(path) for path in data_manifests},
                },
            )
        if args.generator == "heuragenix":
            if not args.llm_config:
                print("ERROR: --llm-config is required for HeurAgenix generation", file=sys.stderr)
                return 2
            generator = HeurAgenixGenerator(
                root, _resolve(args.llm_config, root), run_dir / "candidates",
                timeout_seconds=args.evolution_timeout,
            )
        else:
            generator = BaselineGenerator(str(root))
        runner = StreamRunner(
            registry=registry,
            stream=stream,
            experiment=experiment,
            evaluator=Evaluator(root, experiment.evaluation),
            generator=generator,
            run_dir=run_dir,
            seed=seed,
            cold_start_scores=(
                {
                    index: float(load_json(_resolve(args.cold_start_scores, root))[task_id])
                    for index, task_id in enumerate(stream.task_ids)
                }
                if args.cold_start_scores else None
            ),
        )
        runner.run()
        print(run_dir)
        return 0

    if args.command == "run-isolated":
        seed = args.seed if args.seed is not None else experiment.seeds[0]
        run_id = args.run_id or datetime.now(timezone.utc).strftime("isolated_%Y%m%dT%H%M%SZ")
        run_dir = experiment.output_root / run_id
        experiment_path = _resolve(args.experiment, root)
        stream_path = _resolve(args.stream, root)
        data_manifests = [registry.get(task_id).splits.train.parent / "manifest.json" for task_id in stream.task_ids]
        create_run_manifest(
            run_dir / "manifest.json",
            root,
            run_id,
            seed,
            [experiment_path, stream_path, root / "cmhh/configs/tasks/task_registry.yaml"],
            {
                "condition": experiment.condition,
                "generator": args.generator,
                "stream_id": stream.stream_id,
                "data_manifests": {str(path): sha256_file(path) for path in data_manifests},
            },
        )
        evaluator = Evaluator(root, experiment.evaluation)
        scores = {}
        selected = {}
        for index, task_id in enumerate(stream.task_ids):
            task = registry.get(task_id)
            if args.generator == "heuragenix":
                if not args.llm_config:
                    print("ERROR: --llm-config is required for HeurAgenix generation", file=sys.stderr)
                    return 2
                generator = HeurAgenixGenerator(
                    root,
                    _resolve(args.llm_config, root),
                    run_dir / "candidates" / task_id,
                    timeout_seconds=args.evolution_timeout,
                )
            else:
                generator = BaselineGenerator(str(root))
            candidates = generator.generate(
                task, baseline_artifacts(task, root), experiment.search, seed + index
            )
            ranked = []
            for candidate in candidates:
                smoke = evaluator.evaluate(candidate, task, "smoke")
                if smoke.failure_rate:
                    continue
                validation = evaluator.evaluate(candidate, task, "validation")
                write_evaluation(
                    run_dir / "evaluations" / task_id / "validation" / f"{candidate.heuristic_id}.json",
                    validation,
                )
                objectives = [item.objective for item in validation.successful if item.objective is not None]
                if validation.failure_rate == 0 and objectives:
                    runtime = sum(item.runtime_seconds for item in validation.successful) / len(validation.successful)
                    ranked.append((sum(objectives) / len(objectives), runtime, candidate.heuristic_id, candidate))
            if not ranked:
                print(f"ERROR: no valid isolated candidate for {task_id}", file=sys.stderr)
                return 1
            best = min(ranked, key=lambda item: item[:3])[3]
            result = evaluator.evaluate(best, task, "test")
            write_evaluation(run_dir / "evaluations" / task_id / "test.json", result)
            if result.mean_score is None:
                print(f"ERROR: references are missing for {task_id}", file=sys.stderr)
                return 1
            scores[task_id] = result.mean_score
            selected[task_id] = best.to_dict()
        write_json_atomic(run_dir / "cold_start_scores.json", scores)
        write_json_atomic(run_dir / "selected.json", selected)
        print(run_dir)
        return 0

    if args.command == "evolve-task":
        task = registry.get(args.task)
        run_id = args.run_id or datetime.now(timezone.utc).strftime("evolve_%Y%m%dT%H%M%SZ")
        run_dir = experiment.output_root / run_id
        budget = experiment.search
        if args.max_llm_calls is not None:
            from cmhh.models import SearchBudget
            budget = SearchBudget(
                generations=budget.generations,
                candidates_per_generation=budget.candidates_per_generation,
                max_llm_calls=args.max_llm_calls,
            )
        generator = HeurAgenixGenerator(
            root, _resolve(args.llm_config, root), run_dir / "candidates" / task.task_id,
            timeout_seconds=args.evolution_timeout,
        )
        candidates = generator.generate(
            task, baseline_artifacts(task, root), budget, args.seed
        )
        evaluator = Evaluator(root, experiment.evaluation)
        ranked = []
        for candidate in candidates:
            smoke = evaluator.evaluate(candidate, task, "smoke")
            write_evaluation(run_dir / "evaluations/smoke" / f"{candidate.heuristic_id}.json", smoke)
            if smoke.failure_rate:
                continue
            validation = evaluator.evaluate(candidate, task, "validation")
            write_evaluation(
                run_dir / "evaluations/validation" / f"{candidate.heuristic_id}.json", validation
            )
            objectives = [item.objective for item in validation.successful if item.objective is not None]
            if validation.failure_rate == 0 and objectives:
                runtime = sum(item.runtime_seconds for item in validation.successful) / len(validation.successful)
                ranked.append((sum(objectives) / len(objectives), runtime, candidate.heuristic_id, candidate))
        if not ranked:
            print("ERROR: evolution produced no valid candidate", file=sys.stderr)
            return 1
        selected = min(ranked, key=lambda item: item[:3])[3]
        write_json_atomic(run_dir / "selected.json", selected.to_dict())
        print(run_dir)
        return 0

    if args.command == "audit-run":
        report = audit_run(experiment.output_root / args.run_id)
        for warning in report.warnings:
            print(f"WARNING: {warning}")
        for error in report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Audit {'passed' if report.valid else 'failed'}: {args.run_id}")
        return 0 if report.valid else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
