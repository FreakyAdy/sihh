from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from statistics import median
from typing import Sequence

from idr.models import ImuSample


class QualityFlag(StrEnum):
    VALID = "valid"
    HIGH_ACCELERATION = "high_acceleration"
    HIGH_YAW_RATE = "high_yaw_rate"
    TIMESTAMP_GAP = "timestamp_gap"


@dataclass(frozen=True)
class QualityReport:
    flags: tuple[QualityFlag, ...]
    vibration_score: float


def assess_quality(
    samples: Sequence[ImuSample],
    acceleration_limit_mps2: float = 12.0,
    yaw_rate_limit_rps: float = 2.5,
    max_gap_s: float = 0.25,
) -> list[QualityReport]:
    if acceleration_limit_mps2 <= 0.0 or yaw_rate_limit_rps <= 0.0 or max_gap_s <= 0.0:
        raise ValueError("quality limits must be positive")
    reports: list[QualityReport] = []
    for index, sample in enumerate(samples):
        flags: list[QualityFlag] = []
        if abs(sample.forward_acceleration_mps2) > acceleration_limit_mps2:
            flags.append(QualityFlag.HIGH_ACCELERATION)
        if abs(sample.yaw_rate_rps) > yaw_rate_limit_rps:
            flags.append(QualityFlag.HIGH_YAW_RATE)
        if index and sample.timestamp_s - samples[index - 1].timestamp_s > max_gap_s:
            flags.append(QualityFlag.TIMESTAMP_GAP)
        if not flags:
            flags.append(QualityFlag.VALID)
        vibration_score = min(1.0, abs(sample.forward_acceleration_mps2) / acceleration_limit_mps2)
        reports.append(QualityReport(tuple(flags), vibration_score))
    return reports


def smooth_acceleration(samples: Sequence[ImuSample], window_size: int = 5) -> list[float]:
    if window_size < 1 or window_size % 2 == 0:
        raise ValueError("window_size must be a positive odd number")
    if not all(isfinite(sample.forward_acceleration_mps2) for sample in samples):
        raise ValueError("samples must contain finite acceleration")
    result: list[float] = []
    half_window = window_size // 2
    for index in range(len(samples)):
        start = max(0, index - half_window)
        end = min(len(samples), index + half_window + 1)
        result.append(median(sample.forward_acceleration_mps2 for sample in samples[start:end]))
    return result
