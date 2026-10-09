"""Tests for heading initialization from GNSS data.

Verifies that the fusion engine correctly determines travel direction before
a GNSS outage instead of defaulting to east (heading_rad = 0).
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "edge-engine"))

from idr.models import GnssFix, ImuSample, NavigationMode, SensorFrame
from idr_engine import FusionConfig, FusionEngine

# Approximate degrees-per-metre for lat/lon at equator
_DEG_PER_M_LAT = 1.0 / 111_320.0
_DEG_PER_M_LON = 1.0 / 111_320.0  # close enough at equator for small distances


def _gnss_frame(t: float, lat: float, lon: float, *, speed: float = 10.0, bearing: float | None = None) -> SensorFrame:
    return SensorFrame(
        imu=ImuSample(timestamp_s=t, forward_acceleration_mps2=0.0, yaw_rate_rps=0.0),
        gnss=GnssFix(
            timestamp_s=t,
            latitude_deg=lat,
            longitude_deg=lon,
            speed_mps=speed,
            bearing_deg=bearing,
        ),
    )


def _imu_frame(t: float) -> SensorFrame:
    return SensorFrame(
        imu=ImuSample(timestamp_s=t, forward_acceleration_mps2=0.0, yaw_rate_rps=0.0),
        gnss=None,
    )


def _run_engine(frames: list[SensorFrame]) -> list[object]:
    engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
    return [engine.update(f) for f in frames]


class HeadingFromBearingFieldTest(unittest.TestCase):
    """Heading should use bearing_deg from the GNSS fix when supplied."""

    def test_northbound_bearing_sets_correct_heading(self) -> None:
        # bearing_deg=0 means north; in east/north math that's π/2 (90°)
        frames = [
            _gnss_frame(0.0, 0.0, 0.0, bearing=0.0),
            _gnss_frame(0.1, _DEG_PER_M_LAT * 1.0, 0.0, bearing=0.0),
            _imu_frame(0.2),
        ]
        engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
        for f in frames:
            engine.update(f)
        self.assertAlmostEqual(engine._heading_rad, math.pi / 2.0, places=6)
        self.assertTrue(engine._heading_initialized)

    def test_eastbound_bearing_sets_correct_heading(self) -> None:
        # bearing_deg=90 means east; in east/north math that's 0 (0°)
        frames = [_gnss_frame(0.0, 0.0, 0.0, bearing=90.0)]
        engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
        engine.update(frames[0])
        self.assertAlmostEqual(engine._heading_rad, 0.0, places=6)

    def test_westbound_bearing_sets_correct_heading(self) -> None:
        # bearing_deg=270 means west; in east/north math that's ±π (180°)
        # math.atan2(0, -1) returns -π, which is equivalent to +π
        frames = [_gnss_frame(0.0, 0.0, 0.0, bearing=270.0)]
        engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
        engine.update(frames[0])
        # Both -π and +π represent due-west; accept either
        self.assertAlmostEqual(abs(engine._heading_rad), math.pi, places=6)

    def test_southbound_bearing_sets_correct_heading(self) -> None:
        # bearing_deg=180 means south; in east/north math that's -π/2
        frames = [_gnss_frame(0.0, 0.0, 0.0, bearing=180.0)]
        engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
        engine.update(frames[0])
        expected = math.radians(90.0 - 180.0)  # = -π/2
        self.assertAlmostEqual(engine._heading_rad, expected, places=6)


class HeadingFromSeparatedFixesTest(unittest.TestCase):
    """When bearing_deg is absent, heading is inferred from two fixes >= 5 m apart."""

    def test_northbound_fixes_produce_north_heading(self) -> None:
        # Two fixes 10 m apart in the northward (lat+) direction, no bearing field
        lat_step = _DEG_PER_M_LAT * 10.0
        frames = [
            _gnss_frame(0.0, 0.0, 0.0),
            _gnss_frame(1.0, lat_step, 0.0),
        ]
        engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
        for f in frames:
            engine.update(f)
        self.assertTrue(engine._heading_initialized)
        # North in east/north frame = π/2
        self.assertAlmostEqual(engine._heading_rad, math.pi / 2.0, places=2)

    def test_eastbound_fixes_produce_east_heading(self) -> None:
        lon_step = _DEG_PER_M_LON * 10.0
        frames = [
            _gnss_frame(0.0, 0.0, 0.0),
            _gnss_frame(1.0, 0.0, lon_step),
        ]
        engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
        for f in frames:
            engine.update(f)
        self.assertTrue(engine._heading_initialized)
        self.assertAlmostEqual(engine._heading_rad, 0.0, places=2)

    def test_fixes_under_5m_do_not_initialize_heading(self) -> None:
        # Only 1 m separation — not reliable enough
        lat_step = _DEG_PER_M_LAT * 1.0
        frames = [
            _gnss_frame(0.0, 0.0, 0.0),
            _gnss_frame(1.0, lat_step, 0.0),
        ]
        engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
        for f in frames:
            engine.update(f)
        self.assertFalse(engine._heading_initialized)
        # Heading should remain 0.0 (default east) until initialized
        self.assertAlmostEqual(engine._heading_rad, 0.0, places=6)


class OutageAfterHeadingInitTest(unittest.TestCase):
    """DR propagation must use the initialized heading, not the 0.0 default."""

    def test_northbound_dr_propagates_north(self) -> None:
        """After traveling north under GNSS, DR should continue north (y increases)."""
        lat_step = _DEG_PER_M_LAT * 10.0
        frames: list[SensorFrame] = [
            _gnss_frame(0.0, 0.0, 0.0, speed=10.0, bearing=0.0),  # north at 10 m/s
            _gnss_frame(0.5, lat_step / 2, 0.0, speed=10.0, bearing=0.0),
        ]
        # Add DR frames at 0.9 s intervals to stay within max_dt_s=1.0
        for step in range(1, 4):
            frames.append(SensorFrame(
                imu=ImuSample(
                    timestamp_s=0.5 + step * 0.9,
                    forward_acceleration_mps2=0.0,
                    yaw_rate_rps=0.0,
                ),
                gnss=None,
            ))

        engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
        states = [engine.update(f) for f in frames]
        # During the DR phase (last 3 states), y should increase (northward)
        dr_states = [s for s in states if s.mode == NavigationMode.DEAD_RECKONING]
        self.assertTrue(len(dr_states) >= 2, "Expected at least two DR states")
        # y_m must be positive (north) and growing
        y_values = [s.y_m for s in dr_states]
        self.assertTrue(all(y > 0 for y in y_values), f"Expected northward y values, got {y_values}")
        self.assertGreater(y_values[-1], y_values[0])

    def test_default_heading_used_before_initialization(self) -> None:
        """Before initialization heading=0.0 (east) so x increases during DR."""
        # Single GNSS fix that is too close to a second one to init heading
        lat_step = _DEG_PER_M_LAT * 1.0  # only 1 m — not enough
        frames: list[SensorFrame] = [
            _gnss_frame(0.0, 0.0, 0.0, speed=10.0),
            _gnss_frame(1.0, lat_step, 0.0, speed=10.0),
            # Now outage while heading is still uninitialized (0 = east)
            _imu_frame(2.0),
            _imu_frame(3.0),
        ]
        engine = FusionEngine(FusionConfig(outage_confirm_s=0.05))
        states = [engine.update(f) for f in frames]
        dr_states = [s for s in states if s.mode == NavigationMode.DEAD_RECKONING]
        if dr_states:
            # Heading = east → x should increase, y should stay ~0
            last = dr_states[-1]
            self.assertGreaterEqual(last.x_m, 0.0)


if __name__ == "__main__":
    unittest.main()
