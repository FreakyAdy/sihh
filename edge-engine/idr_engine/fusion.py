from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Optional

from idr.models import GnssFix, NavigationMode, NavigationState, SensorFrame
from idr.replay import _project_fix

from .constraints import MapMatcher


@dataclass(frozen=True)
class FusionConfig:
    outage_confirm_s: float = 0.2
    recovery_confirm_count: int = 2
    max_dt_s: float = 1.0
    confidence_decay_s: float = 60.0
    nhc_lateral_velocity_gain: float = 0.15
    map_correction_gain: float = 0.2

    def __post_init__(self) -> None:
        if self.outage_confirm_s < 0.0:
            raise ValueError("outage_confirm_s must be non-negative")
        if self.recovery_confirm_count < 1:
            raise ValueError("recovery_confirm_count must be positive")
        if self.max_dt_s <= 0.0 or self.confidence_decay_s <= 0.0:
            raise ValueError("max_dt_s and confidence_decay_s must be positive")
        if not 0.0 <= self.nhc_lateral_velocity_gain <= 1.0:
            raise ValueError("nhc_lateral_velocity_gain must be between 0 and 1")
        if not 0.0 <= self.map_correction_gain <= 1.0:
            raise ValueError("map_correction_gain must be between 0 and 1")


class FusionEngine:
    """Streaming 2D GNSS/INS baseline with explicit mode hysteresis.

    Inputs are already calibrated into the vehicle frame. The estimator keeps
    the safety-critical propagation classical; learned corrections can be
    supplied by replacing the acceleration and speed inputs at the adapter.
    """

    def __init__(
        self,
        config: FusionConfig | None = None,
        initial_fix: GnssFix | None = None,
        map_matcher: MapMatcher | None = None,
    ) -> None:
        self.config = config or FusionConfig()
        self._map_matcher = map_matcher
        self._origin = initial_fix
        self._x_m = 0.0
        self._y_m = 0.0
        self._speed_mps = initial_fix.speed_mps if initial_fix and initial_fix.speed_mps else 0.0
        self._heading_rad = 0.0
        self._last_timestamp_s: Optional[float] = None
        self._outage_started_s: Optional[float] = None
        self._mode = NavigationMode.INITIALIZING
        self._recovery_count = 0

    def update(self, frame: SensorFrame) -> NavigationState:
        timestamp = frame.imu.timestamp_s
        dt_s = 0.0 if self._last_timestamp_s is None else timestamp - self._last_timestamp_s
        if self._last_timestamp_s is not None and dt_s <= 0.0:
            raise ValueError("timestamps must be strictly increasing")
        if dt_s > self.config.max_dt_s:
            raise ValueError("timestamp gap exceeds fusion limit")
        self._last_timestamp_s = timestamp

        self._propagate(frame, dt_s)
        if frame.gnss is None:
            state = self._handle_missing_gnss(timestamp)
            return self._apply_map_constraint(state)
        return self._handle_gnss(frame.gnss, timestamp)

    def replay(self, frames: Iterable[SensorFrame]) -> list[NavigationState]:
        return [self.update(frame) for frame in frames]

    def _propagate(self, frame: SensorFrame, dt_s: float) -> None:
        self._heading_rad += frame.imu.yaw_rate_rps * dt_s
        self._speed_mps = max(
            0.0,
            self._speed_mps + frame.imu.forward_acceleration_mps2 * dt_s,
        )
        distance_m = self._speed_mps * dt_s
        self._x_m += math.cos(self._heading_rad) * distance_m
        self._y_m += math.sin(self._heading_rad) * distance_m

    def _handle_missing_gnss(self, timestamp_s: float) -> NavigationState:
        if self._origin is None:
            raise ValueError("a GNSS fix is required before inertial propagation")
        self._recovery_count = 0
        if self._outage_started_s is None:
            self._outage_started_s = timestamp_s
        outage_duration = timestamp_s - self._outage_started_s
        if outage_duration >= self.config.outage_confirm_s:
            self._mode = NavigationMode.DEAD_RECKONING
        confidence = max(0.0, 1.0 - outage_duration / self.config.confidence_decay_s)
        return self._state(timestamp_s, confidence, outage_duration)

    def _handle_gnss(self, fix: GnssFix, timestamp_s: float) -> NavigationState:
        if self._origin is None:
            self._origin = fix
        projected_x, projected_y = _project_fix(fix, self._origin)
        self._recovery_count += 1
        if self._mode in (NavigationMode.INITIALIZING, NavigationMode.GNSS_AIDED):
            self._apply_gnss(fix, projected_x, projected_y)
            self._mode = NavigationMode.GNSS_AIDED
        elif self._recovery_count >= self.config.recovery_confirm_count:
            self._apply_gnss(fix, projected_x, projected_y)
            self._mode = NavigationMode.GNSS_AIDED
            self._outage_started_s = None
        confidence = self._gnss_confidence(fix)
        outage_duration = 0.0 if self._outage_started_s is None else timestamp_s - self._outage_started_s
        return self._state(timestamp_s, confidence, outage_duration)

    def _apply_gnss(self, fix: GnssFix, x_m: float, y_m: float) -> None:
        self._x_m = x_m
        self._y_m = y_m
        if fix.speed_mps is not None:
            self._speed_mps = fix.speed_mps

    def _state(self, timestamp_s: float, confidence: float, outage_duration_s: float) -> NavigationState:
        return NavigationState(
            timestamp_s=timestamp_s,
            x_m=self._x_m,
            y_m=self._y_m,
            speed_mps=self._speed_mps,
            heading_rad=self._heading_rad,
            mode=self._mode,
            confidence=confidence,
            outage_duration_s=max(0.0, outage_duration_s),
        )

    def _apply_map_constraint(self, state: NavigationState) -> NavigationState:
        if self._map_matcher is None or state.mode != NavigationMode.DEAD_RECKONING:
            return state
        constraint = self._map_matcher.match(state.x_m, state.y_m, state.heading_rad)
        if constraint is None:
            return state
        from .constraints import blend_map_constraint

        self._x_m, self._y_m, self._heading_rad = blend_map_constraint(
            state.x_m,
            state.y_m,
            state.heading_rad,
            constraint,
            self.config.map_correction_gain,
        )
        return self._state(state.timestamp_s, state.confidence, state.outage_duration_s)

    @staticmethod
    def _gnss_confidence(fix: GnssFix) -> float:
        if fix.horizontal_accuracy_m is None:
            return 1.0
        return max(0.0, min(1.0, 1.0 - fix.horizontal_accuracy_m / 50.0))
