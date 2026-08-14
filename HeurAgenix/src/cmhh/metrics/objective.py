from __future__ import annotations

import math


def relative_gap(candidate: float, reference: float, epsilon: float = 1e-12) -> float:
    if not math.isfinite(candidate) or not math.isfinite(reference):
        raise ValueError("Objectives must be finite")
    if reference <= 0:
        raise ValueError("Reference objective must be positive")
    return (candidate - reference) / max(abs(reference), epsilon)


def score_from_gap(gap: float) -> float:
    if not math.isfinite(gap):
        raise ValueError("Gap must be finite")
    return -gap

