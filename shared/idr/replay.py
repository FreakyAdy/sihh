from __future__ import annotations

import math
from typing import Iterable, Optional

from .models import GnssFix, NavigationMode, NavigationState, SensorFrame


EARTH_RADIUS_M = 6_378_137.0


def _project_fix(fix: GnssFix, origin: GnssFix) -> tuple[float, float]:
    """Project latitude/longitude to a local east/north tangent plane."""

    latitude_scale = math.pi * EARTH_RADIUS_M / 180.0
    longitude_scale = latitude_scale * math.cos(math.radians(origin.latitude_deg))
    return (
        (fix.longitude_deg - origin.longitude_deg) * longitude_scale,
        (fix.latitude_deg - origin.latitude_deg) * latitude_scale,
    )


class DeadReckoningReplay:
    """Deterministic baseline replay engine.

    This is intentionally a classical baseline, not the final learned model.
    It provides a stable contract and measurable reference for later fusion work.
    """

    def __init__(self, initial_fix: Optional[GnssFix] = None) -> None:
        self._origin = initial_fix
        self._x_m = 0.0
        self._y_m = 0.0
        self._speed_mps = initial_fix.speed_mps if initial_fix and initial_fix.speed_mps else 0.0
        self._heading_rad = 0.0
        self._last_timestamp_s: Optional[float] = None
        self._outage_started_s: Optional[float] = None

    def update(self, frame: SensorFrame) -> NavigationState:
        imu = frame.imu
        if self._last_timestamp_s is None:
            dt_s = 0.0
        else:
            dt_s = imu.timestamp_s - self._last_timestamp_s
            if dt_s <= 0.0:
                raise ValueError("IMU timestamps must be strictly increasing")
            if dt_s > 1.0:
                raise ValueError("IMU timestamp gap exceeds the 1 second replay limit")
        self._last_timestamp_s = imu.timestamp_s

        if frame.gnss is not None:
            if self._origin is None:
                self._origin = frame.gnss
            self._x_m, self._y_m = _project_fix(frame.gnss, self._origin)
            if frame.gnss.speed_mps is not None:
                self._speed_mps = max(0.0, frame.gnss.speed_mps)
            self._outage_started_s = None
            mode = NavigationMode.GNSS_AIDED
            confidence = self._gnss_confidence(frame.gnss)
        else:
            if self._origin is None:
                raise ValueError("The first frame must contain a GNSS fix")
            self._heading_rad += imu.yaw_rate_rps * dt_s
            self._speed_mps = max(0.0, self._speed_mps + imu.forward_acceleration_mps2 * dt_s)
            distance_m = self._speed_mps * dt_s
            self._x_m += math.cos(self._heading_rad) * distance_m
            self._y_m += math.sin(self._heading_rad) * distance_m
            if self._outage_started_s is None:
                self._outage_started_s = imu.timestamp_s
            mode = NavigationMode.DEAD_RECKONING
            confidence = max(0.0, 1.0 - self.outage_duration_s / 60.0)

        return NavigationState(
            timestamp_s=imu.timestamp_s,
            x_m=self._x_m,
            y_m=self._y_m,
            speed_mps=self._speed_mps,
            heading_rad=self._heading_rad,
            mode=mode,
            confidence=confidence,
            outage_duration_s=self.outage_duration_s,
        )

    @property
    def outage_duration_s(self) -> float:
        if self._outage_started_s is None or self._last_timestamp_s is None:
            return 0.0
        return self._last_timestamp_s - self._outage_started_s

    @staticmethod
    def _gnss_confidence(fix: GnssFix) -> float:
        if fix.horizontal_accuracy_m is None:
            return 1.0
        return max(0.0, min(1.0, 1.0 - fix.horizontal_accuracy_m / 50.0))

    def replay(self, frames: Iterable[SensorFrame]) -> list[NavigationState]:
        return [self.update(frame) for frame in frames]
