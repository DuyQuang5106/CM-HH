from src.problems.cvrp.components import RelocateOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import profile_from_problem_state
from src.problems.cvrp.route_metrics import compute_route_metrics


def node_shift_between_routes_7b8a(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[RelocateOperator | None, dict]:
    """
    Inter-route relocate with best-improvement strategy.
    Evaluates moving a customer node from a source vehicle route to any position
    in a different target vehicle route. Fully constraint-aware: supports both
    closed and open route semantics, and checks vehicle capacity and time window
    feasibility for both modified routes.
    """
    profile = profile_from_problem_state(problem_state)
    depot = problem_state["depot"]
    current_solution = problem_state["current_solution"]

    best_cost_reduction = 1e-6
    best_move = None

    for source_vehicle_id, source_route in enumerate(current_solution.routes):
        if len(source_route) <= 1:
            continue
        orig_src_metrics = compute_route_metrics(source_route, source_vehicle_id, problem_state, profile)
        if not orig_src_metrics.feasible:
            continue

        for source_position, node in enumerate(source_route):
            if node == depot:
                continue

            candidate_src = [n for idx, n in enumerate(source_route) if idx != source_position]
            new_src_metrics = compute_route_metrics(candidate_src, source_vehicle_id, problem_state, profile)
            if not new_src_metrics.feasible:
                continue

            for target_vehicle_id, target_route in enumerate(current_solution.routes):
                if source_vehicle_id == target_vehicle_id:
                    continue

                orig_tgt_metrics = compute_route_metrics(target_route, target_vehicle_id, problem_state, profile)
                if not orig_tgt_metrics.feasible:
                    continue

                # Target insertion positions: from after depot (index 1) to end of route
                tgt_start = 1 if (depot in target_route) else 0
                for target_position in range(tgt_start, len(target_route) + 1):
                    candidate_tgt = list(target_route)
                    candidate_tgt.insert(target_position, node)
                    new_tgt_metrics = compute_route_metrics(candidate_tgt, target_vehicle_id, problem_state, profile)
                    if not new_tgt_metrics.feasible:
                        continue

                    old_total = orig_src_metrics.distance + orig_tgt_metrics.distance
                    new_total = new_src_metrics.distance + new_tgt_metrics.distance
                    cost_reduction = old_total - new_total

                    if cost_reduction > best_cost_reduction:
                        best_cost_reduction = cost_reduction
                        best_move = (source_vehicle_id, source_position, target_vehicle_id, target_position)

    if best_move:
        src_v, src_p, tgt_v, tgt_p = best_move
        return RelocateOperator(
            source_vehicle_id=src_v,
            source_position=src_p,
            target_vehicle_id=tgt_v,
            target_position=tgt_p,
        ), {}

    return None, {}