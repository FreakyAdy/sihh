from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Optional, Protocol

from idr.models import GnssFix, NavigationMode, NavigationState, SensorFrame
from idr.replay import _project_fix

from .constraints import MapMatcher


@dataclass(frozen=True)
class FusionCorrection:
    """Bounded learned correction applied inside the classical filter."""

    acceleration_scale: float = 1.0
    yaw_rate_bias_rps: float = 0.0
    gnss_gain: float = 1.0
    speed_override_mps: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.acceleration_scale <= 2.0:
            raise ValueError("acceleration_scale must be between 0 and 2")
        if not math.isfinite(self.yaw_rate_bias_rps):
            raise ValueError("yaw_rate_bias_rps must be finite")
        if not 0.0 < self.gnss_gain <= 1.0:
            raise ValueError("gnss_gain must be in (0, 1]")
        if self.speed_override_mps is not None:
            if not math.isfinite(self.speed_override_mps) or self.speed_override_mps < 0.0:
                raise ValueError("speed_override_mps must be non-negative and finite")


class FusionCorrectionModel(Protocol):
    def predict(self, frame: SensorFrame) -> FusionCorrection:
        """Predict bounded propagation and GNSS correction terms."""


class NoOpFusionCorrection:
    def predict(self, frame: SensorFrame) -> FusionCorrection:
        return FusionCorrection()


class LinearFusionCorrection:
    """Transparent adaptive correction baseline for future learned weights."""

    def __init__(
        self,
        acceleration_scale_bias: float = 1.0,
        acceleration_scale_abs_accel_weight: float = 0.0,
        yaw_bias_weight: float = 0.0,
        gnss_gain: float = 1.0,
    ) -> None:
        self._acceleration_scale_bias = acceleration_scale_bias
        self._acceleration_scale_abs_accel_weight = acceleration_scale_abs_accel_weight
        self._yaw_bias_weight = yaw_bias_weight
        self._gnss_gain = gnss_gain

    def predict(self, frame: SensorFrame) -> FusionCorrection:
        acceleration = frame.imu.forward_acceleration_mps2
        scale = self._acceleration_scale_bias + (
            self._acceleration_scale_abs_accel_weight * abs(acceleration)
        )
        return FusionCorrection(
            acceleration_scale=max(0.0, min(2.0, scale)),
            yaw_rate_bias_rps=max(-1.0, min(1.0, self._yaw_bias_weight * acceleration)),
            gnss_gain=max(0.01, min(1.0, self._gnss_gain)),
        )


