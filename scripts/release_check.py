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
    ROOT / "docs" / "evidence" / "io-vnbd" / "model.json",
    ROOT / "docs" / "evidence" / "io-vnbd" / "evaluation-report.json",
    ROOT / "docs" / "evidence" / "io-vnbd" / "trajectory-iovnbd-outage.svg",
    ROOT / "docs" / "evidence" / "io-vnbd" / "provenance.json",
    ROOT / "mobile" / "app" / "src" / "main" / "assets" / "model.json",
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

    # Verify synthetic 1 km report
    synthetic_report_path = ROOT / "docs" / "evidence" / "synthetic-1km-report.json"
    synthetic_data = json.loads(synthetic_report_path.read_text(encoding="utf-8"))
    synthetic_passed = synthetic_data.get("passed", False) and synthetic_data.get("outage_metrics", {}).get("meets_drift_target", False)

    # Verify IO-VNBD evaluation report
    iovnbd_report_path = ROOT / "docs" / "evidence" / "io-vnbd" / "evaluation-report.json"
    iovnbd_data = json.loads(iovnbd_report_path.read_text(encoding="utf-8"))
    iovnbd_passed = (
        iovnbd_data.get("model_trained", False)
        and iovnbd_data.get("classical", {}).get("window_count", 0) > 0
    )

    frames = straight_line_trace(
        sample_count=101,
        rate_hz=10.0,
        speed_mps=10.0,
        outage_start_s=3.0,
        outage_end_s=7.0,
    )
    states = FusionEngine(FusionConfig(outage_confirm_s=0.2)).replay(frames)
    report = certify_replay("release-synthetic-baseline", frames, states)

    overall_passed = report.passed and synthetic_passed and iovnbd_passed
    payload = {
        "release": "0.1.0-screening",
        "passed": overall_passed,
        "benchmark": report.to_dict(),
        "evidence_verification": {
            "synthetic_1km_verified": synthetic_passed,
            "io_vnbd_verified": iovnbd_passed,
        },
        "required_paths": [path.relative_to(ROOT).as_posix() for path in REQUIRED_PATHS],
    }
    print(json.dumps(payload, indent=2))
    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
