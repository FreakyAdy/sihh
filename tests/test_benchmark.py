import json
import sys
import unittest
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "shared"))

from idr.benchmark import certify_replay
from idr.replay import DeadReckoningReplay
from idr.synthetic import straight_line_trace


class BenchmarkTests(unittest.TestCase):
    def test_certification_reports_drift_and_update_targets(self) -> None:
        frames = straight_line_trace(
            sample_count=101,
            rate_hz=10.0,
            speed_mps=10.0,
            outage_start_s=3.0,
            outage_end_s=7.0,
        )
        states = DeadReckoningReplay().replay(frames)
        report = certify_replay("synthetic-straight-line", frames, states)
        self.assertTrue(report.passed)
        self.assertLess(report.metrics.drift_percent, 10.0)
        self.assertGreaterEqual(report.metrics.update_rate_hz, 10.0)
        self.assertIsNotNone(report.metrics.outage_transition_latency_s)
        self.assertIsNotNone(report.metrics.recovery_timestamp_s)

    def test_report_json_is_reviewable(self) -> None:
        frames = straight_line_trace(sample_count=11, rate_hz=10.0)
        report = certify_replay("short", frames, DeadReckoningReplay().replay(frames))
        stream = StringIO()
        report.save(stream)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["name"], "short")
        self.assertIn("drift_percent", payload["metrics"])
        self.assertTrue(payload["passed"])


if __name__ == "__main__":
    unittest.main()
