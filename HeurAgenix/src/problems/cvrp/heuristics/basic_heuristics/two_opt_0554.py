from src.problems.cvrp.components import ReverseSegmentOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import profile_from_problem_state
from src.problems.cvrp.route_metrics import compute_route_metrics


def two_opt_0554(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[ReverseSegmentOperator | None, dict]:
    """
    Intra-route 2-opt local search with best-improvement strategy.
    Evaluates reversing contiguous customer segments within each route.
    Fully constraint-aware: supports both closed and open route semantics,
    and enforces capacity and time window feasibility constraints.
    """
    profile = profile_from_problem_state(problem_state)
    current_solution = problem_state["current_solution"]

    best_delta = -1e-6
    best_move = None

    for route_index, route in enumerate(current_solution.routes):
        if len(route) <= 2:
            continue
        original_metrics = compute_route_metrics(route, route_index, problem_state, profile)
        if not original_metrics.feasible:
            continue

        # Evaluate reversing segment [i, j]
        for i in range(1, len(route)):
            for j in range(i + 1, len(route)):
                candidate = route[:]
                candidate[i : j + 1] = reversed(candidate[i : j + 1])
                candidate_metrics = compute_route_metrics(candidate, route_index, problem_state, profile)
                if not candidate_metrics.feasible:
                    continue

                delta = candidate_metrics.distance - original_metrics.distance
                if delta < best_delta:
                    best_delta = delta
                    best_move = (route_index, [(i, j)])

    if best_move:
        route_index, move_pair = best_move
        return ReverseSegmentOperator(route_index, move_pair), algorithm_data

    return None, algorithm_data