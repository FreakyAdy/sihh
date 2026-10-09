from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .models import NavigationState, SensorFrame


@dataclass(frozen=True)
class ReplayMetrics:
    sample_count: int
    duration_s: float
    update_rate_hz: float
    max_position_error_m: float
    travelled_distance_m: float
    drift_percent: float
    outage_transition_latency_s: float | None


def measure_replay(
    frames: Sequence[SensorFrame], states: Sequence[NavigationState]
) -> ReplayMetrics:
    if len(frames) != len(states):
        raise ValueError("frames and states must have equal length")
    if not frames:
        raise ValueError("at least one frame is required")

    duration_s = frames[-1].imu.timestamp_s - frames[0].imu.timestamp_s
    update_rate_hz = (len(frames) - 1) / duration_s if duration_s > 0 else 0.0
    errors = [
        math.hypot(state.x_m - frame.truth_x_m, state.y_m - frame.truth_y_m)
        for frame, state in zip(frames, states)
        if frame.truth_x_m is not None and frame.truth_y_m is not None
    ]
    travelled_distance_m = sum(
        math.hypot(b.truth_x_m - a.truth_x_m, b.truth_y_m - a.truth_y_m)
        for a, b in zip(frames, frames[1:])
        if None not in (a.truth_x_m, a.truth_y_m, b.truth_x_m, b.truth_y_m)
    )
    outage_transition_latency_s = next(
        (
            state.timestamp_s - frame.imu.timestamp_s
            for frame, state in zip(frames, states)
            if frame.gnss is None and state.mode.value == "dead_reckoning"
        ),
        None,
    )
    return ReplayMetrics(
        sample_count=len(frames),
        duration_s=duration_s,
        update_rate_hz=update_rate_hz,
        max_position_error_m=max(errors, default=0.0),
        travelled_distance_m=travelled_distance_m,
        drift_percent=(
            max(errors, default=0.0) / travelled_distance_m * 100.0
            if travelled_distance_m > 0
            else 0.0
        ),
        outage_transition_latency_s=outage_transition_latency_s,
    )
