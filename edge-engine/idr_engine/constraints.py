from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, sin
from typing import Protocol


@dataclass(frozen=True)
class MapConstraint:
    """A bounded road-network correction in the local ENU frame."""

    x_m: float
    y_m: float
    heading_rad: float | None = None
    confidence: float = 1.0


class MapMatcher(Protocol):
    def match(self, x_m: float, y_m: float, heading_rad: float) -> MapConstraint | None:
        """Return a candidate road correction or None when no map match exists."""


class NoOpMapMatcher:
    def match(self, x_m: float, y_m: float, heading_rad: float) -> None:
        return None


def blend_map_constraint(
    x_m: float,
    y_m: float,
    heading_rad: float,
    constraint: MapConstraint,
    gain: float,
) -> tuple[float, float, float]:
    if not 0.0 <= gain <= 1.0:
        raise ValueError("map correction gain must be between 0 and 1")
    confidence = max(0.0, min(1.0, constraint.confidence))
    effective_gain = gain * confidence
    corrected_x = x_m + (constraint.x_m - x_m) * effective_gain
    corrected_y = y_m + (constraint.y_m - y_m) * effective_gain
    if constraint.heading_rad is None:
        corrected_heading = heading_rad
    else:
        delta = atan2(sin(constraint.heading_rad - heading_rad), cos(constraint.heading_rad - heading_rad))
        corrected_heading = heading_rad + delta * effective_gain
    return corrected_x, corrected_y, corrected_heading
