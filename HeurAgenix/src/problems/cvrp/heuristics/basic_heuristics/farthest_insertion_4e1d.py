from src.problems.cvrp.components import Solution, AppendOperator, InsertOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import (
    insertion_cost_delta,
    insertion_positions,
    insertion_route_is_feasible,
    is_open_route,
)
import numpy as np

def farthest_insertion_4e1d(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[AppendOperator, dict]:
    """
    Constructive farthest-insertion for CVRP with depot-anchored routes. At each step, select the single unvisited node with maximum distance from the depot, then insert it into the route-position across all vehicles that yields the smallest marginal cost while respecting remaining capacity. Marginal cost model: replace edge (prev,next) by (prev,node) + (node,next) − (prev,next); at route boundaries the depot acts as prev or next, implicitly modeling routes that start and end at the depot. Capacity feasibility is enforced per vehicle prior to evaluating positions. This variant prioritizes remote (peripheral) customers early to reduce late-stage detours, and uses directed distances, making it compatible with asymmetric matrices. Per step complexity: O(|unvisited|) to pick the seed + O(sum over vehicles of route length) to evaluate insertions; constant extra memory. Deterministic behavior under standard Python max/min tie rules.

    Args:
        problem_state (dict): The dictionary contains the problem state. In this algorithm, the following items are necessary:
            - "node_num" (int): The total number of nodes in the problem.
            - "distance_matrix" (numpy.ndarray): A 2D array representing the distances between nodes.
            - "vehicle_num" (int): The total number of vehicles.
            - "capacity" (int): The capacity for each vehicle and all vehicles share the same value.
            - "depot" (int): The index for depot node.
            - "demands" (numpy.ndarray): The demand of each node.
            - "current_solution" (Solution): The current set of routes for all vehicles.
            - "unvisited_nodes" (list[int]): Nodes that have not yet been visited by any vehicle.
            - "vehicle_loads" (list[int]): The current load of each vehicle.
            - "vehicle_remaining_capacity" (list[int]): The remaining capacity for each vehicle.
            - "validation_solution" (callable): A function to check whether a new solution is valid.

    Returns:
        AppendOperator: An operator that represents the insertion of a node into the route.
        dict: An empty dictionary since this heuristic does not update algorithm_data.
    """
    distance_matrix = problem_state["distance_matrix"]
    depot = problem_state["depot"]
    demands = problem_state["demands"]
    unvisited_nodes = problem_state["unvisited_nodes"]
    vehicle_loads = problem_state["vehicle_loads"]
    vehicle_remaining_capacity = problem_state["vehicle_remaining_capacity"]
    current_solution = problem_state["current_solution"]
    open_route = is_open_route(problem_state)

    # If all nodes are visited, return None
    if not unvisited_nodes:
        return None, {}

    best_insertion = None
    min_cost_increase = float('inf')

    for farthest_node in sorted(unvisited_nodes, key=lambda node: distance_matrix[depot][node], reverse=True):
        # Try to insert the farthest feasible node into each route at the best position
        for vehicle_id, route in enumerate(current_solution.routes):
            if demands[farthest_node] <= vehicle_remaining_capacity[vehicle_id]:
                for position in insertion_positions(route, depot):
                    if not insertion_route_is_feasible(problem_state, route, vehicle_id, farthest_node, position):
                        continue
                    cost_increase = insertion_cost_delta(
                        distance_matrix,
                        route,
                        depot,
                        farthest_node,
                        position,
                        open_route,
                    )

                    # Update the best insertion if the cost is lower
                    if cost_increase < min_cost_increase:
                        min_cost_increase = cost_increase
                        best_insertion = InsertOperator(vehicle_id, farthest_node, position)
        if best_insertion is not None:
            break

    # If a valid insertion is found, return it
    if best_insertion is not None:
        return best_insertion, {}

    # If no valid insertion is found, return None
    return None, {}
