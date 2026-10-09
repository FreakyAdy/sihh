import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "shared"))
sys.path.insert(0, str(Path(__file__).parents[1] / "edge-engine"))

from idr.models import GnssFix, ImuSample, NavigationMode, SensorFrame
from idr.synthetic import METERS_PER_DEGREE
from idr_engine import (
    FusionConfig,
    FusionCorrection,
    FusionEngine,
    LinearFusionCorrection,
    MapConstraint,
    RoadSegment,
    SegmentMapMatcher,
    HmmMapMatcher,
    frame_from_external,
)


class FusionTests(unittest.TestCase):
    def test_outage_hysteresis_and_recovery(self) -> None:
        def frame(timestamp: float, gnss: bool) -> SensorFrame:
            fix = (
                GnssFix(timestamp, 0.0, timestamp * 10.0 / METERS_PER_DEGREE, speed_mps=10.0)
                if gnss
                else None
            )
            return SensorFrame(ImuSample(timestamp, 0.0, 0.0), fix)

        engine = FusionEngine(FusionConfig(outage_confirm_s=1.0, recovery_confirm_count=2))
        self.assertEqual(engine.update(frame(0.0, True)).mode, NavigationMode.GNSS_AIDED)
        self.assertEqual(engine.update(frame(1.0, False)).mode, NavigationMode.GNSS_AIDED)
        self.assertEqual(engine.update(frame(2.0, False)).mode, NavigationMode.DEAD_RECKONING)
        self.assertEqual(engine.update(frame(3.0, True)).mode, NavigationMode.DEAD_RECKONING)
        self.assertEqual(engine.update(frame(4.0, True)).mode, NavigationMode.GNSS_AIDED)

    def test_requires_gnss_initialization(self) -> None:
        engine = FusionEngine()
        with self.assertRaises(ValueError):
            engine.update(SensorFrame(ImuSample(0.0, 0.0, 0.0)))

    def test_rejects_large_timestamp_gap(self) -> None:
        engine = FusionEngine()
        engine.update(
            SensorFrame(ImuSample(0.0, 0.0, 0.0), GnssFix(0.0, 0.0, 0.0, speed_mps=1.0))
        )
        with self.assertRaises(ValueError):
            engine.update(
                SensorFrame(ImuSample(2.0, 0.0, 0.0), GnssFix(2.0, 0.0, 0.0, speed_mps=1.0))
            )

    def test_map_constraint_is_bounded_during_outage(self) -> None:
        class Matcher:
            def match(self, x_m: float, y_m: float, heading_rad: float) -> MapConstraint:
                return MapConstraint(0.0, 0.0, confidence=1.0)

        engine = FusionEngine(
            FusionConfig(outage_confirm_s=0.0, map_correction_gain=0.5),
            map_matcher=Matcher(),
        )
        engine.update(
            SensorFrame(ImuSample(0.0, 0.0, 0.0), GnssFix(0.0, 0.0, 0.0, speed_mps=10.0))
        )
        state = engine.update(SensorFrame(ImuSample(1.0, 0.0, 0.0)))
        self.assertEqual(state.mode, NavigationMode.DEAD_RECKONING)
        self.assertAlmostEqual(state.x_m, 5.0)

    def test_external_adapter_builds_shared_frame(self) -> None:
        frame = frame_from_external(
            {
                "timestamp_s": 1.0,
                "forward_acceleration_mps2": 0.2,
                "yaw_rate_rps": 0.01,
                "gnss": {"latitude_deg": 28.0, "longitude_deg": 77.0, "speed_mps": 4.0},
            }
        )
        self.assertEqual(frame.imu.timestamp_s, 1.0)
        self.assertEqual(frame.gnss.speed_mps, 4.0)

    def test_correction_model_changes_inertial_propagation(self) -> None:
        frame = SensorFrame(
            ImuSample(0.0, 0.0, 0.0),
            GnssFix(0.0, 0.0, 0.0, speed_mps=2.0),
        )
        corrected = FusionEngine(
            correction_model=LinearFusionCorrection(
                acceleration_scale_bias=0.0,
                yaw_bias_weight=0.5,
                gnss_gain=0.5,
            )
        )
        corrected.update(frame)
        corrected.update(SensorFrame(ImuSample(0.5, 2.0, 0.0), None))
        state = corrected.update(SensorFrame(ImuSample(1.0, 2.0, 0.0), None))
        self.assertEqual(state.mode, NavigationMode.DEAD_RECKONING)
        self.assertAlmostEqual(state.speed_mps, 2.0)

    def test_correction_bounds_are_explicit(self) -> None:
        with self.assertRaises(ValueError):
            FusionCorrection(acceleration_scale=3.0)

    def test_segment_matcher_projects_to_heading_compatible_road(self) -> None:
        matcher = SegmentMapMatcher(
            [RoadSegment(0.0, 0.0, 100.0, 0.0, road_id="east-west")],
            max_distance_m=10.0,
        )
        match = matcher.match(40.0, 6.0, 0.0)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertAlmostEqual(match.x_m, 40.0)
        self.assertAlmostEqual(match.y_m, 0.0)
        self.assertGreater(match.confidence, 0.3)

    def test_segment_matcher_rejects_wrong_heading(self) -> None:
        matcher = SegmentMapMatcher(
            [RoadSegment(0.0, 0.0, 100.0, 0.0)],
            max_distance_m=10.0,
            max_heading_error_rad=0.2,
        )
        self.assertIsNone(matcher.match(40.0, 2.0, 1.57))

    def test_hmm_matcher_uses_connected_segment_sequence(self) -> None:
        matcher = HmmMapMatcher(
            [
                RoadSegment(0.0, 0.0, 10.0, 0.0),
                RoadSegment(10.0, 0.0, 20.0, 0.0),
            ],
            {0: (0, 1), 1: (1,)},
        )
        matches = matcher.match_sequence([(4.0, 1.0, 0.0), (14.0, -1.0, 0.0)])
        self.assertEqual(len(matches), 2)
        self.assertAlmostEqual(matches[0].x_m, 4.0)  # type: ignore[union-attr]
        self.assertAlmostEqual(matches[1].x_m, 14.0)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
