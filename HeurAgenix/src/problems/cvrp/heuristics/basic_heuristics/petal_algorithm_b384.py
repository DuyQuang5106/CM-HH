from src.problems.cvrp.components import Solution, InsertOperator
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import insertion_route_is_feasible
import math

def petal_algorithm_b384(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[InsertOperator | None, dict]:
    """
    Sweep-style single-customer petal seeding. Unvisited customers are ordered by a depot-centric polar angle.
    The heuristic scans customers in this angular order and vehicles in identifier order, returning the first
    feasible append-to-end insertion that respects both capacity and time-window constraints.
    """
    distance_matrix = problem_state["distance_matrix"]
    demands = problem_state["demands"]
    vehicle_capacity = problem_state["capacity"]
    vehicle_remaining_capacity = problem_state["vehicle_remaining_capacity"].copy()
    current_solution = problem_state["current_solution"].routes
    unvisited_nodes = problem_state["unvisited_nodes"].copy()

    if not unvisited_nodes:
        return None, {}

    # Sort nodes based on their polar angle with respect to the depot
    depot = problem_state.get("depot", 0)
    sorted_nodes = sorted(unvisited_nodes, key=lambda node: polar_angle(distance_matrix, depot, node))

    # Create petals
    petals = []
    for node in sorted_nodes:
        if demands[node] <= vehicle_capacity:
            petals.append([node])

    # Try to fit petals into existing vehicle routes
    for petal in petals:
        node = petal[0]
        for vehicle_id, route in enumerate(current_solution):
            if route_fits(petal, vehicle_id, vehicle_remaining_capacity, demands, vehicle_capacity):
                if insertion_route_is_feasible(problem_state, route, vehicle_id, node, len(route)):
                    return InsertOperator(vehicle_id=vehicle_id, node=node, position=len(route)), {}

    return None, {}

def polar_angle(distance_matrix, depot, node):
    """Calculate the polar angle of a node with respect to the depot for sorting."""
    y_diff = distance_matrix[depot][node] - distance_matrix[depot][0]
    x_diff = distance_matrix[node][depot] - distance_matrix[0][depot]
    return math.atan2(y_diff, x_diff)

def route_fits(petal, vehicle_id, vehicle_remaining_capacity, demands, vehicle_capacity):
    """Check if a petal can fit into the current route of a vehicle."""
    petal_demand = sum(demands[node] for node in petal)
    return petal_demand <= vehicle_remaining_capacity[vehicle_id]