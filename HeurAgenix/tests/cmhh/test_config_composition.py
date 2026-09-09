from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cmhh.config import (
    ArchiveConfig,
    ConditionSpec,
    ExperimentConfig,
    SuiteConfig,
    compose_experiment_config,
    load_base_experiment_config,
    load_conditions_registry,
    load_experiment_config,
    load_suite_config,
)
from cmhh.models import EvaluationBudget, SearchBudget
from cmhh.runtime import resolve_condition_experiment_config


class ConfigCompositionTestSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path.cwd()
        if not (self.repo_root / "cmhh" / "configs").exists() and (self.repo_root / "HeurAgenix" / "cmhh" / "configs").exists():
            self.repo_root = self.repo_root / "HeurAgenix"

    def test_load_base_experiment_config(self) -> None:
        """defaults.yaml must load as a valid ExperimentConfig with complete search/eval budgets."""
        base = load_base_experiment_config(self.repo_root)
        self.assertIsInstance(base, ExperimentConfig)
        self.assertEqual(base.search.max_llm_calls, 200)
        self.assertEqual(base.search.generations, 10)
        self.assertEqual(base.search.candidates_per_generation, 10)
        self.assertEqual(base.evaluation.instance_timeout_seconds, 30.0)
        self.assertEqual(base.evaluation.batch_timeout_seconds, 900.0)
        self.assertEqual(base.data.splits["train"], 20)
        self.assertEqual(base.data.splits["validation"], 10)
        self.assertEqual(base.data.splits["test"], 30)

    def test_load_conditions_registry(self) -> None:
        """conditions.yaml must define all 5 core continual conditions cleanly without parameter duplication."""
        registry = load_conditions_registry(self.repo_root)
        expected_conditions = {"isolated", "population", "naive-bounded", "naive-unbounded", "managed"}
        self.assertTrue(expected_conditions.issubset(set(registry.keys())))

        # Isolated: no memory
        iso = registry["isolated"]
        self.assertEqual(iso.condition, "isolated_task")
        self.assertEqual(iso.archive.policy, "none")
        self.assertEqual(iso.archive.capacity, 0)

        # Naive Bounded: capacity 20, overwrite
        nb = registry["naive-bounded"]
        self.assertEqual(nb.condition, "naive_memory_sequential")
        self.assertEqual(nb.archive.policy, "naive_overwrite")
        self.assertEqual(nb.archive.capacity, 20)
        self.assertEqual(nb.archive.memory_seed_quota, 1)

        # Naive Unbounded: capacity null
        nu = registry["naive-unbounded"]
        self.assertEqual(nu.condition, "naive_memory_unbounded")
        self.assertIsNone(nu.archive.capacity)

        # Managed: archivist managed policy
        managed = registry["managed"]
        self.assertEqual(managed.condition, "archivist_managed")
        self.assertEqual(managed.archive.policy, "archivist_managed")
        self.assertEqual(managed.archive.capacity, 20)

    def test_compose_experiment_config_with_condition(self) -> None:
        """Composing base experiment with a condition spec must apply archive policy while preserving base settings."""
        base = load_base_experiment_config(self.repo_root)
        registry = load_conditions_registry(self.repo_root)

        composed_managed = compose_experiment_config(base=base, condition_spec=registry["managed"])
        self.assertEqual(composed_managed.condition, "archivist_managed")
        self.assertEqual(composed_managed.archive.policy, "archivist_managed")
        self.assertEqual(composed_managed.search.max_llm_calls, base.search.max_llm_calls)
        self.assertEqual(composed_managed.evaluation.instance_timeout_seconds, 30.0)

        composed_iso = compose_experiment_config(base=base, condition_spec=registry["isolated"])
        self.assertEqual(composed_iso.condition, "isolated_task")
        self.assertEqual(composed_iso.archive.policy, "none")

    def test_compose_experiment_config_with_suite_overrides(self) -> None:
        """Composing with a suite must cleanly override budget and splits without touching condition policies."""
        base = load_base_experiment_config(self.repo_root)
        registry = load_conditions_registry(self.repo_root)

        suite = SuiteConfig(
            suite_id="pilot_custom",
            streams=("tsp_size_up_small",),
            conditions=("managed",),
            seeds=(42,),
            llm_budget_per_task=25,
            splits={"train": 5, "validation": 5, "test": 15},
        )

        composed = compose_experiment_config(
            base=base,
            condition_spec=registry["managed"],
            suite=suite,
        )

        self.assertEqual(composed.condition, "archivist_managed")
        self.assertEqual(composed.archive.policy, "archivist_managed")
        self.assertEqual(composed.search.max_llm_calls, 25)
        self.assertEqual(composed.seeds, (42,))
        self.assertEqual(composed.data.splits["train"], 5)
        self.assertEqual(composed.data.splits["validation"], 5)
        self.assertEqual(composed.data.splits["test"], 15)
        self.assertEqual(composed.data.splits["smoke"], 2)  # preserved from base

    def test_resolve_condition_experiment_config_dynamic(self) -> None:
        """resolve_condition_experiment_config must dynamically construct condition configs."""
        base = load_base_experiment_config(self.repo_root)
        for cond_name in ("isolated", "population", "naive-bounded", "naive-unbounded", "managed"):
            path, exp_cfg = resolve_condition_experiment_config(cond_name, base, self.repo_root)
            self.assertIsInstance(exp_cfg, ExperimentConfig)
            self.assertIsNotNone(exp_cfg.condition)
            self.assertIsNotNone(exp_cfg.archive)

    def test_benchmark_full_suite_yaml(self) -> None:
        """benchmark_full.yaml must parse cleanly and contain all active benchmark streams."""
        suite_path = self.repo_root / "cmhh" / "configs" / "suites" / "benchmark_full.yaml"
        self.assertTrue(suite_path.exists())
        suite = load_suite_config(suite_path)
        self.assertEqual(suite.suite_id, "benchmark_full")
        self.assertEqual(suite.mode, "full")
        self.assertEqual(suite.seeds, (1, 2, 3, 4, 5))
        self.assertIn("isolated", suite.conditions)
        self.assertIn("managed", suite.conditions)
        self.assertEqual(len(suite.streams), 10)


if __name__ == "__main__":
    unittest.main()
