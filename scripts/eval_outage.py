from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
import statistics
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "edge-engine"))
sys.path.insert(0, str(ROOT / "ml"))

from idr.models import SensorFrame
from idr_engine import FusionConfig, FusionEngine
from idr_ml.io_vnbd import ColumnMap, read_csv_sessions


def main() -> int:
    arguments = _parse_args()
    columns = ColumnMap(**json.loads(Path(arguments.columns).read_text(encoding="utf-8")))
    sessions = read_csv_sessions(arguments.input, columns)
    reports: list[dict[str, object]] = []
    for session in sessions:
        for start_s in _window_starts(session.frames, arguments.outage_seconds):
            frames = _mask_outage(session.frames, start_s, arguments.outage_seconds)
            if not any(frame.gnss is not None for frame in frames[: frames.index(next(
                frame for frame in frames if frame.imu.timestamp_s >= start_s
            ))]):
                continue
            states = FusionEngine(
                FusionConfig(outage_confirm_s=arguments.outage_confirm_seconds)
            ).replay(frames)
            errors = [
                ((state.x_m - frame.truth_x_m) ** 2 + (state.y_m - frame.truth_y_m) ** 2) ** 0.5
                for frame, state in zip(frames, states)
                if frame.truth_x_m is not None and frame.truth_y_m is not None
            ]
            distance = _travelled_distance(frames)
            if not errors or distance <= 0.0:
                continue
            reports.append({
                "session_id": session.session_id,
                "outage_start_s": start_s,
                "outage_seconds": arguments.outage_seconds,
                "drift_percent": max(errors) / distance * 100.0,
                "max_position_error_m": max(errors),
                "travelled_distance_m": distance,
            })
    if not reports:
        raise SystemExit("no evaluable windows: truth_x/truth_y and a pre-outage GNSS fix are required")
    payload = {
        "dataset": str(arguments.input),
        "method": "classical_fusion_baseline",
        "column_mapping": json.loads(Path(arguments.columns).read_text(encoding="utf-8")),
        "outage_seconds": arguments.outage_seconds,
        "window_count": len(reports),
        "aggregate": _aggregate(reports),
        "windows": reports,
    }
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate explicit CSV sessions with GNSS outage windows.")
    parser.add_argument("--input", type=Path, required=True, help="CSV path; dataset is not copied into the repository")
    parser.add_argument("--columns", type=Path, required=True, help="JSON ColumnMap produced after inspecting the CSV")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--outage-seconds", type=float, required=True)
    parser.add_argument("--outage-confirm-seconds", type=float, default=0.2)
    return parser.parse_args()


def _window_starts(frames: tuple[SensorFrame, ...], outage_seconds: float) -> Iterable[float]:
    if outage_seconds <= 0.0:
        raise ValueError("outage-seconds must be positive")
    start = frames[0].imu.timestamp_s
    end = frames[-1].imu.timestamp_s - outage_seconds
    timestamp = start
    while timestamp <= end:
        yield timestamp
        timestamp += outage_seconds


def _mask_outage(frames: tuple[SensorFrame, ...], start_s: float, duration_s: float) -> list[SensorFrame]:
    end_s = start_s + duration_s
    return [
        replace(frame, gnss=None)
        if start_s <= frame.imu.timestamp_s <= end_s
        else frame
        for frame in frames
    ]


def _travelled_distance(frames: list[SensorFrame]) -> float:
    return sum(
        ((b.truth_x_m - a.truth_x_m) ** 2 + (b.truth_y_m - a.truth_y_m) ** 2) ** 0.5
        for a, b in zip(frames, frames[1:])
        if None not in (a.truth_x_m, a.truth_y_m, b.truth_x_m, b.truth_y_m)
    )


def _aggregate(reports: list[dict[str, object]]) -> dict[str, float]:
    values = sorted(float(report["drift_percent"]) for report in reports)
    return {
        "median_drift_percent": statistics.median(values),
        "p90_drift_percent": values[min(len(values) - 1, int(len(values) * 0.9))],
        "worst_drift_percent": max(values),
    }


if __name__ == "__main__":
    raise SystemExit(main())
