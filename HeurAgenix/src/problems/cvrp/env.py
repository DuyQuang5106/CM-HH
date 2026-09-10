import json
import os
import tsplib95
import numpy as np
import networkx as nx
from src.problems.base.env import BaseEnv
from src.problems.cvrp.components import Solution
from src.problems.cvrp.constraints import all_customers_visited, validate_solution
from src.problems.cvrp.route_metrics import total_solution_distance
from src.problems.cvrp.variant import CVRP_PROFILE, profile_from_config


class Env(BaseEnv):
    """CVRP env that stores the instance data, current solution, and problem state to support algorithm."""
    def __init__(self, data_name: str, **kwargs):
        self.constraint_profile = profile_from_config(
            kwargs.get("constraint_profile") or kwargs.get("variant") or kwargs.get("profile")
        )
        super().__init__(data_name, "cvrp")
        self.constraint_profile = self.instance_data.get("constraint_profile", self.constraint_profile)
        self.construction_steps = self.instance_data["node_num"]
        self.key_item = "total_current_cost"
        self.compare = lambda x, y: y - x

    @property
    def is_complete_solution(self) -> bool:
        return all_customers_visited(self.current_solution, self.instance_data)

    def load_data(self, data_path: str) -> None:
        problem = tsplib95.load(data_path)
        meta = _load_meta(data_path)
        constraint_profile = profile_from_config(
            meta.get("variant") or meta.get("constraints") or getattr(self, "constraint_profile", CVRP_PROFILE)
        )
        depots = getattr(problem, "depots", None)
        depot = (depots[0] - 1) if (depots and len(depots) > 0) else 0
        if problem.edge_weight_type == "EUC_2D":
            node_coords = problem.node_coords
            node_num = len(node_coords)
            distance_matrix = np.zeros((node_num, node_num))
            for i in range(node_num):
                for j in range(node_num):
                    if i != j:
                        x1, y1 = node_coords[i + 1]
                        x2, y2 = node_coords[j + 1]
                        distance_matrix[i][j] = np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
        else:
            distance_matrix = nx.to_numpy_array(problem.get_graph())
            node_num = len(distance_matrix)
        if os.path.basename(data_path).split(".")[0].split("-")[-1][0] == "k":
            vehicle_num = int(os.path.basename(data_path).split(".")[0].split("-")[-1][1:])
        elif open(data_path).readlines()[-1].strip().split(" : ")[0] == "VEHICLE":
            vehicle_num = int(open(data_path).readlines()[-1].strip().split(" : ")[-1])
        else:
            raise NotImplementedError("Vehicle number error")
        capacity = problem.capacity
        demands = np.array(list(problem.demands.values()))
        instance_data = {
            "node_num": node_num,
            "distance_matrix": distance_matrix,
            "depot": depot,
            "vehicle_num": vehicle_num,
            "capacity": capacity,
            "demands": demands,
            "family": "vrp",
            "variant": constraint_profile.variant,
            "constraints": constraint_profile.to_dict(),
            "constraint_profile": constraint_profile,
        }
        if "time_windows" in meta:
            instance_data["time_windows"] = meta["time_windows"]
        if "service_times" in meta:
            instance_data["service_times"] = meta["service_times"]
        return instance_data

    def init_solution(self) -> Solution:
        return Solution(routes=[[self.instance_data["depot"]] for _ in range(self.instance_data["vehicle_num"])], depot=self.instance_data["depot"])

    def get_key_value(self, solution: Solution=None) -> float:
        """Get the key value of the current solution based on the key item."""
        if solution is None:
            solution = self.current_solution
        return total_solution_distance(solution, self.instance_data, self.constraint_profile)

    def validation_solution(self, solution: Solution=None) -> bool:
        """
        Check the validation of this solution in following items:
            1. Node existence: Each node in each route must be within the valid range.
            2. Uniqueness: Each node (except for the depot) must only be visited once across all routes.
            3. Include depot: Each route must include at the depot.
            4. Capacity constraints: The load of each vehicle must not exceed its capacity.
        """
        if solution is None:
            solution = self.current_solution

        return all(result.feasible for result in validate_solution(solution, self.instance_data, self.constraint_profile))


def _load_meta(data_path: str) -> dict:
    meta_path = os.path.splitext(data_path)[0] + ".meta.json"
    if not os.path.exists(meta_path):
        return {}
    with open(meta_path, encoding="utf-8") as fp:
        return json.load(fp)
