from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

from .models import NavigationMode, NavigationState, SensorFrame


@dataclass(frozen=True)
class ReplayMetrics:
    sample_count: int
    duration_s: float
    update_rate_hz: float
    max_position_error_m: float
    travelled_distance_m: float
    drift_percent: float
    outage_transition_latency_s: float | None
    recovery_timestamp_s: float | None

    @property
    def meets_drift_target(self) -> bool:
        return self.drift_percent < 10.0

    @property
    def meets_mobile_rate_target(self) -> bool:
        return self.update_rate_hz >= 10.0


@dataclass(frozen=True)
class OutageMetrics:
    """Position error statistics computed *only* inside the GNSS-denied window.

    Using the full session to compute drift dilutes (or inflates) the outage
    error because pre- and post-outage frames have GNSS correction. This
    dataclass encapsulates the correct calculation so every caller uses the
    same definition.
    """

    outage_start_s: float
    outage_end_s: float
    covered_distance_m: float
    truth_coverage_fraction: float   # fraction of outage frames that have truth labels
    max_error_m: float
    median_error_m: float
    p90_error_m: float
    drift_percent: float             # max_error_m / covered_distance_m * 100

    @property
    def meets_drift_target(self) -> bool:
        """True when drift is below the SIH 10 % threshold."""
        return self.drift_percent < 10.0

    @property
    def has_adequate_truth_coverage(self) -> bool:
        """True when at least 80 % of outage frames carry ground-truth labels."""
        return self.truth_coverage_fraction >= 0.8


def measure_outage(
    frames: Sequence[SensorFrame],
    states: Sequence[NavigationState],
    outage_start_s: float,
    outage_end_s: float,
) -> OutageMetrics | None:
    """Compute position-error statistics restricted to the GNSS-denied window.

    Returns ``None`` when there are no truth-labelled frames inside the window
    or when the ground-truth path length is zero (e.g. stationary vehicle).

    Parameters
    ----------
    frames:
        Ordered sensor frames fed to the estimator.
    states:
        Corresponding navigation states (same length as *frames*).
    outage_start_s:
        Timestamp at which GNSS masking begins.
    outage_end_s:
        Timestamp at which GNSS masking ends.
    """
    if len(frames) != len(states):
        raise ValueError("frames and states must have equal length")

    outage_pairs = [
        (frame, state)
        for frame, state in zip(frames, states)
        if outage_start_s <= frame.imu.timestamp_s <= outage_end_s
    ]
    if not outage_pairs:
        return None

    truth_frames = [
        (frame, state) for frame, state in outage_pairs
        if frame.truth_x_m is not None and frame.truth_y_m is not None
    ]
    truth_coverage = len(truth_frames) / len(outage_pairs)

    errors = [
        math.hypot(state.x_m - frame.truth_x_m, state.y_m - frame.truth_y_m)
        for frame, state in truth_frames
    ]
    if not errors:
        return None

    # Ground-truth path length inside the outage window only
    covered_distance_m = sum(
        math.hypot(b.truth_x_m - a.truth_x_m, b.truth_y_m - a.truth_y_m)
        for (a, _), (b, _) in zip(truth_frames, truth_frames[1:])
    )
    if covered_distance_m <= 0.0:
        return None

    sorted_errors = sorted(errors)
    p90_index = min(len(sorted_errors) - 1, int(len(sorted_errors) * 0.9))

    return OutageMetrics(
        outage_start_s=outage_start_s,
        outage_end_s=outage_end_s,
        covered_distance_m=covered_distance_m,
        truth_coverage_fraction=truth_coverage,
        max_error_m=max(errors),
        median_error_m=statistics.median(sorted_errors),
        p90_error_m=sorted_errors[p90_index],
        drift_percent=max(errors) / covered_distance_m * 100.0,
    )


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
    outage_start = next(
        (frame.imu.timestamp_s for frame in frames if frame.gnss is None),
        None,
    )
    dead_reckoning_timestamp = next(
        (
            state.timestamp_s
            for frame, state in zip(frames, states)
            if frame.gnss is None and state.mode == NavigationMode.DEAD_RECKONING
        ),
        None,
    )
    recovery_timestamp = next(
        (
            state.timestamp_s
            for index, state in enumerate(states)
            if index > 0
            and state.mode == NavigationMode.GNSS_AIDED
            and states[index - 1].mode == NavigationMode.DEAD_RECKONING
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
        outage_transition_latency_s=(
            dead_reckoning_timestamp - outage_start
            if dead_reckoning_timestamp is not None and outage_start is not None
            else None
        ),
        recovery_timestamp_s=recovery_timestamp,
    )
