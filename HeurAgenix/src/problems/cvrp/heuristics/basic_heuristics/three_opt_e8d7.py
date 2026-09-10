from src.problems.cvrp.components import ReverseSegmentOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import profile_from_problem_state
from src.problems.cvrp.route_metrics import compute_route_metrics


def three_opt_e8d7(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[ReverseSegmentOperator | None, dict]:
    """
    Intra-route 3-opt local search with best-improvement strategy.
    Evaluates 3-opt reconnection patterns (represented as 1 or 2 segment reversals)
    within each route. Fully constraint-aware: supports both closed and open route semantics,
    and enforces capacity and time window feasibility constraints.
    """
    profile = profile_from_problem_state(problem_state)
    current_solution = problem_state["current_solution"]

    best_delta = -1e-6
    best_move = None

    for route_index, route in enumerate(current_solution.routes):
        n = len(route)
        if n <= 3:
            continue

        original_metrics = compute_route_metrics(route, route_index, problem_state, profile)
        if not original_metrics.feasible:
            continue

        for i in range(1, n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    # Test 3 standard 2-reversal patterns
                    patterns = [
                        [(i, j - 1), (j, k - 1)],
                        [(i, j - 1)],
                        [(j, k - 1)],
                    ]
                    for segments in patterns:
                        candidate = route[:]
                        for start_idx, end_idx in segments:
                            candidate[start_idx : end_idx + 1] = reversed(candidate[start_idx : end_idx + 1])
                        candidate_metrics = compute_route_metrics(candidate, route_index, problem_state, profile)
                        if not candidate_metrics.feasible:
                            continue

                        delta = candidate_metrics.distance - original_metrics.distance
                        if delta < best_delta:
                            best_delta = delta
                            best_move = (route_index, segments)

    if best_move:
        route_index, segments = best_move
        return ReverseSegmentOperator(route_index, segments), algorithm_data

    return None, algorithm_data