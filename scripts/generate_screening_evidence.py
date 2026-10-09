from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from idr.benchmark import certify_replay
from idr.replay import DeadReckoningReplay
from idr.synthetic import straight_line_trace


def main() -> int:
    output_dir = ROOT / "docs" / "evidence"
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = straight_line_trace(
        sample_count=601,
        rate_hz=10.0,
        speed_mps=60.0 / 3.6,
        outage_start_s=10.0,
        outage_end_s=50.0,
    )
    states = DeadReckoningReplay().replay(frames)
    report = certify_replay("synthetic-1km-60kmph-outage", frames, states)
    (output_dir / "synthetic-1km-report.json").write_text(
        json.dumps(report.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "synthetic-1km-trajectory.svg").write_text(
        _trajectory_svg(frames, states),
        encoding="utf-8",
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.passed else 1


def _trajectory_svg(frames: list[object], states: list[object]) -> str:
    width, height, padding = 900, 420, 48
    truth = [(float(frame.truth_x_m or 0.0), float(frame.truth_y_m or 0.0)) for frame in frames]
    estimate = [(float(state.x_m), float(state.y_m)) for state in states]
    all_x = [point[0] for point in truth + estimate]
    all_y = [point[1] for point in truth + estimate]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    def point(value: tuple[float, float]) -> str:
        x = padding + (value[0] - min_x) / max(max_x - min_x, 1.0) * (width - 2 * padding)
        y = height - padding - (value[1] - min_y) / max(max_y - min_y, 1.0) * (height - 2 * padding)
        return f"{x:.2f},{y:.2f}"

    truth_points = " ".join(point(value) for value in truth)
    estimate_points = " ".join(point(value) for value in estimate)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{padding}" y="24" font-family="sans-serif" font-size="16">Synthetic 1 km trajectory, 60 km/h, 40 s GNSS outage</text>
<line x1="{padding}" y1="{height - padding}" x2="{width - padding}" y2="{height - padding}" stroke="#999"/>
<line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}" stroke="#999"/>
<polyline points="{truth_points}" fill="none" stroke="#1f77b4" stroke-width="3"/>
<polyline points="{estimate_points}" fill="none" stroke="#d62728" stroke-width="2" stroke-dasharray="6 4"/>
<text x="{padding}" y="{height - 14}" font-family="sans-serif" font-size="13">Truth (blue)</text>
<text x="{padding + 120}" y="{height - 14}" font-family="sans-serif" font-size="13">Replay estimate (red dashed)</text>
</svg>
"""


if __name__ == "__main__":
    raise SystemExit(main())
