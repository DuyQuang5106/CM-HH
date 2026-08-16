from __future__ import annotations

from pathlib import Path

from cmhh.data.tsp_io import load_euc2d_graph


def parse_concorde_tour(path: str | Path, dimension: int) -> list[int]:
    tokens = [int(token) for token in Path(path).read_text(encoding="ascii").split()]
    if len(tokens) == dimension + 1 and tokens[0] == dimension:
        tokens = tokens[1:]
    if len(tokens) != dimension:
        raise ValueError(f"Expected {dimension} tour nodes, found {len(tokens)}")
    if set(tokens) == set(range(1, dimension + 1)):
        tokens = [node - 1 for node in tokens]
    if set(tokens) != set(range(dimension)):
        raise ValueError("Tour is not a permutation of all nodes")
    return tokens


def tour_objective(instance_path: str | Path, tour: list[int]) -> float:
    graph = load_euc2d_graph(instance_path)
    if set(tour) != set(range(len(graph))):
        raise ValueError("Tour does not match instance nodes")
    total = 0.0
    for index, node in enumerate(tour):
        next_node = tour[(index + 1) % len(tour)]
        edge = graph[node][next_node]
        total += float(edge["weight"] if isinstance(edge, dict) else edge)
    return total


def write_normalized_tour(path: str | Path, tour: list[int]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{len(tour)}\n" + " ".join(map(str, tour)) + "\n", encoding="ascii")

