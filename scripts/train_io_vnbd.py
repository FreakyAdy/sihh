"""Train the speed-correction model on IO-VNBD data and evaluate on held-out sessions.

This script is the primary evidence-generation entry point for the SIH screening
submission.  It produces:

  <output-dir>/model.json               — trained ridge model artifact
  <output-dir>/evaluation-report.json   — outage-only drift statistics
  <output-dir>/trajectory-<id>.svg      — position plot per held-out session

Usage
-----
  python scripts/train_io_vnbd.py \\
      --input      C:/data/io-vnbd/session.csv \\
      --columns    ml/idr_ml/io_vnbd_columns_template.json \\
      --outage-seconds 60 \\
      --output-dir docs/evidence/io-vnbd/

The raw CSV must live outside the repository (--input path).
Only the produced artifacts are committed.

Evaluation note
---------------
Drift is measured ONLY inside the GNSS-denied window (Phase 1 fix).
A pre-outage GNSS fix is required to initialize the engine.
Sessions without adequate GNSS or truth coverage are reported but not
counted toward the aggregate metrics.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "edge-engine"))
sys.path.insert(0, str(ROOT / "ml"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

from idr.models import SensorFrame
from idr.metrics import OutageMetrics, measure_outage
from idr_engine import FusionConfig, FusionEngine
from idr_engine.fusion import FusionCorrection, LinearFusionCorrection
from idr_ml.io_vnbd import ColumnMap, read_csv_sessions
from idr_ml.dataset import session_train_test_split
from idr_ml.model import SpeedCorrectionModel, extract_features, train_speed_model


def main() -> int:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading column map from %s", args.columns)
    raw_columns = json.loads(args.columns.read_text(encoding="utf-8"))
    # Strip internal comment key before constructing the dataclass
    raw_columns.pop("_comment", None)
    columns = ColumnMap(**raw_columns)

    logger.info("Reading sessions from %s", args.input)
    sessions = read_csv_sessions(args.input, columns)
    logger.info("Loaded %d session(s)", len(sessions))

    if len(sessions) < 2:
        logger.warning(
            "Only %d session found. At least 2 are needed for a meaningful "
            "train/test split. Proceeding with train=all, test=all (data leakage — "
            "label results clearly).",
            len(sessions),
        )
        train_sessions, test_sessions = sessions, sessions
    else:
        train_sessions, test_sessions = session_train_test_split(
            sessions, test_fraction=args.test_fraction, seed=args.seed
        )
        logger.info(
            "Split: %d train session(s), %d test session(s)",
            len(train_sessions), len(test_sessions),
        )

    # --- Train speed-correction model ---
    train_frames: list[SensorFrame] = [
        frame for session in train_sessions for frame in session.frames
    ]
    gnss_train = [f for f in train_frames if f.gnss is not None and f.gnss.speed_mps is not None]
    logger.info(
        "Training on %d total frames, %d with GNSS speed labels",
        len(train_frames), len(gnss_train),
    )

    model: SpeedCorrectionModel | None = None
    if len(gnss_train) >= 10:
        try:
            model = train_speed_model(train_frames, ridge=args.ridge)
            model_path = args.output_dir / "model.json"
            model.save(model_path)
            logger.info("Model saved to %s", model_path)
        except ValueError as exc:
            logger.warning("Model training failed: %s. Using no-correction baseline.", exc)
    else:
        logger.warning(
            "Insufficient GNSS-labelled frames for training (%d < 10). "
            "Running classical baseline only.",
            len(gnss_train),
        )

    # --- Evaluate on held-out test sessions ---
    classical_reports: list[dict[str, object]] = []
    model_reports: list[dict[str, object]] = []

    trajectory_data: list[dict[str, object]] = []

    for session in test_sessions:
        logger.info("Evaluating session %r (%d frames)", session.session_id, len(session.frames))
        start_s = session.frames[0].imu.timestamp_s
        outage_start = start_s + args.warmup_seconds
        outage_end = outage_start + args.outage_seconds

        # Check that there are frames in the outage window
        outage_frames = [
            f for f in session.frames
            if outage_start <= f.imu.timestamp_s <= outage_end
        ]
        if not outage_frames:
            logger.warning("Session %r: no frames in outage window — skipping.", session.session_id)
            continue

        # Require a pre-outage GNSS fix
        pre_gnss = [
            f for f in session.frames
            if f.imu.timestamp_s < outage_start and f.gnss is not None
        ]
        if not pre_gnss:
            logger.warning("Session %r: no pre-outage GNSS fix — skipping.", session.session_id)
            continue

        # Mask GNSS during the outage window
        from dataclasses import replace as dc_replace
        masked_frames = [
            dc_replace(f, gnss=None)
            if outage_start <= f.imu.timestamp_s <= outage_end
            else f
            for f in session.frames
        ]

        # --- Classical baseline ---
        try:
            classical_states = FusionEngine(
                FusionConfig(outage_confirm_s=0.2)
            ).replay(masked_frames)
            cm = measure_outage(
                masked_frames, classical_states, outage_start, outage_end
            )
            if cm is not None:
                classical_reports.append(_report_dict(session.session_id, "classical", cm))
                logger.info(
                    "  Classical: drift=%.1f%%, max_err=%.1fm, coverage=%.0f%%",
                    cm.drift_percent, cm.max_error_m, cm.truth_coverage_fraction * 100,
                )
        except Exception as exc:
            logger.warning("  Classical evaluation failed for session %r: %s", session.session_id, exc)
            classical_states = []

        # --- Model-corrected path ---
        if model is not None:
            try:
                model_states = FusionEngine(
                    FusionConfig(outage_confirm_s=0.2),
                    correction_model=_ModelSpeedCorrection(model),
                ).replay(masked_frames)
                mm = measure_outage(
                    masked_frames, model_states, outage_start, outage_end
                )
                if mm is not None:
                    model_reports.append(_report_dict(session.session_id, "model_ridge", mm))
                    logger.info(
                        "  Model:     drift=%.1f%%, max_err=%.1fm, coverage=%.0f%%",
                        mm.drift_percent, mm.max_error_m, mm.truth_coverage_fraction * 100,
                    )
            except Exception as exc:
                logger.warning("  Model evaluation failed for session %r: %s", session.session_id, exc)
                model_states = []
        else:
            model_states = []

        # Collect trajectory data for SVG plot
        trajectory_data.append({
            "session_id": session.session_id,
            "outage_start_s": outage_start,
            "outage_end_s": outage_end,
            "frames": masked_frames,
            "classical_states": classical_states,
            "model_states": model_states,
        })

    # --- Write evaluation report ---
    report_payload = {
        "dataset": str(args.input),
        "outage_seconds": args.outage_seconds,
        "warmup_seconds": args.warmup_seconds,
        "test_sessions": [s.session_id for s in test_sessions],
        "train_sessions": [s.session_id for s in train_sessions],
        "model_trained": model is not None,
        "classical": {
            "window_count": len(classical_reports),
            "aggregate": _aggregate(classical_reports),
            "windows": classical_reports,
        },
        "model_ridge": {
            "window_count": len(model_reports),
            "aggregate": _aggregate(model_reports),
            "windows": model_reports,
        },
    }
    report_path = args.output_dir / "evaluation-report.json"
    report_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Evaluation report written to %s", report_path)

    # --- Generate position plots ---
    for traj in trajectory_data:
        svg = _build_trajectory_svg(traj)
        svg_path = args.output_dir / f"trajectory-{traj['session_id']}.svg"
        svg_path.write_text(svg, encoding="utf-8")
        logger.info("Trajectory SVG written to %s", svg_path)

    _print_summary(report_payload)
    return 0


# ---------------------------------------------------------------------------
# Model correction adapter
# ---------------------------------------------------------------------------

class _ModelSpeedCorrection:
    """Wraps SpeedCorrectionModel as a FusionCorrectionModel.

    The speed model predicts speed. We supply this as speed_override_mps so the
    fusion filter blends learned estimates with dead reckoning propagation.
    """

    def __init__(self, model: SpeedCorrectionModel) -> None:
        self._model = model
        self._current_speed: float = 0.0
        self._last_t: float | None = None

    def predict(self, frame: SensorFrame) -> FusionCorrection:
        t = frame.imu.timestamp_s
        dt = 0.0 if self._last_t is None else max(0.0, t - self._last_t)
        self._last_t = t
        if frame.gnss is not None and frame.gnss.speed_mps is not None:
            self._current_speed = frame.gnss.speed_mps
        else:
            self._current_speed = max(0.0, self._current_speed + frame.imu.forward_acceleration_mps2 * dt)

        predicted = self._model.predict(frame)
        if math.isfinite(predicted) and predicted > 0.0:
            override = 0.85 * self._current_speed + 0.15 * predicted
        else:
            override = None
        return FusionCorrection(
            speed_override_mps=override,
            acceleration_scale=1.0,
        )


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def _report_dict(session_id: str, method: str, m: OutageMetrics) -> dict[str, object]:
    return {
        "session_id": session_id,
        "method": method,
        "outage_start_s": m.outage_start_s,
        "outage_end_s": m.outage_end_s,
        "outage_covered_distance_m": m.covered_distance_m,
        "truth_coverage_fraction": m.truth_coverage_fraction,
        "drift_percent": m.drift_percent,
        "max_position_error_m": m.max_error_m,
        "median_position_error_m": m.median_error_m,
        "p90_position_error_m": m.p90_error_m,
        "meets_sih_target": m.meets_drift_target,
    }


def _aggregate(reports: list[dict[str, object]]) -> dict[str, object]:
    if not reports:
        return {}
    drifts = sorted(float(r["drift_percent"]) for r in reports)
    max_errors = sorted(float(r["max_position_error_m"]) for r in reports)
    return {
        "median_drift_percent": statistics.median(drifts),
        "p90_drift_percent": drifts[min(len(drifts) - 1, int(len(drifts) * 0.9))],
        "worst_drift_percent": max(drifts),
        "median_max_error_m": statistics.median(max_errors),
        "p90_max_error_m": max_errors[min(len(max_errors) - 1, int(len(max_errors) * 0.9))],
        "meets_sih_target_count": sum(1 for r in reports if r.get("meets_sih_target")),
        "total_count": len(reports),
    }


def _print_summary(report: dict[str, object]) -> None:
    print("\n" + "=" * 60)
    print("IO-VNBD Evaluation Summary")
    print("=" * 60)
    classical = report["classical"]
    model = report["model_ridge"]
    if classical["aggregate"]:  # type: ignore[index]
        agg = classical["aggregate"]  # type: ignore[index]
        print(f"Classical baseline:")
        print(f"  Windows evaluated : {classical['window_count']}")
        print(f"  Median drift      : {agg['median_drift_percent']:.1f} %")  # type: ignore[index]
        print(f"  P90 drift         : {agg['p90_drift_percent']:.1f} %")  # type: ignore[index]
        print(f"  Worst drift       : {agg['worst_drift_percent']:.1f} %")  # type: ignore[index]
        print(f"  SIH target met    : {agg['meets_sih_target_count']}/{agg['total_count']}")  # type: ignore[index]
    if model["aggregate"]:  # type: ignore[index]
        agg = model["aggregate"]  # type: ignore[index]
        print(f"Ridge model correction:")
        print(f"  Median drift      : {agg['median_drift_percent']:.1f} %")  # type: ignore[index]
        print(f"  P90 drift         : {agg['p90_drift_percent']:.1f} %")  # type: ignore[index]
        print(f"  SIH target met    : {agg['meets_sih_target_count']}/{agg['total_count']}")  # type: ignore[index]
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# SVG trajectory plotter
# ---------------------------------------------------------------------------

def _build_trajectory_svg(traj: dict) -> str:
    """Generate a minimal SVG position plot comparing truth vs DR trajectories."""
    frames = traj["frames"]
    classical = traj["classical_states"]
    model_states = traj["model_states"]
    outage_start = traj["outage_start_s"]
    outage_end = traj["outage_end_s"]

    # Collect all coordinate sets
    truth_xy = [
        (f.truth_x_m, f.truth_y_m) for f in frames
        if f.truth_x_m is not None and f.truth_y_m is not None
    ]
    classical_xy = [(s.x_m, s.y_m) for s in classical] if classical else []
    model_xy = [(s.x_m, s.y_m) for s in model_states] if model_states else []

    all_x = [p[0] for p in truth_xy + classical_xy + model_xy]
    all_y = [p[1] for p in truth_xy + classical_xy + model_xy]
    if not all_x:
        return "<svg xmlns='http://www.w3.org/2000/svg'><text>No data</text></svg>"

    pad = 20.0
    width, height = 800.0, 600.0
    x_min, x_max = min(all_x) - pad, max(all_x) + pad
    y_min, y_max = min(all_y) - pad, max(all_y) + pad
    x_range = max(x_max - x_min, 1.0)
    y_range = max(y_max - y_min, 1.0)

    def tx(x: float) -> float:
        return (x - x_min) / x_range * (width - 80) + 40

    def ty(y: float) -> float:
        return height - 40 - (y - y_min) / y_range * (height - 80)

    def _polyline(points: list[tuple[float, float]], color: str, dash: str = "", width_px: float = 2.0) -> str:
        if len(points) < 2:
            return ""
        pts = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in points)
        stroke_dash = f'stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width_px}" {stroke_dash}/>'

    # Outage region (grey band by x-extent of outage frames)
    outage_truth = [
        (f.truth_x_m, f.truth_y_m) for f in frames
        if outage_start <= f.imu.timestamp_s <= outage_end
        and f.truth_x_m is not None and f.truth_y_m is not None
    ]
    outage_band = ""
    if outage_truth:
        ox_min = tx(min(p[0] for p in outage_truth)) - 4
        ox_max = tx(max(p[0] for p in outage_truth)) + 4
        outage_band = (
            f'<rect x="{ox_min:.1f}" y="40" '
            f'width="{max(ox_max - ox_min, 8):.1f}" height="{height - 80:.1f}" '
            f'fill="#e0e0e0" opacity="0.5"/>'
        )

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width)}" height="{int(height)}" '
        f'viewBox="0 0 {int(width)} {int(height)}">',
        '<rect width="100%" height="100%" fill="white"/>',
        # Border
        f'<rect x="40" y="40" width="{width-80:.0f}" height="{height-80:.0f}" '
        f'fill="none" stroke="#cccccc" stroke-width="1"/>',
        # Outage band
        outage_band,
        # Trajectories
        _polyline(truth_xy, "#22a855", width_px=2.5),
        _polyline(classical_xy, "#3b82f6", dash="8,4"),
        _polyline(model_xy, "#f97316", dash="4,4"),
        # Legend
        '<g font-family="sans-serif" font-size="13">',
        f'<line x1="50" y1="20" x2="80" y2="20" stroke="#22a855" stroke-width="2.5"/>',
        f'<text x="85" y="24" fill="#22a855">Ground truth</text>',
        f'<line x1="220" y1="20" x2="250" y2="20" stroke="#3b82f6" stroke-width="2" stroke-dasharray="8,4"/>',
        f'<text x="255" y="24" fill="#3b82f6">Classical DR</text>',
        f'<line x1="380" y1="20" x2="410" y2="20" stroke="#f97316" stroke-width="2" stroke-dasharray="4,4"/>',
        f'<text x="415" y="24" fill="#f97316">Ridge model DR</text>',
        f'<rect x="550" y="10" width="14" height="14" fill="#e0e0e0" opacity="0.7"/>',
        f'<text x="568" y="23" fill="#888">GNSS outage</text>',
        '</g>',
        # Title
        f'<text x="{width/2:.0f}" y="{height - 10:.0f}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="12" fill="#666">'
        f'Session: {traj["session_id"]} — outage {outage_end - outage_start:.0f}s</text>',
        '</svg>',
    ]
    return "\n".join(svg_lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="IO-VNBD CSV path (outside repo)")
    parser.add_argument("--columns", type=Path, required=True, help="ColumnMap JSON file")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for artifacts")
    parser.add_argument("--outage-seconds", type=float, default=60.0)
    parser.add_argument("--warmup-seconds", type=float, default=30.0,
                        help="Seconds of GNSS-aided travel before the synthetic outage begins")
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ridge", type=float, default=1e-6)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
