from src.problems.cvrp.components import MergeRoutesOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import profile_from_problem_state
from src.problems.cvrp.route_metrics import compute_route_metrics, normalize_route


def saving_algorithm_710e(
    problem_state: dict, algorithm_data: dict, merge_threshold: float = 0.0, **kwargs
) -> tuple[MergeRoutesOperator | None, dict]:
    """
    Clarke-Wright style savings merge on the current CVRP solution with best-improvement selection.
    Evaluates ordered route pairs (i, j) where merging route i into route j yields a cost reduction.
    Fully constraint-aware: supports both closed and open route semantics, and checks
    vehicle capacity and time window feasibility constraints on the merged route.
    """
    profile = profile_from_problem_state(problem_state)
    depot = problem_state["depot"]
    current_solution = problem_state["current_solution"]

    best_saving = merge_threshold
    best_operator = None

    for i, route1 in enumerate(current_solution.routes):
        norm1 = normalize_route(route1, depot)
        cust1 = [n for n in norm1 if n != depot]
        if not cust1:
            continue
        orig1 = compute_route_metrics(norm1, i, problem_state, profile)
        if not orig1.feasible:
            continue

        for j, route2 in enumerate(current_solution.routes):
            if i == j:
                continue
            norm2 = normalize_route(route2, depot)
            cust2 = [n for n in norm2 if n != depot]
            if not cust2:
                continue
            orig2 = compute_route_metrics(norm2, j, problem_state, profile)
            if not orig2.feasible:
                continue

            merged_route = [depot] + cust1 + cust2
            merged_metrics = compute_route_metrics(merged_route, j, problem_state, profile)
            if not merged_metrics.feasible:
                continue

            saving = (orig1.distance + orig2.distance) - merged_metrics.distance
            if saving > best_saving:
                best_saving = saving
                best_operator = MergeRoutesOperator(source_vehicle_id=i, target_vehicle_id=j)

    if best_operator:
        return best_operator, {}

    return None, {}