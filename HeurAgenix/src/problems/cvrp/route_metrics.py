from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Sequence

from src.problems.cvrp.variant import VRPConstraintProfile


@dataclass(frozen=True)
class RouteMetrics:
    distance: float
    load: float
    remaining_capacity: float
    arrival_times: list[float]
    service_start_times: list[float]
    waiting_time: float
    time_window_violations: int
    capacity_feasible: bool
    time_window_feasible: bool
    feasible: bool


def normalize_route(route: Sequence[int], depot: int) -> list[int]:
    nodes = list(route)
    if not nodes:
        return [depot]
    if depot in nodes:
        depot_index = nodes.index(depot)
        nodes = nodes[depot_index:] + nodes[:depot_index]
    else:
        nodes = [depot] + nodes
    while len(nodes) > 1 and nodes[-1] == depot:
        nodes.pop()
    return nodes


def customer_sequence(route: Sequence[int], depot: int) -> list[int]:
    return [node for node in normalize_route(route, depot) if node != depot]


def route_distance(route: Sequence[int], instance: dict, profile: VRPConstraintProfile) -> float:
    depot = int(instance["depot"])
    normalized = normalize_route(route, depot)
    if len(normalized) <= 1:
        return 0.0

    distance_matrix = instance["distance_matrix"]
    distance = 0.0
    for index in range(len(normalized) - 1):
        distance += float(distance_matrix[normalized[index]][normalized[index + 1]])
    if not profile.open_route:
        distance += float(distance_matrix[normalized[-1]][depot])
    return distance


def compute_route_metrics(
    route: Sequence[int],
    vehicle_id: int,
    instance: dict,
    profile: VRPConstraintProfile,
) -> RouteMetrics:
    del vehicle_id
    depot = int(instance["depot"])
    normalized = normalize_route(route, depot)
    customers = [node for node in normalized if node != depot]
    demands = instance["demands"]
    capacity = float(instance.get("capacity", inf))
    load = float(sum(float(demands[node]) for node in customers))
    remaining_capacity = capacity - load
    capacity_feasible = (not profile.capacitated) or load <= capacity

    distance = route_distance(normalized, instance, profile)
    arrival_times: list[float] = []
    service_start_times: list[float] = []
    waiting_time = 0.0
    time_window_violations = 0

    if profile.time_windows:
        distance_matrix = instance["distance_matrix"]
        time_windows = instance.get("time_windows", {})
        service_times = instance.get("service_times", {})
        current_node = depot
        current_time = 0.0

        for customer in customers:
            arrival = current_time + float(distance_matrix[current_node][customer])
            earliest, latest = _time_window_for_node(time_windows, customer)
            service_start = max(arrival, earliest)
            waiting_time += max(0.0, earliest - arrival)
            if service_start > latest:
                time_window_violations += 1
            arrival_times.append(arrival)
            service_start_times.append(service_start)
            current_time = service_start + _service_time_for_node(service_times, customer)
            current_node = customer

        if not profile.open_route and customers:
            depot_arrival = current_time + float(distance_matrix[current_node][depot])
            depot_earliest, depot_latest = _time_window_for_node(time_windows, depot)
            service_start = max(depot_arrival, depot_earliest)
            waiting_time += max(0.0, depot_earliest - depot_arrival)
            if service_start > depot_latest:
                time_window_violations += 1
            arrival_times.append(depot_arrival)
            service_start_times.append(service_start)

    time_window_feasible = (not profile.time_windows) or time_window_violations == 0
    return RouteMetrics(
        distance=distance,
        load=load,
        remaining_capacity=remaining_capacity,
        arrival_times=arrival_times,
        service_start_times=service_start_times,
        waiting_time=waiting_time,
        time_window_violations=time_window_violations,
        capacity_feasible=capacity_feasible,
        time_window_feasible=time_window_feasible,
        feasible=capacity_feasible and time_window_feasible,
    )


def total_solution_distance(solution, instance: dict, profile: VRPConstraintProfile) -> float:
    return sum(
        compute_route_metrics(route, vehicle_id, instance, profile).distance
        for vehicle_id, route in enumerate(solution.routes)
    )


def _time_window_for_node(time_windows, node: int) -> tuple[float, float]:
    if isinstance(time_windows, dict):
        value = time_windows.get(node, time_windows.get(str(node), None))
        if value is None and "customers" in time_windows:
            customers = time_windows["customers"]
            value = customers.get(node, customers.get(str(node), None))
        if value is None and node == 0 and "depot" in time_windows:
            value = time_windows["depot"]
    else:
        value = time_windows[node] if node < len(time_windows) else None

    if value is None:
        return (0.0, inf)
    return (float(value[0]), float(value[1]))


def _service_time_for_node(service_times, node: int) -> float:
    if isinstance(service_times, dict):
        return float(service_times.get(node, service_times.get(str(node), service_times.get("default", 0.0))))
    if service_times and node < len(service_times):
        return float(service_times[node])
    return 0.0
