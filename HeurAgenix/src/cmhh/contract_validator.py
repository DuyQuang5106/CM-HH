from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContractValidationResult:
    is_valid: bool
    status: str
    error: str | None = None
    entrypoint: str | None = None

    @property
    def error_message(self) -> str | None:
        return self.error


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
            "expected_params": {"solve_tsp": 1, "select_next_node": 2},
            "description": "TSP heuristic should accept distance/coordinate context",
        },
        "cvrp": {
            "required_functions": ["select_next_customer", "solve_cvrp", "heuristic", "run"],
            "expected_params": {"solve_cvrp": 4, "select_next_customer": 4},
            "description": "CVRP heuristic should accept demands, capacity, coordinates",
        },
        "jssp": {
            "required_functions": ["select_next_operation", "solve_jssp", "heuristic", "run"],
            "expected_params": {"solve_jssp": 2, "select_next_operation": 2},
            "description": "JSSP heuristic should accept processing times and machine orders",
        },
    }

    @classmethod
    def validate_code(cls, code: str, target_problem: str) -> ContractValidationResult:
        validator = cls()
        return validator.validate(code, target_problem)

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
                error=f"Syntax error: {exc.msg} at line {exc.lineno}",
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

        # Check function definitions and parameters
        function_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        defined_functions = [fn.name for fn in function_nodes]

        prob_spec = self.PROBLEM_SIGNATURES.get(target_problem.lower())
        matched_entrypoint: str | None = None
        if prob_spec:
            req_fns = prob_spec["required_functions"]
            expected_params = prob_spec.get("expected_params", {})
            for fn_node in function_nodes:
                if fn_node.name in req_fns:
                    matched_entrypoint = fn_node.name
                    # Check argument count if specified
                    if fn_node.name in expected_params:
                        param_count = len(fn_node.args.args)
                        exp_count = expected_params[fn_node.name]
                        if param_count != exp_count:
                            return ContractValidationResult(
                                is_valid=False,
                                status="invalid_candidate",
                                error=f"Function {fn_node.name} expected {exp_count} parameters, got {param_count}",
                                entrypoint=fn_node.name,
                            )
                    break

            if not matched_entrypoint:
                return ContractValidationResult(
                    is_valid=False,
                    status="invalid_candidate",
                    error=f"Target contract mismatch for {target_problem}: Code must define one of {req_fns}, found {defined_functions}",
                )

        return ContractValidationResult(
            is_valid=True,
            status="ok",
            error=None,
            entrypoint=matched_entrypoint,
        )
