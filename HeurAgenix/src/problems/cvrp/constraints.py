from __future__ import annotations

from dataclasses import dataclass

from src.problems.cvrp.components import Solution
from src.problems.cvrp.route_metrics import compute_route_metrics, customer_sequence
from src.problems.cvrp.variant import VRPConstraintProfile


@dataclass(frozen=True)
class ConstraintResult:
    name: str
    feasible: bool
    violations: list[str]


class Constraint:
    name = "constraint"

    def validate(self, solution: Solution, instance: dict, profile: VRPConstraintProfile) -> ConstraintResult:
        raise NotImplementedError


class NodeExistenceConstraint(Constraint):
    name = "node_existence"

    def validate(self, solution: Solution, instance: dict, profile: VRPConstraintProfile) -> ConstraintResult:
        del profile
        violations = []
        node_num = int(instance["node_num"])
        for route_index, route in enumerate(solution.routes):
            for node in route:
                if not (0 <= node < node_num):
                    violations.append(f"route {route_index} contains invalid node {node}")
        return ConstraintResult(self.name, not violations, violations)


class SingleVisitConstraint(Constraint):
    name = "single_visit"

    def validate(self, solution: Solution, instance: dict, profile: VRPConstraintProfile) -> ConstraintResult:
        del profile
        depot = int(instance["depot"])
        customers = [
            node
            for route in solution.routes
            for node in route
            if node != depot
        ]
        violations = []
        duplicates = sorted({node for node in customers if customers.count(node) > 1})
        if duplicates:
            violations.append(f"duplicate customers: {duplicates}")
        return ConstraintResult(self.name, not violations, violations)


class RouteOriginConstraint(Constraint):
    name = "route_origin"

    def validate(self, solution: Solution, instance: dict, profile: VRPConstraintProfile) -> ConstraintResult:
        del profile
        depot = int(instance["depot"])
        violations = []
        for route_index, route in enumerate(solution.routes):
            if depot not in route:
                violations.append(f"route {route_index} does not include depot {depot}")
        return ConstraintResult(self.name, not violations, violations)


class CapacityConstraint(Constraint):
    name = "capacity"

    def validate(self, solution: Solution, instance: dict, profile: VRPConstraintProfile) -> ConstraintResult:
        violations = []
        for vehicle_id, route in enumerate(solution.routes):
            metrics = compute_route_metrics(route, vehicle_id, instance, profile)
            if not metrics.capacity_feasible:
                violations.append(
                    f"route {vehicle_id} load {metrics.load} exceeds capacity {instance['capacity']}"
                )
        return ConstraintResult(self.name, not violations, violations)


class TimeWindowConstraint(Constraint):
    name = "time_windows"

    def validate(self, solution: Solution, instance: dict, profile: VRPConstraintProfile) -> ConstraintResult:
        violations = []
        for vehicle_id, route in enumerate(solution.routes):
            metrics = compute_route_metrics(route, vehicle_id, instance, profile)
            if metrics.time_window_violations:
                violations.append(
                    f"route {vehicle_id} has {metrics.time_window_violations} time-window violation(s)"
                )
        return ConstraintResult(self.name, not violations, violations)


def active_constraints(profile: VRPConstraintProfile) -> list[Constraint]:
    constraints: list[Constraint] = [
        NodeExistenceConstraint(),
        SingleVisitConstraint(),
        RouteOriginConstraint(),
    ]
    if profile.capacitated:
        constraints.append(CapacityConstraint())
    if profile.time_windows:
        constraints.append(TimeWindowConstraint())
    return constraints


def validate_solution(solution: Solution, instance: dict, profile: VRPConstraintProfile) -> list[ConstraintResult]:
    if not isinstance(solution, Solution) or not isinstance(solution.routes, list):
        return [ConstraintResult("solution_type", False, ["solution must be a CVRP Solution with routes"])]
    return [constraint.validate(solution, instance, profile) for constraint in active_constraints(profile)]


def all_customers_visited(solution: Solution, instance: dict) -> bool:
    depot = int(instance["depot"])
    expected = set(range(int(instance["node_num"]))) - {depot}
    actual = {
        customer
        for route in solution.routes
        for customer in customer_sequence(route, depot)
    }
    return actual == expected
