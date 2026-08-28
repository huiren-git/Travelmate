"""依据允许交通方式、距离和时段选择市内出行方式。"""

from __future__ import annotations

from typing import Iterable


def select_local_transport(distance_km: float, allowed_modes: Iterable[str], hour: int | None = None) -> str:
    allowed = list(allowed_modes) or ["walking", "metro", "bus", "taxi"]
    if hour is not None and (hour >= 22 or hour < 6) and "taxi" in allowed:
        return "taxi"
    if distance_km < 1 and "walking" in allowed:
        return "walking"
    if distance_km <= 5:
        for mode in ("metro", "bus", "taxi", "self_driving", "walking"):
            if mode in allowed:
                return mode
    for mode in ("taxi", "self_driving", "metro", "bus", "walking"):
        if mode in allowed:
            return mode
    return allowed[0]