@dataclass(frozen=True)
class FusionConfig:
    outage_confirm_s: float = 1.5
    recovery_confirm_count: int = 2
    max_dt_s: float = 1.0
    confidence_decay_s: float = 60.0
    nhc_lateral_velocity_gain: float = 0.15  # Non-holonomic lateral velocity constraint damping gain
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
        correction_model: FusionCorrectionModel | None = None,
    ) -> None:
        self.config = config or FusionConfig()
        self._map_matcher = map_matcher
        self._correction_model = correction_model or NoOpFusionCorrection()
        self._origin = initial_fix
        self._x_m = 0.0
        self._y_m = 0.0
        self._speed_mps = initial_fix.speed_mps if initial_fix and initial_fix.speed_mps else 0.0
        self._heading_rad = 0.0
        self._heading_initialized = False
        self._gyro_bias_rps = 0.0
        # Stores (x_m, y_m) from successive GNSS fixes for bearing inference
        # when the receiver does not supply a course-over-ground field.
        self._gnss_history: list[tuple[float, float]] = []
        self._last_timestamp_s: Optional[float] = None
        self._last_gnss_timestamp_s: Optional[float] = None
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

        correction = self._correction_model.predict(frame)
        self._propagate(frame, dt_s, correction)
        if frame.gnss is None:
            state = self._handle_missing_gnss(timestamp)
            return self._apply_map_constraint(state)
        return self._handle_gnss(frame.gnss, timestamp, correction)

    def replay(self, frames: Iterable[SensorFrame]) -> list[NavigationState]:
        return [self.update(frame) for frame in frames]

    def _propagate(
        self,
        frame: SensorFrame,
        dt_s: float,
        correction: FusionCorrection,
    ) -> None:
        effective_yaw_rate = (
            frame.imu.yaw_rate_rps
            - correction.yaw_rate_bias_rps
            - self._gyro_bias_rps
        )
        self._heading_rad += effective_yaw_rate * dt_s
        self._speed_mps = max(
            0.0,
            self._speed_mps
            + frame.imu.forward_acceleration_mps2
            * correction.acceleration_scale
            * dt_s,
        )
        if correction.speed_override_mps is not None:
            self._speed_mps = max(0.0, self._speed_mps * 0.8 + correction.speed_override_mps * 0.2)
        if (
            self._speed_mps < 0.3
            and abs(frame.imu.forward_acceleration_mps2) < 0.15
            and abs(frame.imu.yaw_rate_rps) < 0.05
        ):
            self._speed_mps = 0.0
        distance_m = self._speed_mps * dt_s
        self._x_m += math.cos(self._heading_rad) * distance_m
        self._y_m += math.sin(self._heading_rad) * distance_m

    def _handle_missing_gnss(self, timestamp_s: float) -> NavigationState:
        if self._origin is None:
            raise ValueError("a GNSS fix is required before inertial propagation")
        # Only reset recovery counter if GNSS has been missing longer than expected recovery interval
        if self._last_gnss_timestamp_s is not None and (
            timestamp_s - self._last_gnss_timestamp_s >= max(self.config.outage_confirm_s * 2.0, 2.5)
        ):
            self._recovery_count = 0

        if self._outage_started_s is None:
            self._outage_started_s = timestamp_s
        outage_duration = timestamp_s - self._outage_started_s
        if outage_duration >= self.config.outage_confirm_s:
            self._mode = NavigationMode.DEAD_RECKONING
        confidence = max(0.0, 1.0 - outage_duration / self.config.confidence_decay_s)
        return self._state(timestamp_s, confidence, outage_duration)

    def _handle_gnss(
        self,
        fix: GnssFix,
        timestamp_s: float,
        correction: FusionCorrection,
    ) -> NavigationState:
        initializing = self._origin is None
        if self._origin is None:
            self._origin = fix
        self._last_gnss_timestamp_s = timestamp_s
        projected_x, projected_y = _project_fix(fix, self._origin)
        self._recovery_count += 1
        if self._mode in (NavigationMode.INITIALIZING, NavigationMode.GNSS_AIDED):
            self._apply_gnss(
                fix,
                projected_x,
                projected_y,
                1.0 if initializing else correction.gnss_gain,
            )
            self._mode = NavigationMode.GNSS_AIDED
            self._outage_started_s = None
            self._recovery_count = 0
        elif self._recovery_count >= self.config.recovery_confirm_count:
            recovery_gain = min(1.0, max(0.2, correction.gnss_gain))
            self._apply_gnss(fix, projected_x, projected_y, recovery_gain)
            self._mode = NavigationMode.GNSS_AIDED
            self._outage_started_s = None
            self._recovery_count = 0

        # --- Continuous heading tracking and gyro bias estimation from GNSS ---
        # Priority 1: receiver-supplied course-over-ground
        # Priority 2: inferred from two fixes at least 5 m apart
        if fix.bearing_deg is not None:
            target_heading = math.radians(90.0 - fix.bearing_deg)
            if not self._heading_initialized:
                self._heading_rad = target_heading
                self._heading_initialized = True
            elif fix.speed_mps is not None and fix.speed_mps >= 2.5:
                heading_err = math.atan2(
                    math.sin(target_heading - self._heading_rad),
                    math.cos(target_heading - self._heading_rad),
                )
                self._heading_rad += heading_err * 0.15
                if abs(heading_err) < 0.2:
                    self._gyro_bias_rps = max(-0.05, min(0.05, self._gyro_bias_rps - heading_err * 0.01))
        else:
            self._gnss_history.append((projected_x, projected_y))
            if len(self._gnss_history) >= 2:
                dx = self._gnss_history[-1][0] - self._gnss_history[-2][0]
                dy = self._gnss_history[-1][1] - self._gnss_history[-2][1]
                separation = math.hypot(dx, dy)
                if separation >= 5.0:
                    inferred_heading = math.atan2(dy, dx)
                    if not self._heading_initialized:
                        self._heading_rad = inferred_heading
                        self._heading_initialized = True
                    elif fix.speed_mps is not None and fix.speed_mps >= 2.5:
                        heading_err = math.atan2(
                            math.sin(inferred_heading - self._heading_rad),
                            math.cos(inferred_heading - self._heading_rad),
                        )
                        self._heading_rad += heading_err * 0.10
                        if abs(heading_err) < 0.2:
                            self._gyro_bias_rps = max(-0.05, min(0.05, self._gyro_bias_rps - heading_err * 0.01))
            if len(self._gnss_history) > 10:
                self._gnss_history = self._gnss_history[-5:]

        confidence = self._gnss_confidence(fix)
        outage_duration = 0.0 if self._outage_started_s is None else timestamp_s - self._outage_started_s
        return self._state(timestamp_s, confidence, outage_duration)

    def _apply_gnss(
        self,
        fix: GnssFix,
        x_m: float,
        y_m: float,
        gain: float,
    ) -> None:
        self._x_m += (x_m - self._x_m) * gain
        self._y_m += (y_m - self._y_m) * gain
        if fix.speed_mps is not None:
            self._speed_mps += (fix.speed_mps - self._speed_mps) * gain

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
