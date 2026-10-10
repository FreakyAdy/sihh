from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "edge-engine"))
sys.path.insert(0, str(ROOT / "mobile"))

from idr.benchmark import certify_replay
from idr.synthetic import straight_line_trace
from idr_engine import FusionConfig, FusionEngine


REQUIRED_PATHS = (
    ROOT / ".ofa" / "config.yml",
    ROOT / "README.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "benchmarking.md",
    ROOT / "docs" / "demo-runbook.md",
    ROOT / "docs" / "model-card.md",
    ROOT / "docs" / "gap-audit.md",
    ROOT / "docs" / "requirements-matrix.md",
    ROOT / "docs" / "data-provenance.md",
    ROOT / "docs" / "limitations.md",
    ROOT / "docs" / "io-vnbd-evaluation.md",
    ROOT / "docs" / "evidence" / "synthetic-1km-report.json",
    ROOT / "docs" / "evidence" / "synthetic-1km-trajectory.svg",
    ROOT / "shared" / "idr",
    ROOT / "edge-engine" / "idr_engine",
    ROOT / "ml" / "idr_ml",
    ROOT / "mobile" / "idr_mobile",
    ROOT / "rover" / "protocol.py",
)


def main() -> int:
    missing = [path.relative_to(ROOT).as_posix() for path in REQUIRED_PATHS if not path.exists()]
    if missing:
        print(json.dumps({"passed": False, "missing_paths": missing}, indent=2))
        return 1

    frames = straight_line_trace(
        sample_count=101,
        rate_hz=10.0,
        speed_mps=10.0,
        outage_start_s=3.0,
        outage_end_s=7.0,
    )
    states = FusionEngine(FusionConfig(outage_confirm_s=0.2)).replay(frames)
    report = certify_replay("release-synthetic-baseline", frames, states)
    payload = {
        "release": "0.1.0-screening",
        "passed": report.passed,
        "benchmark": report.to_dict(),
        "required_paths": [path.relative_to(ROOT).as_posix() for path in REQUIRED_PATHS],
    }
    print(json.dumps(payload, indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
