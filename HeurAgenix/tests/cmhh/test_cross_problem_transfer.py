from __future__ import annotations

import unittest
from pathlib import Path

from cmhh.contract_validator import TargetContractValidator
from cmhh.memory import (
    MemoryEvidence,
    MemoryKey,
    MemoryMetadata,
    MemoryPolicyState,
    MemoryScope,
    MemoryUnit,
    MemoryValue,
)
from cmhh.transferable_knowledge import (
    CrossProblemAdapter,
    TransferableKnowledge,
    normalize_archive_item_to_transferable,
    normalize_memory_unit_to_transferable,
    normalize_population_item_to_transferable,
)


class TestCrossProblemTransfer(unittest.TestCase):
    def test_transferable_knowledge_serialization(self) -> None:
        """TransferableKnowledge can serialize and deserialize cleanly without loss."""
        tk = TransferableKnowledge(
            source_problem="tsp",
            source_task_id="tsp_uniform_n50_a",
            algorithmic_principles=["Greedy 2-opt edge swap", "Nearest-neighbor tour initialization"],
            design_description="Constructive tour builder with iterative local search",
            source_performance={"relative_gap": 0.045, "score": 105.2},
            source_heuristic_id="heur_tsp_001",
            provenance="managed_ku",
        )

        d = tk.to_dict()
        self.assertEqual(d["source_problem"], "tsp")
        self.assertEqual(len(d["algorithmic_principles"]), 2)
        self.assertEqual(d["provenance"], "managed_ku")

        tk_recovered = TransferableKnowledge.from_dict(d)
        self.assertEqual(tk_recovered.source_problem, tk.source_problem)
        self.assertEqual(list(tk_recovered.algorithmic_principles), list(tk.algorithmic_principles))
        self.assertEqual(tk_recovered.source_performance, tk.source_performance)

    def test_normalizers_from_all_three_memory_sources(self) -> None:
        """MemoryUnit, Population item, and Naive Archive item all normalize to canonical TransferableKnowledge."""
        # 1. Managed MemoryUnit
        unit = MemoryUnit(
            id="ku_001",
            created_at="2026-09-08T00:00:00Z",
            scope=MemoryScope(problem="tsp", task_id="tsp_uniform_n50_a"),
            key=MemoryKey(applicability="tsp routing", task_signature={"nodes": 50}),
            value=MemoryValue(
                type="heuristic_insight",
                content="Prioritize shortest edges first to avoid crossing boundaries.",
            ),
            evidence=MemoryEvidence(source_artifacts=("heuristic_01.py",), validation_after={"relative_gap": 0.03}),
        )
        tk_unit = normalize_memory_unit_to_transferable(unit)
        self.assertEqual(tk_unit.source_problem, "tsp")
        self.assertEqual(tk_unit.provenance, "managed_ku")
        self.assertEqual(tk_unit.source_heuristic_id, "ku_001")
        self.assertIn("shortest edges", tk_unit.design_description)

        # 2. Population item
        tk_pop = normalize_population_item_to_transferable(
            source_problem="cvrp",
            source_task_id="cvrp_uniform_n50_medium",
            heuristic_id="pop_ind_042",
            thought="Cluster customers by angle from depot before solving individual routes.",
            fitness={"relative_gap": 0.08},
        )
        self.assertEqual(tk_pop.source_problem, "cvrp")
        self.assertEqual(tk_pop.provenance, "population_thought")
        self.assertEqual(tk_pop.source_heuristic_id, "pop_ind_042")
        self.assertIn("Cluster customers", tk_pop.design_description)

        # 3. Naive Archive item
        tk_arch = normalize_archive_item_to_transferable(
            source_problem="jssp",
            source_task_id="jssp_j10_m5",
            heuristic_id="arch_007",
            thought_or_summary="Schedule operations with most remaining work first.",
            performance={"relative_gap": 0.02},
        )
        self.assertEqual(tk_arch.source_problem, "jssp")
        self.assertEqual(tk_arch.provenance, "naive_archive")
        self.assertEqual(tk_arch.source_heuristic_id, "arch_007")

    def test_cross_problem_adapter_formatting(self) -> None:
        """CrossProblemAdapter generates formatted prompt block and forbids direct code inclusion."""
        tk1 = TransferableKnowledge(
            source_problem="tsp",
            source_task_id="tsp_uniform_n50_a",
            algorithmic_principles=["Greedy 2-opt edge swap", "Farthest insertion initialization"],
            design_description="Constructive tour builder with iterative local search",
            source_performance={"relative_gap": 0.045},
            source_heuristic_id="heur_tsp_001",
            provenance="managed_ku",
        )

        prompt_block = CrossProblemAdapter.format_cross_problem_prompt_block(
            knowledge_list=[tk1],
            target_problem="cvrp",
            target_task_id="cvrp_uniform_n50_medium",
        )

        self.assertIn("<TRANSFERRED_KNOWLEDGE>", prompt_block)
        self.assertIn("</TRANSFERRED_KNOWLEDGE>", prompt_block)
        self.assertIn("Source Problem: tsp", prompt_block)
        self.assertIn("Target Problem: cvrp", prompt_block)
        self.assertIn("DO NOT blindly copy data structures", prompt_block)
        self.assertIn("Greedy 2-opt edge swap", prompt_block)
        # Verify no python executable headers or raw python code are leaked
        self.assertNotIn("def solve_tsp", prompt_block)

    def test_target_contract_validator(self) -> None:
        """TargetContractValidator verifies AST contracts for TSP, CVRP, JSSP without executing code."""
        # Valid TSP code
        valid_tsp = """
def solve_tsp(points: list[tuple[float, float]]) -> list[int]:
    n = len(points)
    return list(range(n))
"""
        res = TargetContractValidator.validate_code(valid_tsp, "tsp")
        self.assertTrue(res.is_valid, f"TSP validation failed: {res.error_message}")
        self.assertEqual(res.entrypoint, "solve_tsp")

        # Valid CVRP code
        valid_cvrp = """
def solve_cvrp(depot: tuple[float, float], customers: list[tuple[float, float]], demands: list[int], capacity: int) -> list[list[int]]:
    return [[i] for i in range(1, len(customers) + 1)]
"""
        res_cvrp = TargetContractValidator.validate_code(valid_cvrp, "cvrp")
        self.assertTrue(res_cvrp.is_valid, f"CVRP validation failed: {res_cvrp.error_message}")
        self.assertEqual(res_cvrp.entrypoint, "solve_cvrp")

        # Invalid: Syntax Error
        res_syntax = TargetContractValidator.validate_code("def broken(: pass", "tsp")
        self.assertFalse(res_syntax.is_valid)
        self.assertIn("Syntax error", res_syntax.error_message)

        # Invalid: Wrong Entrypoint Name
        res_wrong_name = TargetContractValidator.validate_code("def solve_route(points): return []", "tsp")
        self.assertFalse(res_wrong_name.is_valid)
        self.assertIn("solve_tsp", res_wrong_name.error_message)

        # Invalid: Wrong Argument Count
        res_wrong_args = TargetContractValidator.validate_code("def solve_tsp(): return []", "tsp")
        self.assertFalse(res_wrong_args.is_valid)
        self.assertIn("parameters", res_wrong_args.error_message)

        # Invalid: Cross-Domain Entrypoint Rejection (e.g. CVRP code submitted to TSP)
        res_mismatch = TargetContractValidator.validate_code(valid_cvrp, "tsp")
        self.assertFalse(res_mismatch.is_valid)


if __name__ == "__main__":
    unittest.main()
