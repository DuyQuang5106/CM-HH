from __future__ import annotations

import math
from pathlib import Path


def read_euc2d_coordinates(path: str | Path) -> list[tuple[int, int]]:
    coordinates: list[tuple[int, int]] = []
    in_section = False
    with Path(path).open("r", encoding="utf-8") as fp:
        for raw_line in fp:
            line = raw_line.strip()
            if not line:
                continue
            if line == "NODE_COORD_SECTION":
                in_section = True
                continue
            if line == "EOF":
                break
            if not in_section:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            coordinates.append((int(float(parts[1])), int(float(parts[2]))))
    return coordinates


def load_euc2d_graph(path: str | Path) -> list[list[int]]:
    coordinates = read_euc2d_coordinates(path)
    return [
        [_euc2d_distance(first, second) for second in coordinates]
        for first in coordinates
    ]


def _euc2d_distance(first: tuple[int, int], second: tuple[int, int]) -> int:
    return int(math.hypot(first[0] - second[0], first[1] - second[1]) + 0.5)
