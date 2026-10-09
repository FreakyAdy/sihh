from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from idr.models import SensorFrame

from .quality import smooth_acceleration


@dataclass(frozen=True)
class BaselineOutput:
    speeds_mps: tuple[float, ...]
    used_gnss_count: int
    rejected_acceleration_count: int


def estimate_forward_speed(
    frames: Sequence[SensorFrame],
    initial_speed_mps: float = 0.0,
    acceleration_limit_mps2: float = 12.0,
    smoothing_window: int = 5,
) -> BaselineOutput:
    """Estimate forward speed using GNSS anchors and robust IMU integration."""

    if initial_speed_mps < 0.0:
        raise ValueError("initial_speed_mps must be non-negative")
    if not frames:
        return BaselineOutput((), 0, 0)
    smoothed = smooth_acceleration([frame.imu for frame in frames], smoothing_window)
    speeds: list[float] = []
    speed = initial_speed_mps
    used_gnss_count = 0
    rejected_count = 0
    previous_timestamp = frames[0].imu.timestamp_s
    for index, frame in enumerate(frames):
        timestamp = frame.imu.timestamp_s
        dt_s = 0.0 if index == 0 else timestamp - previous_timestamp
        if index > 0 and dt_s <= 0.0:
            raise ValueError("frame timestamps must be strictly increasing")
        previous_timestamp = timestamp
        if frame.gnss is not None and frame.gnss.speed_mps is not None:
            speed = frame.gnss.speed_mps
            used_gnss_count += 1
        elif abs(smoothed[index]) > acceleration_limit_mps2:
            rejected_count += 1
        else:
            speed = max(0.0, speed + smoothed[index] * dt_s)
        speeds.append(speed)
    return BaselineOutput(tuple(speeds), used_gnss_count, rejected_count)
