import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "shared"))

from idr.metrics import measure_replay
from idr.models import GnssFix, ImuSample, NavigationMode, SensorFrame
from idr.replay import DeadReckoningReplay
from idr.synthetic import straight_line_trace
from idr.trace import read_jsonl, write_jsonl


class ReplayTests(unittest.TestCase):
    def test_dead_reckoning_transitions_and_recovers(self) -> None:
        frames = []
        for index in range(11):
            timestamp = float(index)
            x = timestamp * 10.0
            gnss = GnssFix(
                timestamp_s=timestamp,
                latitude_deg=0.0,
                longitude_deg=x / 111_319.49079327357,
                speed_mps=10.0,
            )
            if 3 <= index <= 7:
                gnss = None
            frames.append(
                SensorFrame(
                    imu=ImuSample(timestamp, 0.0, 0.0),
                    gnss=gnss,
                    truth_x_m=x,
                    truth_y_m=0.0,
                )
            )

        states = DeadReckoningReplay().replay(frames)
        self.assertEqual(states[3].mode, NavigationMode.DEAD_RECKONING)
        self.assertEqual(states[8].mode, NavigationMode.GNSS_AIDED)
        self.assertAlmostEqual(states[7].x_m, 70.0, delta=1e-9)
        self.assertEqual(states[7].outage_duration_s, 4.0)

        metrics = measure_replay(frames, states)
        self.assertEqual(metrics.sample_count, 11)
        self.assertAlmostEqual(metrics.update_rate_hz, 1.0)
        self.assertLess(metrics.drift_percent, 0.01)
        self.assertEqual(metrics.outage_transition_latency_s, 0.0)

    def test_invalid_timestamp_is_rejected(self) -> None:
        replay = DeadReckoningReplay(
            GnssFix(0.0, 0.0, 0.0, speed_mps=1.0)
        )
        replay.update(SensorFrame(ImuSample(1.0, 0.0, 0.0)))
        with self.assertRaises(ValueError):
            replay.update(SensorFrame(ImuSample(1.0, 0.0, 0.0)))

    def test_local_projection_preserves_straight_distance(self) -> None:
        frames = [
            SensorFrame(
                ImuSample(float(index), 0.0, 0.0),
                GnssFix(float(index), 0.0, index / 111_319.49079327357, 10.0),
            )
            for index in range(2)
        ]
        states = DeadReckoningReplay().replay(frames)
        self.assertTrue(math.isclose(states[1].x_m, 1.0, abs_tol=1e-9))

    def test_synthetic_trace_round_trips_as_jsonl(self) -> None:
        frames = straight_line_trace(sample_count=5, rate_hz=1.0, outage_start_s=2.0, outage_end_s=2.0)
        from io import StringIO

        stream = StringIO()
        write_jsonl(frames, stream)
        stream.seek(0)
        restored = list(read_jsonl(stream))
        self.assertEqual(restored, frames)

    def test_contract_rejects_invalid_sensor_values(self) -> None:
        with self.assertRaises(ValueError):
            ImuSample(float("nan"), 0.0, 0.0)
        with self.assertRaises(ValueError):
            GnssFix(0.0, 91.0, 0.0)
        with self.assertRaises(ValueError):
            SensorFrame(ImuSample(0.0, 0.0, 0.0), GnssFix(1.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
