import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "shared"))
sys.path.insert(0, str(Path(__file__).parents[1] / "edge-engine"))
sys.path.insert(0, str(Path(__file__).parents[1] / "mobile"))

from idr.models import GnssFix, ImuSample, NavigationMode, SensorFrame
from idr.replay import DeadReckoningReplay
from idr.scenarios import (
    ScenarioStatus,
    intermittent_gnss_trace,
    invalid_timestamp_trace,
    run_scenario,
)
from idr.synthetic import straight_line_trace
from idr_engine import FusionConfig, FusionEngine
from idr_mobile import MobileRuntime, RuntimeHealth, RuntimeSample


class IntegrationScenarioTests(unittest.TestCase):
    def test_blackout_recovery_runs_through_engine_and_mobile_runtime(self) -> None:
        frames = straight_line_trace(
            sample_count=21,
            rate_hz=10.0,
            speed_mps=8.0,
            outage_start_s=0.8,
            outage_end_s=1.4,
        )
        runtime = MobileRuntime(FusionEngine(FusionConfig(outage_confirm_s=0.2)))
        runtime.start()
        for frame in frames:
            runtime.submit(
                RuntimeSample(
                    frame.imu.timestamp_s,
                    frame.imu.forward_acceleration_mps2,
                    frame.imu.yaw_rate_rps,
                    frame.gnss,
                )
            )
        states = runtime.drain()
        self.assertEqual(len(states), len(frames))
        self.assertIn(NavigationMode.DEAD_RECKONING, [state.mode for state in states])
        self.assertEqual(states[-1].mode, NavigationMode.GNSS_AIDED)
        self.assertEqual(runtime.diagnostics.health, RuntimeHealth.READY)

    def test_intermittent_gnss_is_processed_without_timestamp_failure(self) -> None:
        engine = FusionEngine()
        states = engine.replay(intermittent_gnss_trace())
        self.assertEqual(len(states), 20)
        self.assertTrue(all(state.timestamp_s >= 0.0 for state in states))

    def test_invalid_timestamp_is_reported_as_failed_scenario(self) -> None:
        result = run_scenario(
            "out-of-order timestamps",
            invalid_timestamp_trace(),
            DeadReckoningReplay().update,
        )
        self.assertEqual(result.status, ScenarioStatus.FAILED)
        self.assertEqual(result.processed_count, 2)
        self.assertIn("strictly increasing", result.detail)

    def test_mobile_queue_pressure_is_explicit(self) -> None:
        runtime = MobileRuntime(FusionEngine(), max_queue_size=4)
        runtime.start()
        for index in range(10):
            runtime.submit(
                RuntimeSample(
                    float(index),
                    0.0,
                    0.0,
                    GnssFix(float(index), 28.0, 77.0, speed_mps=1.0),
                )
            )
        self.assertEqual(runtime.diagnostics.dropped_samples, 6)
        self.assertEqual(runtime.diagnostics.health, RuntimeHealth.DROPPED_SAMPLES)
