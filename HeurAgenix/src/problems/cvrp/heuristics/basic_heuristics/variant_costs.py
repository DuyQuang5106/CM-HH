from src.problems.cvrp.route_metrics import compute_route_metrics
from src.problems.cvrp.variant import profile_from_config


def profile_from_problem_state(problem_state: dict):
    return profile_from_config(
        problem_state.get("constraint_profile")
        or problem_state.get("constraints")
        or problem_state.get("variant")
    )


def is_open_route(problem_state: dict) -> bool:
    return bool(profile_from_problem_state(problem_state).open_route)


def insertion_positions(route: list[int], depot: int) -> range:
    if depot in route:
        return range(route.index(depot) + 1, len(route) + 1)
    return range(0, len(route) + 1)


def insertion_cost_delta(
    distance_matrix,
    route: list[int],
    depot: int,
    node: int,
    position: int,
    open_route: bool,
) -> float:
    previous_node = route[position - 1] if position > 0 else depot
    if position < len(route):
        next_node = route[position]
        return (
            float(distance_matrix[previous_node][node])
            + float(distance_matrix[node][next_node])
            - float(distance_matrix[previous_node][next_node])
        )
    if open_route:
        return float(distance_matrix[previous_node][node])
    return (
        float(distance_matrix[previous_node][node])
        + float(distance_matrix[node][depot])
        - float(distance_matrix[previous_node][depot])
    )


def insertion_route_is_feasible(
    problem_state: dict,
    route: list[int],
    vehicle_id: int,
    node: int,
    position: int,
) -> bool:
    profile = profile_from_problem_state(problem_state)
    if not profile.time_windows:
        return True
    candidate = route[:]
    candidate.insert(position, node)
    metrics = compute_route_metrics(candidate, vehicle_id, problem_state, profile)
    return metrics.feasible
