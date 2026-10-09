import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "shared"))
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from idr.models import GnssFix, ImuSample, SensorFrame
from eval_outage import _aggregate, _mask_outage


class OutageEvaluationTests(unittest.TestCase):
    def test_masks_only_requested_interval(self) -> None:
        frames = tuple(
            SensorFrame(
                ImuSample(float(index), 0.0, 0.0),
                gnss=GnssFix(float(index), 0.0, 0.0),
                truth_x_m=float(index),
                truth_y_m=0.0,
            )
            for index in range(4)
        )
        masked = _mask_outage(frames, 1.0, 1.0)
        self.assertIsNotNone(masked[0].gnss)
        self.assertIsNone(masked[1].gnss)
        self.assertIsNone(masked[2].gnss)
        self.assertIsNotNone(masked[3].gnss)

    def test_aggregate_reports_median_p90_and_worst(self) -> None:
        reports = [
            {"drift_percent": v, "max_position_error_m": v * 10.0}
            for v in (1.0, 2.0, 10.0, 4.0)
        ]
        aggregate = _aggregate(reports)
        self.assertEqual(aggregate["median_drift_percent"], 3.0)
        self.assertEqual(aggregate["p90_drift_percent"], 10.0)
        self.assertEqual(aggregate["worst_drift_percent"], 10.0)


if __name__ == "__main__":
    unittest.main()
