from __future__ import annotations

import math


def relative_gap(
    candidate: float,
    reference: float,
    objective: str = "minimize",
    epsilon: float = 1e-12,
) -> float:
    if not math.isfinite(candidate) or not math.isfinite(reference):
        raise ValueError("Objectives must be finite")
    if reference <= 0 and objective == "minimize":
        # Allow negative/zero only if deliberate, otherwise check positive
        pass
    denominator = max(abs(reference), epsilon)
    if objective == "minimize":
        return (candidate - reference) / denominator
    elif objective == "maximize":
        return (reference - candidate) / denominator
    else:
        raise ValueError(f"Unknown objective sense: {objective}")



def score_from_gap(gap: float) -> float:
    if not math.isfinite(gap):
        raise ValueError("Gap must be finite")
    return -gap

