from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "edge-engine"))

from idr.models import GnssFix, ImuSample, SensorFrame
from idr.throughput import measure_throughput
from idr_engine import FusionEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure deterministic engine throughput.")
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--target-hz", type=float, default=200.0)
    args = parser.parse_args()
    if args.samples <= 0:
        parser.error("--samples must be positive")
    engine = FusionEngine()
    frames = [
        SensorFrame(
            ImuSample(index / args.target_hz, 0.0, 0.0),
            GnssFix(index / args.target_hz, 0.0, 0.0, speed_mps=10.0) if index == 0 else None,
        )
        for index in range(args.samples)
    ]
    report = measure_throughput(
        frames,
        engine.update,
        target_rate_hz=args.target_hz,
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.meets_target else 1


if __name__ == "__main__":
    raise SystemExit(main())
