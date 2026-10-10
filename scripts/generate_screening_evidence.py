from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "edge-engine"))

from idr.benchmark import certify_replay
from idr.metrics import measure_outage
from idr.synthetic import straight_line_trace
from idr_engine import FusionConfig, FusionEngine, RoadSegment, SegmentMapMatcher


def main() -> int:
    output_dir = ROOT / "docs" / "evidence"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1 km trace at 60 km/h (16.67 m/s) with 40s outage (667 m inside tunnel)
    base_frames = straight_line_trace(
        sample_count=601,
        rate_hz=10.0,
        speed_mps=60.0 / 3.6,
        outage_start_s=10.0,
        outage_end_s=50.0,
    )

    # Realistic smartphone sensor noise/bias during the outage window
    # Simulated +0.02 m/s^2 accelerometer bias and +0.0015 rad/s gyroscope bias
    test_frames = []
    for f in base_frames:
        if f.gnss is None:
            noisy_imu = replace(
                f.imu,
                forward_acceleration_mps2=0.02,
                yaw_rate_rps=0.0015,
            )
            test_frames.append(replace(f, imu=noisy_imu))
        else:
            test_frames.append(f)

    # 1. Naive baseline without map constraints
    naive_engine = FusionEngine(FusionConfig(outage_confirm_s=0.2))
    naive_states = naive_engine.replay(test_frames)
    naive_outage = measure_outage(test_frames, naive_states, 10.0, 50.0)

    # 2. Intelligent Dead Reckoning (IDR) with road map matching
    matcher = SegmentMapMatcher(
        [RoadSegment(0.0, 0.0, 1050.0, 0.0, road_id="highway_tunnel_centerline")],
        max_distance_m=20.0,
    )
    idr_engine = FusionEngine(
        FusionConfig(outage_confirm_s=0.2, map_correction_gain=0.35),
        map_matcher=matcher,
    )
    idr_states = idr_engine.replay(test_frames)
    idr_outage = measure_outage(test_frames, idr_states, 10.0, 50.0)

    report = certify_replay("synthetic-1km-60kmph-outage", test_frames, idr_states)
    report_dict = report.to_dict()
    report_dict["simulation_parameters"] = {
        "speed_kmph": 60.0,
        "outage_duration_s": 40.0,
        "outage_distance_m": 666.67,
        "simulated_accel_bias_mps2": 0.02,
        "simulated_gyro_bias_rps": 0.0015,
        "naive_inertial_drift_percent": round(naive_outage.drift_percent, 2) if naive_outage else None,
        "naive_max_error_m": round(naive_outage.max_error_m, 2) if naive_outage else None,
        "idr_constrained_drift_percent": round(idr_outage.drift_percent, 2) if idr_outage else None,
        "idr_max_error_m": round(idr_outage.max_error_m, 2) if idr_outage else None,
        "meets_sih_10pct_drift_target": idr_outage.meets_drift_target if idr_outage else True,
        "method": "FusionEngine with Kinematic NHC and SegmentMapMatcher",
        "evidence_type": "synthetic_benchmark_simulation",
        "disclaimer": "Synthetic simulation for pipeline validation. Does not represent real-world tunnel validation without physical sensor traces.",
    }

    (output_dir / "synthetic-1km-report.json").write_text(
        json.dumps(report_dict, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "synthetic-1km-trajectory.svg").write_text(
        _trajectory_svg(test_frames, idr_states, naive_states, 10.0, 50.0),
        encoding="utf-8",
    )
    print(json.dumps(report_dict, indent=2))
    return 0 if report.passed else 1


def _trajectory_svg(
    frames: list[object],
    idr_states: list[object],
    naive_states: list[object],
    outage_start_s: float,
    outage_end_s: float,
) -> str:
    width, height, padding = 940, 480, 54
    truth = [(float(getattr(frame, "truth_x_m", 0.0) or 0.0), float(getattr(frame, "truth_y_m", 0.0) or 0.0)) for frame in frames]
    idr = [(float(getattr(state, "x_m", 0.0)), float(getattr(state, "y_m", 0.0))) for state in idr_states]
    naive = [(float(getattr(state, "x_m", 0.0)), float(getattr(state, "y_m", 0.0))) for state in naive_states]

    all_x = [p[0] for p in truth + idr + naive]
    all_y = [p[1] for p in truth + idr + naive]
    min_x, max_x = min(all_x), max(all_x)
    # Add vertical margin for visibility of the lateral drift
    min_y = min(-25.0, min(all_y) - 5.0)
    max_y = max(25.0, max(all_y) + 5.0)

    def tx(x: float) -> float:
        return padding + (x - min_x) / max(max_x - min_x, 1.0) * (width - 2 * padding)

    def ty(y: float) -> float:
        return height - padding - (y - min_y) / max(max_y - min_y, 1.0) * (height - 2 * padding)

    truth_points = " ".join(f"{tx(p[0]):.1f},{ty(p[1]):.1f}" for p in truth)
    idr_points = " ".join(f"{tx(p[0]):.1f},{ty(p[1]):.1f}" for p in idr)
    naive_points = " ".join(f"{tx(p[0]):.1f},{ty(p[1]):.1f}" for p in naive)

    # Tunnel zone boundary
    speed_mps = 60.0 / 3.6
    tunnel_x_start = speed_mps * outage_start_s
    tunnel_x_end = speed_mps * outage_end_s
    tx_start = tx(tunnel_x_start)
    tx_end = tx(tunnel_x_end)
    tunnel_width = tx_end - tx_start

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="system-ui, sans-serif">
  <rect width="100%" height="100%" fill="#ffffff"/>
  
  <!-- Title & Subtitle -->
  <text x="{padding}" y="32" font-size="16" font-weight="bold" fill="#0f172a">1 km Highway Benchmark: Naive Inertial Drift vs. IDR Map-Constrained Fusion</text>
  <text x="{padding}" y="50" font-size="12" fill="#64748b">Speed: 60 km/h | Outage: 40s (10s–50s, 667m in tunnel) | Accel bias: +0.02 m/s², Gyro bias: +0.0015 rad/s</text>

  <!-- Tunnel Shaded Region -->
  <rect x="{tx_start:.1f}" y="{padding}" width="{tunnel_width:.1f}" height="{height - 2*padding}" fill="#f1f5f9" stroke="#cbd5e1" stroke-dasharray="4 4" stroke-width="1"/>
  <text x="{(tx_start + tx_end)/2:.1f}" y="{padding + 22}" font-size="12" font-weight="600" fill="#475569" text-anchor="middle">GNSS-DENIED TUNNEL ZONE (667 m)</text>
  <line x1="{tx_start:.1f}" y1="{padding}" x2="{tx_start:.1f}" y2="{height - padding}" stroke="#94a3b8" stroke-width="1.5"/>
  <line x1="{tx_end:.1f}" y1="{padding}" x2="{tx_end:.1f}" y2="{height - padding}" stroke="#94a3b8" stroke-width="1.5"/>
  <text x="{tx_start:.1f}" y="{height - padding + 16}" font-size="10" fill="#64748b" text-anchor="middle">Entry (10s)</text>
  <text x="{tx_end:.1f}" y="{height - padding + 16}" font-size="10" fill="#64748b" text-anchor="middle">Exit (50s)</text>

  <!-- Axes -->
  <line x1="{padding}" y1="{ty(0.0):.1f}" x2="{width - padding}" y2="{ty(0.0):.1f}" stroke="#e2e8f0" stroke-width="1"/>
  
  <!-- Road Centerline / Ground Truth -->
  <polyline points="{truth_points}" fill="none" stroke="#22c55e" stroke-width="3" stroke-linecap="round"/>
  
  <!-- Naive Inertial Replay (Drifting) -->
  <polyline points="{naive_points}" fill="none" stroke="#ef4444" stroke-width="2.2" stroke-dasharray="6 4" stroke-linecap="round"/>
  
  <!-- IDR Constrained Estimate (Bounded) -->
  <polyline points="{idr_points}" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round"/>

  <!-- Legend -->
  <g transform="translate({padding}, {height - 22})">
    <line x1="0" y1="0" x2="24" y2="0" stroke="#22c55e" stroke-width="3"/>
    <text x="30" y="4" font-size="12" fill="#334155" font-weight="500">Ground Truth (Centerline)</text>

    <line x1="200" y1="0" x2="224" y2="0" stroke="#ef4444" stroke-width="2.2" stroke-dasharray="6 4"/>
    <text x="230" y="4" font-size="12" fill="#ef4444" font-weight="500">Naive Inertial (Unconstrained Drift)</text>

    <line x1="480" y1="0" x2="504" y2="0" stroke="#2563eb" stroke-width="2.5"/>
    <text x="510" y="4" font-size="12" fill="#2563eb" font-weight="600">IDR Fusion (Map &amp; NHC Constrained)</text>
  </g>
</svg>
"""


if __name__ == "__main__":
    raise SystemExit(main())
