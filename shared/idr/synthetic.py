from __future__ import annotations

from .models import GnssFix, ImuSample, SensorFrame


METERS_PER_DEGREE = 111_319.49079327357


def straight_line_trace(
    sample_count: int = 101,
    rate_hz: float = 10.0,
    speed_mps: float = 10.0,
    outage_start_s: float = 3.0,
    outage_end_s: float = 7.0,
) -> list[SensorFrame]:
    if sample_count < 2 or rate_hz <= 0.0 or speed_mps < 0.0:
        raise ValueError("sample_count must be >= 2, rate_hz must be positive, and speed non-negative")
    frames: list[SensorFrame] = []
    for index in range(sample_count):
        timestamp_s = index / rate_hz
        x_m = speed_mps * timestamp_s
        gnss = None
        if not outage_start_s <= timestamp_s <= outage_end_s:
            gnss = GnssFix(
                timestamp_s=timestamp_s,
                latitude_deg=0.0,
                longitude_deg=x_m / METERS_PER_DEGREE,
                speed_mps=speed_mps,
            )
        frames.append(
            SensorFrame(
                imu=ImuSample(timestamp_s, 0.0, 0.0),
                gnss=gnss,
                truth_x_m=x_m,
                truth_y_m=0.0,
            )
        )
    return frames
