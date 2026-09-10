from src.problems.cvrp.components import Solution, AppendOperator, InsertOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import (
    insertion_cost_delta,
    insertion_positions,
    insertion_route_is_feasible,
    is_open_route,
)
import numpy as np

def min_cost_insertion_048f(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[InsertOperator, dict]:
    """
    Global best-improvement min-cost insertion for depot-anchored CVRP routes. Scans all unvisited nodes and all vehicles; for each feasible vehicle (remaining capacity ≥ node demand), evaluates positions 1..L where 0 is reserved for the depot sentinel. Marginal cost at position i is computed by replacing edge (prev,next) with (prev,node)+(node,next), with prev=depot when i=1 and next=depot when i=L (thus preserving route closure and keeping the depot fixed at index 0). Selects the single node–vehicle–position triple with the smallest cost increase across the entire fleet (not first-improvement), then returns an InsertOperator for that triple. Supports asymmetric distance matrices; handles empty routes (depot-only) via insertion at position 1. Time complexity: O(|unvisited| · Σ_v |route_v|); minimal extra memory. Capacity is enforced solely via remaining capacity; vehicle_loads are not used.

    Args:
        problem_state (dict): The dictionary contains the problem state. In this algorithm, the following items are necessary:
            - "node_num" (int): Total number of nodes.
            - "distance_matrix" (numpy.ndarray): 2D array representing distances between nodes.
            - "vehicle_num" (int): Total number of vehicles.
            - "capacity" (int): Capacity for each vehicle.
            - "depot" (int): Index for depot node.
            - "demands" (numpy.ndarray): Demand of each node.
            - "current_solution" (Solution): Current set of routes.
            - "unvisited_nodes" (list[int]): Nodes not yet visited.
            - "vehicle_loads" (list[int]): Current load of each vehicle.
            - "vehicle_remaining_capacity" (list[int]): Remaining capacity for each vehicle.
        kwargs: Additional hyper-parameters for the algorithm. Default values should be set here if needed.

    Returns:
        An InsertOperator for inserting the node at the optimal position.
        An updated algorithm data dictionary.
    """

    # Extract necessary data
    distance_matrix = problem_state["distance_matrix"]
    depot = problem_state["depot"]
    demands = problem_state["demands"]
    
    current_solution = problem_state["current_solution"]
    unvisited_nodes = problem_state["unvisited_nodes"]
    vehicle_loads = problem_state["vehicle_loads"]
    vehicle_remaining_capacity = problem_state["vehicle_remaining_capacity"]
    open_route = is_open_route(problem_state)

    # Initialize variables to track the best insertion
    best_increase = float('inf')
    best_operator = None

    # Iterate over all unvisited nodes to find the best insertion point
    for node in unvisited_nodes:
        node_demand = demands[node]

        # Check each vehicle's route for possible insertion points
        for vehicle_id, route in enumerate(current_solution.routes):
            if vehicle_remaining_capacity[vehicle_id] < node_demand:
                continue

            # Iterate over all possible positions to insert the node
            for position in insertion_positions(route, depot):
                if not insertion_route_is_feasible(problem_state, route, vehicle_id, node, position):
                    continue
                increase = insertion_cost_delta(
                    distance_matrix,
                    route,
                    depot,
                    node,
                    position,
                    open_route,
                )

                # Check if this is the best insertion found
                if increase < best_increase:
                    best_increase = increase
                    best_operator = InsertOperator(vehicle_id, node, position)

    # If no valid insertion was found, return None
    if best_operator is None:
        return None, {}

    # Return the best insertion operator found
    return best_operator, {}
