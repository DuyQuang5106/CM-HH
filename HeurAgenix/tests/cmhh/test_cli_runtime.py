from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from cmhh.cli import build_parser
from cmhh.config import load_experiment_config, load_stream_config
from cmhh.runtime import (
    apply_runtime_overrides,
    normalize_conditions,
    parse_int_values,
    resolve_stream_path,
    write_resolved_config,
)


class CLIRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_run_stream_accepts_mode_seed_seeds_and_resume(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "run-stream",
            "--stream",
            "tsp_size_ascending",
            "--mode",
            "pilot",
            "--seeds",
            "1",
            "2",
            "3",
            "--resume",
        ])

        self.assertEqual("run-stream", args.command)
        self.assertEqual("pilot", args.mode)
        self.assertEqual(["1", "2", "3"], args.seeds)
        self.assertTrue(args.resume)

    def test_invalid_mode_is_rejected_by_argparse(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["run-stream", "--mode", "tiny"])

    def test_seed_parser_accepts_space_and_comma_forms(self) -> None:
        self.assertEqual((1, 2, 3, 4), parse_int_values(["1", "2,3", 4]))

    def test_condition_aliases_normalize_to_canonical_names(self) -> None:
        self.assertEqual(
            ("isolated", "naive-bounded", "managed"),
            normalize_conditions(["Isolated", "NaiveBounded", "archivist_managed"]),
        )

    def test_mode_budget_overrides_yaml_values(self) -> None:
        experiment = load_experiment_config(
            self.repo_root / "cmhh/configs/experiments/h1_isolated.yaml",
            self.repo_root,
        )
        resolved = apply_runtime_overrides(experiment, mode="pilot")

        self.assertEqual(2, resolved.search.generations)
        self.assertEqual(1, resolved.search.candidates_per_generation)
        self.assertEqual(5, resolved.search.max_llm_calls)

    def test_explicit_budget_override_wins_after_mode(self) -> None:
        experiment = load_experiment_config(
            self.repo_root / "cmhh/configs/experiments/h1_isolated.yaml",
            self.repo_root,
        )
        resolved = apply_runtime_overrides(
            experiment,
            mode="pilot",
            generations=7,
            max_llm_calls=11,
        )

        self.assertEqual(7, resolved.search.generations)
        self.assertEqual(1, resolved.search.candidates_per_generation)
        self.assertEqual(11, resolved.search.max_llm_calls)

    def test_stream_name_resolution_is_platform_neutral(self) -> None:
        path = resolve_stream_path("tsp_size_ascending", self.repo_root)

        self.assertTrue(path.exists())
        self.assertEqual("tsp_size_ascending.yaml", path.name)

    def test_write_resolved_config_uses_effective_values(self) -> None:
        experiment_path = self.repo_root / "cmhh/configs/experiments/h1_isolated.yaml"
        stream_path = self.repo_root / "cmhh/configs/streams/tsp_size_ascending.yaml"
        experiment = apply_runtime_overrides(
            load_experiment_config(experiment_path, self.repo_root),
            mode="pilot",
            max_llm_calls=13,
        )
        stream = load_stream_config(stream_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "resolved_config.yaml"
            write_resolved_config(
                target,
                repo_root=self.repo_root,
                experiment_path=experiment_path,
                stream_path=stream_path,
                experiment=experiment,
                stream=stream,
                run_id="test_run",
                seed=3,
                mode="pilot",
                generator="baseline",
                llm_config=None,
                evolution_timeout_seconds=12.0,
                resume=True,
            )

            raw = yaml.safe_load(target.read_text(encoding="utf-8"))

        self.assertEqual(3, raw["seed"])
        self.assertEqual("pilot", raw["mode"])
        self.assertTrue(raw["resume"])
        self.assertEqual(13, raw["experiment"]["search"]["max_llm_calls"])


if __name__ == "__main__":
    unittest.main()
