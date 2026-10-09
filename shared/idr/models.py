from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Optional


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


class NavigationMode(StrEnum):
    GNSS_AIDED = "gnss_aided"
    DEAD_RECKONING = "dead_reckoning"
    INITIALIZING = "initializing"


@dataclass(frozen=True)
class ImuSample:
    """One calibrated sample in the vehicle frame.

    ``forward_acceleration_mps2`` is longitudinal acceleration and
    ``yaw_rate_rps`` is positive for a left turn.
    """

    timestamp_s: float
    forward_acceleration_mps2: float
    yaw_rate_rps: float

    def __post_init__(self) -> None:
        _require_finite("timestamp_s", self.timestamp_s)
        _require_finite("forward_acceleration_mps2", self.forward_acceleration_mps2)
        _require_finite("yaw_rate_rps", self.yaw_rate_rps)


@dataclass(frozen=True)
class GnssFix:
    timestamp_s: float
    latitude_deg: float
    longitude_deg: float
    speed_mps: Optional[float] = None
    horizontal_accuracy_m: Optional[float] = None

    def __post_init__(self) -> None:
        _require_finite("timestamp_s", self.timestamp_s)
        _require_finite("latitude_deg", self.latitude_deg)
        _require_finite("longitude_deg", self.longitude_deg)
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("latitude_deg must be between -90 and 90")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("longitude_deg must be between -180 and 180")
        if self.speed_mps is not None:
            _require_finite("speed_mps", self.speed_mps)
            if self.speed_mps < 0.0:
                raise ValueError("speed_mps must be non-negative")
        if self.horizontal_accuracy_m is not None:
            _require_finite("horizontal_accuracy_m", self.horizontal_accuracy_m)
            if self.horizontal_accuracy_m < 0.0:
                raise ValueError("horizontal_accuracy_m must be non-negative")


@dataclass(frozen=True)
class SensorFrame:
    imu: ImuSample
    gnss: Optional[GnssFix] = None
    truth_x_m: Optional[float] = None
    truth_y_m: Optional[float] = None

    def __post_init__(self) -> None:
        if self.gnss is not None and self.gnss.timestamp_s != self.imu.timestamp_s:
            raise ValueError("GNSS and IMU timestamps must match within a frame")
        for name, value in (("truth_x_m", self.truth_x_m), ("truth_y_m", self.truth_y_m)):
            if value is not None:
                _require_finite(name, value)


@dataclass(frozen=True)
class NavigationState:
    timestamp_s: float
    x_m: float
    y_m: float
    speed_mps: float
    heading_rad: float
    mode: NavigationMode
    confidence: float
    outage_duration_s: float

    def __post_init__(self) -> None:
        for name, value in (
            ("timestamp_s", self.timestamp_s),
            ("x_m", self.x_m),
            ("y_m", self.y_m),
            ("speed_mps", self.speed_mps),
            ("heading_rad", self.heading_rad),
            ("confidence", self.confidence),
            ("outage_duration_s", self.outage_duration_s),
        ):
            _require_finite(name, value)
        if self.speed_mps < 0.0:
            raise ValueError("speed_mps must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.outage_duration_s < 0.0:
            raise ValueError("outage_duration_s must be non-negative")
