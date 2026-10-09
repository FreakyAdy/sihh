from __future__ import annotations

import argparse
import json
import math
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
            outage_end_s = start_s + arguments.outage_seconds

            # Require at least one GNSS fix before the outage window so the
            # engine can initialize. A pre-outage fix is defined as any frame
            # whose IMU timestamp precedes the outage start.
            pre_outage_has_gnss = any(
                frame.gnss is not None
                for frame in frames
                if frame.imu.timestamp_s < start_s
            )
            if not pre_outage_has_gnss:
                continue

            states = FusionEngine(
                FusionConfig(outage_confirm_s=arguments.outage_confirm_seconds)
            ).replay(frames)

            # --- measure error ONLY inside the GNSS-denied interval ---
            outage_pairs = [
                (frame, state)
                for frame, state in zip(frames, states)
                if start_s <= frame.imu.timestamp_s <= outage_end_s
            ]
            errors = [
                math.hypot(state.x_m - frame.truth_x_m, state.y_m - frame.truth_y_m)
                for frame, state in outage_pairs
                if frame.truth_x_m is not None and frame.truth_y_m is not None
            ]

            # Ground-truth distance covered inside the outage window only
            outage_distance = _travelled_distance_window(frames, start_s, outage_end_s)

            # Coverage fraction: how many outage frames have truth labels
            outage_frame_count = len(outage_pairs)
            truth_covered = sum(
                1 for frame, _ in outage_pairs
                if frame.truth_x_m is not None and frame.truth_y_m is not None
            )
            truth_coverage = truth_covered / outage_frame_count if outage_frame_count else 0.0

            if not errors or outage_distance <= 0.0:
                continue

            sorted_errors = sorted(errors)
            p50 = statistics.median(sorted_errors)
            p90 = sorted_errors[min(len(sorted_errors) - 1, int(len(sorted_errors) * 0.9))]

            reports.append({
                "session_id": session.session_id,
                "outage_start_s": start_s,
                "outage_end_s": outage_end_s,
                "outage_seconds": arguments.outage_seconds,
                "outage_covered_distance_m": outage_distance,
                "truth_coverage_fraction": truth_coverage,
                "drift_percent": max(errors) / outage_distance * 100.0,
                "max_position_error_m": max(errors),
                "median_position_error_m": p50,
                "p90_position_error_m": p90,
            })

    if not reports:
        raise SystemExit(
            "no evaluable windows: truth_x/truth_y, a pre-outage GNSS fix, and "
            "non-zero ground-truth distance inside the outage window are required"
        )

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
    parser = argparse.ArgumentParser(
        description="Evaluate CSV sessions with GNSS outage windows. "
                    "Drift is measured ONLY inside the GNSS-denied interval."
    )
    parser.add_argument(
        "--input", type=Path, required=True,
        help="CSV path; dataset is not copied into the repository",
    )
    parser.add_argument(
        "--columns", type=Path, required=True,
        help="JSON ColumnMap produced after inspecting the CSV",
    )
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


def _travelled_distance_window(
    frames: list[SensorFrame], start_s: float, end_s: float
) -> float:
    """Ground-truth path length inside [start_s, end_s] only."""
    window = [f for f in frames if start_s <= f.imu.timestamp_s <= end_s]
    return sum(
        math.hypot(b.truth_x_m - a.truth_x_m, b.truth_y_m - a.truth_y_m)
        for a, b in zip(window, window[1:])
        if None not in (a.truth_x_m, a.truth_y_m, b.truth_x_m, b.truth_y_m)
    )


def _aggregate(reports: list[dict[str, object]]) -> dict[str, float]:
    drifts = sorted(float(report["drift_percent"]) for report in reports)
    max_errors = sorted(float(report["max_position_error_m"]) for report in reports)
    return {
        "median_drift_percent": statistics.median(drifts),
        "p90_drift_percent": drifts[min(len(drifts) - 1, int(len(drifts) * 0.9))],
        "worst_drift_percent": max(drifts),
        "median_max_error_m": statistics.median(max_errors),
        "p90_max_error_m": max_errors[min(len(max_errors) - 1, int(len(max_errors) * 0.9))],
    }


if __name__ == "__main__":
    raise SystemExit(main())
