from src.problems.cvrp.components import InsertOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import (
    insertion_positions,
    insertion_route_is_feasible,
)


def nearest_neighbor_99ba(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[InsertOperator | None, dict]:
    """
    Greedy nearest-neighbor with capacity and time-window filtering for CVRP variants.
    Finds the closest unvisited customer to the current route tail or best intermediate position.
    """
    distance_matrix = problem_state['distance_matrix']
    demands = problem_state['demands']
    depot = problem_state['depot']

    unvisited_nodes = problem_state['unvisited_nodes']
    vehicle_remaining_capacity = problem_state['vehicle_remaining_capacity']
    current_solution = problem_state['current_solution'].routes
    has_tw = bool(problem_state.get('constraints', {}).get('time_windows'))

    # Iterate over each vehicle
    for vehicle_id, remaining_capacity in enumerate(vehicle_remaining_capacity):
        if not unvisited_nodes or remaining_capacity <= 0:
            continue

        route = current_solution[vehicle_id]
        last_visited = depot if not route else route[-1]
        nearest_node = None
        min_distance = float('inf')
        best_position = len(route)

        # Find the nearest unvisited node that satisfies constraints
        for node in unvisited_nodes:
            if demands[node] > remaining_capacity:
                continue
            positions = (
                [len(route)] + [p for p in insertion_positions(route, depot) if p != len(route)]
                if has_tw
                else [len(route)]
            )
            for position in positions:
                if (
                    insertion_route_is_feasible(problem_state, route, vehicle_id, node, position)
                    and distance_matrix[last_visited][node] < min_distance
                ):
                    nearest_node = node
                    min_distance = distance_matrix[last_visited][node]
                    best_position = position

        if nearest_node is not None:
            return InsertOperator(vehicle_id, nearest_node, best_position), {}

    return None, {}
