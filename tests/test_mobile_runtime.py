import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "shared"))
sys.path.insert(0, str(Path(__file__).parents[1] / "edge-engine"))
sys.path.insert(0, str(Path(__file__).parents[1] / "mobile"))

from idr.models import GnssFix, NavigationMode
from idr_engine import FusionEngine
from idr_mobile import MobileRuntime, RuntimeHealth, RuntimeSample


class MobileRuntimeTests(unittest.TestCase):
    def test_bounded_queue_reports_dropped_samples(self) -> None:
        runtime = MobileRuntime(FusionEngine(), max_queue_size=2)
        runtime.start()
        for index in range(3):
            runtime.submit(
                RuntimeSample(
                    timestamp_s=float(index),
                    forward_acceleration_mps2=0.0,
                    yaw_rate_rps=0.0,
                    gnss=GnssFix(float(index), 28.0, 77.0, speed_mps=1.0),
                )
            )
        self.assertEqual(runtime.diagnostics.dropped_samples, 1)
        self.assertEqual(runtime.diagnostics.health, RuntimeHealth.DROPPED_SAMPLES)

    def test_worker_drain_produces_navigation_state(self) -> None:
        runtime = MobileRuntime(FusionEngine())
        runtime.start()
        runtime.submit(RuntimeSample(0.0, 0.0, 0.0, GnssFix(0.0, 28.0, 77.0, 2.0)))
        states = runtime.drain()
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].mode, NavigationMode.GNSS_AIDED)
        self.assertEqual(runtime.diagnostics.health, RuntimeHealth.READY)

    def test_stop_clears_queue_and_requires_restart(self) -> None:
        runtime = MobileRuntime(FusionEngine())
        runtime.start()
        runtime.submit(RuntimeSample(0.0, 0.0, 0.0))
        runtime.stop()
        self.assertEqual(runtime.diagnostics.queue_depth, 0)
        with self.assertRaises(RuntimeError):
            runtime.drain()
