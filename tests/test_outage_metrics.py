"""Tests for the outage-only drift metric.

These tests verify that pre-outage and post-outage errors do NOT dilute or
distort the drift_percent calculated during the GNSS-denied interval.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from idr.metrics import OutageMetrics, measure_outage
from idr.models import GnssFix, ImuSample, NavigationMode, NavigationState, SensorFrame


def _make_frame(t: float, *, has_gnss: bool = True, truth_x: float | None = None, truth_y: float | None = None) -> SensorFrame:
    return SensorFrame(
        imu=ImuSample(timestamp_s=t, forward_acceleration_mps2=0.0, yaw_rate_rps=0.0),
        gnss=GnssFix(timestamp_s=t, latitude_deg=0.0, longitude_deg=0.0) if has_gnss else None,
        truth_x_m=truth_x,
        truth_y_m=truth_y,
    )


def _make_state(t: float, x: float = 0.0, y: float = 0.0) -> NavigationState:
    return NavigationState(
        timestamp_s=t,
        x_m=x,
        y_m=y,
        speed_mps=0.0,
        heading_rad=0.0,
        mode=NavigationMode.DEAD_RECKONING,
        confidence=1.0,
        outage_duration_s=0.0,
    )


class OutageMetricsWindowTest(unittest.TestCase):
    """Verify that pre/post outage errors do not affect outage drift_percent."""

    def _build_scenario(self) -> tuple[list[SensorFrame], list[NavigationState]]:
        """Scenario:
        t=0–9:   pre-outage (GNSS available, truth on a straight line x=t)
        t=10–19: GNSS denied, estimator drifts — truth_x=t but state_x=0 → big error
        t=20–29: post-outage (GNSS back, position corrected, error ~0)
        """
        frames: list[SensorFrame] = []
        states: list[NavigationState] = []
        for t in range(30):
            in_outage = 10 <= t <= 19
            # Truth follows x=t, y=0 throughout
            frames.append(_make_frame(float(t), has_gnss=not in_outage, truth_x=float(t), truth_y=0.0))
            if in_outage:
                # Estimator stays at x=0 during outage (maximum drift)
                states.append(_make_state(float(t), x=0.0, y=0.0))
            else:
                # Estimator matches truth outside the outage (corrected by GNSS)
                states.append(_make_state(float(t), x=float(t), y=0.0))
        return frames, states

    def test_drift_measured_only_in_outage_window(self) -> None:
        frames, states = self._build_scenario()
        result = measure_outage(frames, states, outage_start_s=10.0, outage_end_s=19.0)
        self.assertIsNotNone(result)
        assert result is not None

        # Outage covers t=10..19, truth x goes 10→19, distance = 9 m
        self.assertAlmostEqual(result.covered_distance_m, 9.0, places=6)

        # At t=10 state_x=0, truth_x=10 → error=10 m (max)
        # At t=19 state_x=0, truth_x=19 → error=19 m is actually the max
        self.assertAlmostEqual(result.max_error_m, 19.0, places=6)

        # drift_percent = 19 / 9 * 100 ≈ 211 % — not diluted by the
        # zero-error pre/post frames
        expected_drift = 19.0 / 9.0 * 100.0
        self.assertAlmostEqual(result.drift_percent, expected_drift, places=4)

    def test_pre_post_errors_not_included(self) -> None:
        """Full-session measure_replay would see near-zero pre/post errors,
        but measure_outage must report only the outage interval."""
        frames, states = self._build_scenario()

        # Validate pre-outage frames have zero error in states
        pre = [(f, s) for f, s in zip(frames, states) if f.imu.timestamp_s < 10]
        for frame, state in pre:
            self.assertAlmostEqual(state.x_m, frame.truth_x_m)

        # measure_outage must not include pre/post frames
        result = measure_outage(frames, states, outage_start_s=10.0, outage_end_s=19.0)
        assert result is not None
        # If full-session errors were used, max_error would be 19 but
        # divided by total distance 29, giving ~65 % — correct value is ~211 %
        self.assertGreater(result.drift_percent, 100.0)

    def test_returns_none_when_no_truth_in_window(self) -> None:
        frames = [_make_frame(float(t), has_gnss=False) for t in range(5)]
        states = [_make_state(float(t)) for t in range(5)]
        result = measure_outage(frames, states, outage_start_s=0.0, outage_end_s=4.0)
        self.assertIsNone(result)

    def test_returns_none_when_window_is_empty(self) -> None:
        frames = [_make_frame(float(t), truth_x=float(t), truth_y=0.0) for t in range(5)]
        states = [_make_state(float(t)) for t in range(5)]
        # Outage window starts after all frames
        result = measure_outage(frames, states, outage_start_s=100.0, outage_end_s=200.0)
        self.assertIsNone(result)

    def test_returns_none_when_distance_is_zero(self) -> None:
        """Stationary vehicle: all truth coordinates the same → distance = 0."""
        frames = [_make_frame(float(t), has_gnss=False, truth_x=5.0, truth_y=5.0) for t in range(5)]
        states = [_make_state(float(t), x=0.0, y=0.0) for t in range(5)]
        result = measure_outage(frames, states, outage_start_s=0.0, outage_end_s=4.0)
        self.assertIsNone(result)

    def test_truth_coverage_fraction(self) -> None:
        """Half the outage frames have truth labels; coverage should be 0.5."""
        frames: list[SensorFrame] = []
        states: list[NavigationState] = []
        for t in range(10):
            has_truth = t % 2 == 0
            frames.append(_make_frame(
                float(t), has_gnss=False,
                truth_x=float(t) if has_truth else None,
                truth_y=0.0 if has_truth else None,
            ))
            states.append(_make_state(float(t), x=0.0, y=0.0))
        result = measure_outage(frames, states, outage_start_s=0.0, outage_end_s=9.0)
        # Only even-indexed frames have truth (0,2,4,6,8 → 5 out of 10)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result.truth_coverage_fraction, 0.5, places=6)

    def test_meets_drift_target(self) -> None:
        """drift_percent < 10 should set meets_drift_target = True."""
        # Straight 100 m path, DR error = 5 m → 5 %
        frames = [_make_frame(float(t), has_gnss=False, truth_x=float(t) * 10.0, truth_y=0.0) for t in range(11)]
        states = [_make_state(float(t), x=float(t) * 10.0 - 5.0, y=0.0) for t in range(11)]
        result = measure_outage(frames, states, outage_start_s=0.0, outage_end_s=10.0)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.meets_drift_target)

    def test_length_mismatch_raises(self) -> None:
        frames = [_make_frame(0.0, truth_x=0.0, truth_y=0.0)]
        states = [_make_state(0.0), _make_state(1.0)]
        with self.assertRaises(ValueError):
            measure_outage(frames, states, outage_start_s=0.0, outage_end_s=1.0)


if __name__ == "__main__":
    unittest.main()
