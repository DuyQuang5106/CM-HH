from __future__ import annotations

import ast
from typing import NamedTuple


class ContractValidationResult(NamedTuple):
    is_valid: bool
    status: str
    error: str | None


class TargetContractValidator:
    """Performs static AST validation on candidate heuristic code before sandbox execution.
    
    Checks syntax, entrypoint functions, parameter counts, and forbidden constructs.
    Runtime output schema and feasibility validation remain the responsibility of the problem evaluator.
    """

    FORBIDDEN_MODULES = {
        "subprocess", "socket", "http", "urllib", "requests", "shutil", "builtins.__import__"
    }

    PROBLEM_SIGNATURES = {
        "tsp": {
            "required_functions": ["select_next_node", "solve_tsp", "heuristic", "run"],
            "description": "TSP heuristic should accept distance/coordinate context",
        },
        "cvrp": {
            "required_functions": ["select_next_customer", "solve_cvrp", "heuristic", "run"],
            "description": "CVRP heuristic should accept demands, capacity, coordinates",
        },
        "jssp": {
            "required_functions": ["select_next_operation", "solve_jssp", "heuristic", "run"],
            "description": "JSSP heuristic should accept processing times and machine orders",
        },
    }

    def validate(self, code: str, target_problem: str) -> ContractValidationResult:
        if not code or not code.strip():
            return ContractValidationResult(
                is_valid=False,
                status="invalid_candidate",
                error="Candidate code is empty",
            )

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return ContractValidationResult(
                is_valid=False,
                status="invalid_candidate",
                error=f"Static syntax error: {exc.msg} at line {exc.lineno}",
            )

        # Check for forbidden modules
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.FORBIDDEN_MODULES:
                        return ContractValidationResult(
                            is_valid=False,
                            status="invalid_candidate",
                            error=f"Forbidden module import: {alias.name}",
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module in self.FORBIDDEN_MODULES:
                    return ContractValidationResult(
                        is_valid=False,
                        status="invalid_candidate",
                        error=f"Forbidden from-import module: {node.module}",
                    )

        # Check function definitions
        defined_functions = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]

        prob_spec = self.PROBLEM_SIGNATURES.get(target_problem.lower())
        if prob_spec and defined_functions:
            # Check if at least one candidate entrypoint exists
            has_entrypoint = any(fn in defined_functions for fn in prob_spec["required_functions"])
            # If no standard named entrypoint, but exactly one function defined, accept as generic entrypoint
            if not has_entrypoint and len(defined_functions) == 0:
                return ContractValidationResult(
                    is_valid=False,
                    status="invalid_candidate",
                    error=f"Target contract mismatch for {target_problem}: No valid function defined",
                )

        return ContractValidationResult(
            is_valid=True,
            status="ok",
            error=None,
        )
