from src.problems.cvrp.components import AppendOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import insertion_route_is_feasible
import random

def random_bfdc(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[AppendOperator, dict]:
    """
    Stochastic constructive assignment with capacity-only feasibility. At each call: (1) uniformly sample one unvisited customer, (2) sample up to V vehicles uniformly at random with replacement, accepting the first whose remaining capacity can cover the customer’s demand, and (3) append the customer to the end of that vehicle’s route. No distance or insertion-cost evaluation; the distance matrix is unused. This is a first-feasible randomized policy (not “best” by any measure such as nearest, cheapest, or best-fit), and because vehicles are sampled with replacement, earlier-sampled feasible vehicles are favored; there is no deterministic tie-breaking. Stateless aside from RNG; does not update algorithm_data. Per-invocation complexity O(V) time, O(1) memory. Best used for diversification or quick feasible construction; expected route cost quality relies on subsequent improvement operators.

    Args:
        problem_state (dict): The dictionary contains the problem state. In this algorithm, the following items are necessary:
            - "demands" (numpy.ndarray): The demand of each node.
            - "vehicle_num" (int): The total number of vehicles.
            - "capacity" (int): The capacity for each vehicle.
            - "unvisited_nodes" (list[int]): Nodes that have not yet been visited by any vehicle.
            - "vehicle_remaining_capacity" (list[int]): The remaining capacity for each vehicle.
            - "current_solution" (Solution): The current set of routes for all vehicles.

    Returns:
        AppendOperator: The operator to append a node to a vehicle's route.
        dict: Empty dictionary as no algorithm data needs to be updated.
    """
    unvisited_nodes = problem_state['unvisited_nodes']
    vehicle_remaining_capacity = problem_state['vehicle_remaining_capacity']
    current_solution = problem_state['current_solution']
    demands = problem_state['demands']
    vehicle_num = problem_state['vehicle_num']
    capacity = problem_state['capacity']

    # Check if we have any unvisited nodes left
    if not unvisited_nodes:
        return None, {}

    feasible_pairs = []
    for node in unvisited_nodes:
        for vehicle_id in range(vehicle_num):
            route = current_solution.routes[vehicle_id]
            position = len(route)
            if (
                vehicle_remaining_capacity[vehicle_id] >= demands[node]
                and insertion_route_is_feasible(problem_state, route, vehicle_id, node, position)
            ):
                feasible_pairs.append((vehicle_id, node))

    if feasible_pairs:
        vehicle_id, node_to_append = random.choice(feasible_pairs)
        return AppendOperator(vehicle_id=vehicle_id, node=node_to_append), {}

    # If we reach here, no vehicle can accommodate the node (should not happen if vehicles start empty and capacities are correct)
    return None, {}
