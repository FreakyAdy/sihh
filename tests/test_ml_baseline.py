import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "shared"))
sys.path.insert(0, str(Path(__file__).parents[1] / "ml"))

from idr.models import GnssFix, ImuSample, SensorFrame
from idr.synthetic import straight_line_trace
from idr_ml.baseline import estimate_forward_speed
from idr_ml.dataset import SessionTrace, split_sessions
from idr_ml.io_vnbd import ColumnMap, read_csv_sessions
from idr_ml.model import SpeedCorrectionModel, train_speed_model
from idr_ml.quality import QualityFlag, assess_quality
from idr_ml.temporal_model import TemporalSpeedModel, train_temporal_speed_model


class MlBaselineTests(unittest.TestCase):
    def test_session_split_is_deterministic_and_leakage_safe(self) -> None:
        sessions = [
            SessionTrace(str(index), tuple(straight_line_trace(sample_count=2)))
            for index in range(10)
        ]
        first = split_sessions(sessions, seed=7)
        second = split_sessions(sessions, seed=7)
        self.assertEqual(
            [[session.session_id for session in group] for group in first],
            [[session.session_id for session in group] for group in second],
        )
        self.assertEqual(sum(len(group) for group in first), len(sessions))
        self.assertEqual(
            len(set.intersection(*(set(session.session_id for session in group) for group in first))),
            0,
        )

    def test_quality_flags_detect_shock_and_gap(self) -> None:
        samples = [
            ImuSample(0.0, 0.0, 0.0),
            ImuSample(0.1, 20.0, 0.0),
            ImuSample(0.5, 0.0, 0.0),
        ]
        reports = assess_quality(samples)
        self.assertIn(QualityFlag.HIGH_ACCELERATION, reports[1].flags)
        self.assertIn(QualityFlag.TIMESTAMP_GAP, reports[2].flags)

    def test_speed_baseline_uses_gnss_anchor_and_imu_outage(self) -> None:
        frames = []
        for index in range(5):
            timestamp = float(index)
            gnss = GnssFix(timestamp, 0.0, 0.0, speed_mps=10.0) if index == 0 else None
            frames.append(SensorFrame(ImuSample(timestamp, 0.0, 0.0), gnss))
        output = estimate_forward_speed(frames, smoothing_window=3)
        self.assertEqual(output.used_gnss_count, 1)
        self.assertEqual(output.speeds_mps, (10.0, 10.0, 10.0, 10.0, 10.0))

    def test_csv_adapter_groups_sessions_with_explicit_mapping(self) -> None:
        from io import StringIO

        source = StringIO(
            "drive,t,accel,gz,lat,lon,speed\n"
            "a,0,0,0,28.0,77.0,5\n"
            "a,1,0,0,,, \n"
            "b,0,0,0,28.1,77.1,6\n"
        )
        sessions = read_csv_sessions(
            source,
            ColumnMap(
                timestamp="t",
                forward_acceleration="accel",
                yaw_rate="gz",
                latitude="lat",
                longitude="lon",
                speed="speed",
                session="drive",
            ),
        )
        self.assertEqual([session.session_id for session in sessions], ["a", "b"])
        self.assertEqual(len(sessions[0].frames), 2)
        self.assertIsNone(sessions[0].frames[1].gnss)

    def test_speed_model_trains_and_round_trips_export(self) -> None:
        from io import StringIO

        frames = [
            SensorFrame(
                ImuSample(
                    float(index),
                    (-0.5, -0.2, 0.5, 1.0, 1.5, 2.0)[index],
                    (0.0, 0.2, -0.4, 0.7, -0.1, 0.5)[index],
                ),
                GnssFix(
                    float(index),
                    28.0,
                    77.0,
                    speed_mps=2.0
                    + 3.0 * (-0.5, -0.2, 0.5, 1.0, 1.5, 2.0)[index]
                    + 0.5 * (0.0, 0.2, -0.4, 0.7, -0.1, 0.5)[index],
                ),
            )
            for index in range(6)
        ]
        model = train_speed_model(frames)
        self.assertAlmostEqual(model.predict(frames[2]), 3.3, places=4)
        stream = StringIO()
        model.save(stream)
        stream.seek(0)
        restored = SpeedCorrectionModel.load(stream)
        self.assertAlmostEqual(restored.predict(frames[4]), model.predict(frames[4]), places=8)

    def test_temporal_model_predicts_and_round_trips_schema(self) -> None:
        frames = [
            SensorFrame(
                ImuSample(float(index), 0.2 * index, 0.01 * index),
                GnssFix(float(index), 28.0, 77.0, speed_mps=2.0 + 0.2 * index),
            )
            for index in range(11)
        ]
        model = train_temporal_speed_model(frames, window_size=5)
        prediction = model.predict(frames[3:8])
        self.assertGreaterEqual(prediction.speed_mps, 0.0)
        self.assertGreaterEqual(prediction.vibration_probability, 0.0)
        self.assertLessEqual(prediction.vibration_probability, 1.0)
        restored = TemporalSpeedModel.from_dict(model.to_dict())
        restored_prediction = restored.predict(frames[3:8])
        self.assertAlmostEqual(prediction.speed_mps, restored_prediction.speed_mps, places=8)
        self.assertAlmostEqual(
            prediction.vibration_probability,
            restored_prediction.vibration_probability,
            places=8,
        )


if __name__ == "__main__":
    unittest.main()
