from src.problems.cvrp.components import InsertOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import (
    insertion_positions,
    insertion_route_is_feasible,
)


def greedy_f4c4(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[InsertOperator | None, dict]:
    """
    Constructive nearest-from-depot assignment for CVRP variants.
    Selects the closest customer to the depot that satisfies capacity and time windows.
    """
    distance_matrix = problem_state['distance_matrix']
    demands = problem_state['demands']
    vehicle_num = problem_state['vehicle_num']
    depot = problem_state.get('depot', 0)

    unvisited_nodes = problem_state['unvisited_nodes']
    vehicle_remaining_capacity = problem_state['vehicle_remaining_capacity']
    current_solution = problem_state['current_solution'].routes
    has_tw = bool(problem_state.get('constraints', {}).get('time_windows'))

    for vehicle_id in range(vehicle_num):
        if not unvisited_nodes or vehicle_remaining_capacity[vehicle_id] <= 0:
            continue

        closest_node = None
        closest_distance = float('inf')
        best_position = None

        route = current_solution[vehicle_id]
        for node in unvisited_nodes:
            if demands[node] > vehicle_remaining_capacity[vehicle_id]:
                continue
            positions = (
                [len(route)] + [p for p in insertion_positions(route, depot) if p != len(route)]
                if has_tw
                else [len(route)]
            )
            for position in positions:
                if (
                    insertion_route_is_feasible(problem_state, route, vehicle_id, node, position)
                    and distance_matrix[depot][node] < closest_distance
                ):
                    closest_distance = distance_matrix[depot][node]
                    closest_node = node
                    best_position = position

        if closest_node is not None and best_position is not None:
            return InsertOperator(vehicle_id, closest_node, best_position), {}

    return None, {}
