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
    StreamingHmmMatcher,
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
            FusionConfig(outage_confirm_s=0.2),
            correction_model=LinearFusionCorrection(
                acceleration_scale_bias=0.0,
                yaw_bias_weight=0.5,
                gnss_gain=0.5,
            ),
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

    def test_zupt_clamps_stationary_drift(self) -> None:
        engine = FusionEngine()
        # Initialize at 0 speed
        engine.update(SensorFrame(ImuSample(0.0, 0.0, 0.0), GnssFix(0.0, 0.0, 0.0, speed_mps=0.0)))
        # Vehicle is idling at standstill; small accelerometer noise
        for step in range(1, 10):
            state = engine.update(SensorFrame(ImuSample(step * 0.1, 0.05, 0.001)))
            self.assertEqual(state.speed_mps, 0.0)
            self.assertEqual(state.x_m, 0.0)

    def test_speed_override_correction_blends_into_state(self) -> None:
        class SpeedModelCorrection:
            def predict(self, frame: SensorFrame) -> FusionCorrection:
                return FusionCorrection(speed_override_mps=10.0)

        engine = FusionEngine(
            FusionConfig(outage_confirm_s=0.0),
            correction_model=SpeedModelCorrection(),
        )
        engine.update(SensorFrame(ImuSample(0.0, 0.0, 0.0), GnssFix(0.0, 0.0, 0.0, speed_mps=0.0)))
        state = engine.update(SensorFrame(ImuSample(0.5, 0.0, 0.0)))
        self.assertGreater(state.speed_mps, 0.0)
        self.assertLessEqual(state.speed_mps, 10.0)

    def test_1hz_gnss_with_10hz_imu_no_flapping(self) -> None:
        """Verify 1 Hz GNSS with 10 Hz IMU stays in GNSS_AIDED and recovers cleanly."""
        frames = []
        for i in range(101):
            t = round(i * 0.1, 2)
            x = 10.0 * t
            gnss = None
            if i % 10 == 0:
                gnss = GnssFix(t, 0.0, x / METERS_PER_DEGREE, speed_mps=10.0, bearing_deg=90.0)
            frames.append(SensorFrame(ImuSample(t, 0.0, 0.0), gnss, truth_x_m=x, truth_y_m=0.0))

        engine = FusionEngine()
        states = engine.replay(frames)
        modes = [s.mode for s in states]
        # After initial fix, no flapping to DEAD_RECKONING should occur
        self.assertTrue(all(m == NavigationMode.GNSS_AIDED for m in modes[1:]))

    def test_streaming_hmm_matcher(self) -> None:
        """Verify StreamingHmmMatcher buffers observations and snaps to road segments."""
        segments = [
            RoadSegment(0.0, 0.0, 50.0, 0.0),
            RoadSegment(50.0, 0.0, 100.0, 0.0),
        ]
        connectivity = {0: (0, 1), 1: (1,)}
        hmm = HmmMapMatcher(segments, connectivity)
        matcher = StreamingHmmMatcher(hmm, window=10, min_window=3)

        # Before min_window samples, returns None
        self.assertIsNone(matcher.match(10.0, 2.0, 0.0))
        self.assertIsNone(matcher.match(20.0, 2.0, 0.0))

        # At sample 3+, snaps to the road segment (y=0.0)
        constraint = matcher.match(30.0, 2.0, 0.0)
        self.assertIsNotNone(constraint)
        self.assertAlmostEqual(constraint.y_m, 0.0, places=3)  # type: ignore[union-attr]
        self.assertAlmostEqual(constraint.x_m, 30.0, places=3)  # type: ignore[union-attr]

    def test_continuous_heading_correction(self) -> None:
        """Verify heading smoothly tracks GNSS course-over-ground updates."""
        engine = FusionEngine()
        # Initialize heading east (90 deg compass = 0.0 rad math angle)
        engine.update(
            SensorFrame(
                ImuSample(0.0, 0.0, 0.0),
                GnssFix(0.0, 0.0, 0.0, speed_mps=10.0, bearing_deg=90.0),
            )
        )
        self.assertAlmostEqual(engine._heading_rad, 0.0, places=5)

        # Receive GNSS bearing pointing north (0 deg compass = pi/2 rad math angle)
        engine.update(
            SensorFrame(
                ImuSample(1.0, 0.0, 0.0),
                GnssFix(1.0, 0.0, 0.0001, speed_mps=10.0, bearing_deg=0.0),
            )
        )
        # Heading should have smoothly rotated toward north (> 0.0)
        self.assertGreater(engine._heading_rad, 0.1)


if __name__ == "__main__":
    unittest.main()
