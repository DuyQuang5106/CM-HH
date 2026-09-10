from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VRPConstraintProfile:
    capacitated: bool = True
    open_route: bool = False
    time_windows: bool = False
    heterogeneous_fleet: bool = False
    max_route_distance: bool = False
    max_route_duration: bool = False
    pickup_delivery: bool = False

    @property
    def variant(self) -> str:
        if self.open_route and self.time_windows:
            return "ovrptw"
        if self.open_route:
            return "ovrp"
        if self.time_windows:
            return "vrptw"
        return "cvrp"

    def to_dict(self) -> dict[str, bool]:
        return {
            "capacitated": self.capacitated,
            "open_route": self.open_route,
            "time_windows": self.time_windows,
            "heterogeneous_fleet": self.heterogeneous_fleet,
            "max_route_distance": self.max_route_distance,
            "max_route_duration": self.max_route_duration,
            "pickup_delivery": self.pickup_delivery,
        }


CVRP_PROFILE = VRPConstraintProfile(
    capacitated=True,
    open_route=False,
    time_windows=False,
)

OVRP_PROFILE = VRPConstraintProfile(
    capacitated=True,
    open_route=True,
    time_windows=False,
)

OVRPTW_PROFILE = VRPConstraintProfile(
    capacitated=True,
    open_route=True,
    time_windows=True,
)

VRPTW_PROFILE = VRPConstraintProfile(
    capacitated=True,
    open_route=False,
    time_windows=True,
)


_PROFILE_BY_VARIANT = {
    "cvrp": CVRP_PROFILE,
    "ovrp": OVRP_PROFILE,
    "ovrptw": OVRPTW_PROFILE,
    "vrptw": VRPTW_PROFILE,
}


def profile_from_config(config: dict | VRPConstraintProfile | None) -> VRPConstraintProfile:
    if config is None:
        return CVRP_PROFILE
    if isinstance(config, VRPConstraintProfile):
        return config
    if isinstance(config, str):
        return _PROFILE_BY_VARIANT.get(config.lower(), CVRP_PROFILE)

    variant = config.get("variant") or config.get("name")
    if isinstance(variant, str) and variant.lower() in _PROFILE_BY_VARIANT:
        base = _PROFILE_BY_VARIANT[variant.lower()]
    else:
        base = CVRP_PROFILE

    constraints = config.get("constraints", config)
    return VRPConstraintProfile(
        capacitated=bool(constraints.get("capacitated", base.capacitated)),
        open_route=bool(constraints.get("open_route", base.open_route)),
        time_windows=bool(constraints.get("time_windows", base.time_windows)),
        heterogeneous_fleet=bool(constraints.get("heterogeneous_fleet", base.heterogeneous_fleet)),
        max_route_distance=bool(constraints.get("max_route_distance", base.max_route_distance)),
        max_route_duration=bool(constraints.get("max_route_duration", base.max_route_duration)),
        pickup_delivery=bool(constraints.get("pickup_delivery", base.pickup_delivery)),
    )


def constraint_vector(profile: VRPConstraintProfile) -> tuple[int, int]:
    return (int(profile.open_route), int(profile.time_windows))


def hamming_distance(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    if len(left) != len(right):
        raise ValueError("Constraint vectors must have the same length")
    return sum(1 for a, b in zip(left, right) if a != b)


@dataclass(frozen=True)
class ConstraintDelta:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: dict[str, tuple[object, object]]
    unchanged: tuple[str, ...]


def diff_constraint_profiles(source: VRPConstraintProfile, target: VRPConstraintProfile) -> ConstraintDelta:
    added = []
    removed = []
    changed = {}
    unchanged = []
    for name in ("capacitated", "open_route", "time_windows"):
        source_value = getattr(source, name)
        target_value = getattr(target, name)
        if source_value == target_value:
            unchanged.append(name)
        elif source_value is False and target_value is True:
            added.append(name)
            changed[name] = (source_value, target_value)
        elif source_value is True and target_value is False:
            removed.append(name)
            changed[name] = (source_value, target_value)
        else:
            changed[name] = (source_value, target_value)
    return ConstraintDelta(
        added=tuple(added),
        removed=tuple(removed),
        changed=changed,
        unchanged=tuple(unchanged),
    )
