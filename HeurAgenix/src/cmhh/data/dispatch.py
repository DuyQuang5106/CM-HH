from __future__ import annotations

from pathlib import Path

from cmhh.config import ExperimentConfig
from cmhh.data.cvrp_generator import generate_cvrp_splits
from cmhh.data.dposp_generator import generate_dposp_splits
from cmhh.data.jssp_generator import generate_jssp_splits
from cmhh.data.manifest import sha256_file, write_json_atomic
from cmhh.data.max_cut_generator import generate_max_cut_splits
from cmhh.data.mkp_generator import generate_mkp_splits
from cmhh.data.obp_generator import generate_obp_splits
from cmhh.data.pfsp_generator import generate_pfsp_splits
from cmhh.data.tsp_generator import generate_tsp_datasets, _generate_task_splits as generate_tsp_splits
from cmhh.tasks import TaskRegistry, TaskSpec


def generate_data_for_tasks(
    registry: TaskRegistry,
    task_ids: tuple[str, ...],
    experiment: ExperimentConfig,
    seed: int,
) -> list[Path]:
    manifests: list[Path] = []
    for task_id in task_ids:
        task = registry.get(task_id)
        if task.problem == "tsp":
            generate_tsp_splits(task, experiment, seed)
        elif task.problem == "cvrp":
            generate_cvrp_splits(task, experiment, seed)
        elif task.problem == "jssp":
            generate_jssp_splits(task, experiment, seed)
        elif task.problem == "pfsp":
            generate_pfsp_splits(task, experiment, seed)
        elif task.problem == "dposp":
            generate_dposp_splits(task, experiment, seed)
        elif task.problem == "mkp":
            generate_mkp_splits(task, experiment, seed)
        elif task.problem == "max_cut":
            generate_max_cut_splits(task, experiment, seed)
        elif task.problem == "obp":
            generate_obp_splits(task, experiment, seed)
        else:
            raise NotImplementedError(f"Data generator for problem '{task.problem}' is not implemented.")

        manifest_path = write_task_manifest(task, experiment, seed)
        manifests.append(manifest_path)

    return manifests


def write_task_manifest(task: TaskSpec, experiment: ExperimentConfig, seed: int) -> Path:
    base = task.splits.train.parent
    records = {}
    for split_name, directory in {
        "train": task.splits.train,
        "validation": task.splits.validation,
        "test": task.splits.test,
        "smoke": task.splits.smoke,
    }.items():
        if directory is None or not directory.exists():
            continue

        split_files = {}
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                rel_name = str(path.relative_to(directory))
                split_files[rel_name] = sha256_file(path)
        records[split_name] = split_files

    manifest_path = base / "manifest.json"
    write_json_atomic(manifest_path, {
        "task_id": task.task_id,
        "problem": task.problem,
        "size_tier": task.size_tier,
        "distribution": task.distribution,
        "data_seed": seed,
        "coordinate_min": experiment.data.coordinate_min,
        "coordinate_max": experiment.data.coordinate_max,
        "splits": records,
    })
    return manifest_path
