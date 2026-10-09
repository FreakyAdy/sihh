from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Sequence

from .models import GnssFix, ImuSample, SensorFrame


class ScenarioStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    status: ScenarioStatus
    processed_count: int
    expected_count: int
    detail: str


def run_scenario(
    name: str,
    frames: Sequence[SensorFrame],
    process: Callable[[SensorFrame], object],
) -> ScenarioResult:
    processed = 0
    try:
        for frame in frames:
            process(frame)
            processed += 1
    except (TypeError, ValueError, RuntimeError) as error:
        return ScenarioResult(
            name=name,
            status=ScenarioStatus.FAILED,
            processed_count=processed,
            expected_count=len(frames),
            detail=str(error),
        )
    return ScenarioResult(
        name=name,
        status=ScenarioStatus.PASSED,
        processed_count=processed,
        expected_count=len(frames),
        detail="all frames processed",
    )


def intermittent_gnss_trace(sample_count: int = 20) -> list[SensorFrame]:
    if sample_count < 4:
        raise ValueError("sample_count must be at least 4")
    frames: list[SensorFrame] = []
    for index in range(sample_count):
        timestamp = index / 10.0
        gnss = (
            GnssFix(timestamp, 28.0, 77.0, speed_mps=8.0)
            if index % 3 != 1
            else None
        )
        frames.append(SensorFrame(ImuSample(timestamp, 0.0, 0.0), gnss))
    return frames


def invalid_timestamp_trace() -> list[SensorFrame]:
    return [
        SensorFrame(ImuSample(0.0, 0.0, 0.0), GnssFix(0.0, 28.0, 77.0, speed_mps=1.0)),
        SensorFrame(ImuSample(0.1, 0.0, 0.0)),
        SensorFrame(ImuSample(0.1, 0.0, 0.0)),
    ]
