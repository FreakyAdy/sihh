from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable, TextIO

from .metrics import ReplayMetrics, measure_replay
from .models import NavigationState, SensorFrame


@dataclass(frozen=True)
class BenchmarkReport:
    name: str
    metrics: ReplayMetrics
    drift_target_percent: float = 10.0
    mobile_update_target_hz: float = 10.0

    @property
    def passed(self) -> bool:
        return (
            self.metrics.drift_percent < self.drift_target_percent
            and self.metrics.update_rate_hz >= self.mobile_update_target_hz
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["passed"] = self.passed
        payload["metrics"]["meets_drift_target"] = self.metrics.meets_drift_target
        payload["metrics"]["meets_mobile_rate_target"] = self.metrics.meets_mobile_rate_target
        return payload

    def save(self, destination: str | Path | TextIO) -> None:
        stream, should_close = _open(destination, "w")
        try:
            json.dump(self.to_dict(), stream, indent=2)
            stream.write("\n")
        finally:
            if should_close:
                stream.close()


def certify_replay(
    name: str,
    frames: list[SensorFrame],
    states: list[NavigationState],
    *,
    drift_target_percent: float = 10.0,
    mobile_update_target_hz: float = 10.0,
) -> BenchmarkReport:
    if drift_target_percent <= 0.0 or mobile_update_target_hz <= 0.0:
        raise ValueError("benchmark targets must be positive")
    return BenchmarkReport(
        name=name,
        metrics=measure_replay(frames, states),
        drift_target_percent=drift_target_percent,
        mobile_update_target_hz=mobile_update_target_hz,
    )


def _open(value: str | Path | TextIO, mode: str) -> tuple[TextIO, bool]:
    if hasattr(value, "read") or hasattr(value, "write"):
        return value, False  # type: ignore[return-value]
    return Path(value).open(mode, encoding="utf-8"), True
