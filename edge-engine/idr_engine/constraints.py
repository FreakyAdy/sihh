from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, sin
from typing import Protocol, Sequence

# Coordinate frame convention used throughout this module and by FusionEngine:
#   x = east  (metres)
#   y = north (metres)
#   heading_rad = 0 → east, increasing counter-clockwise (standard math angle)
# OSM segments and any imported map data must be reprojected to this frame
# using the same GNSS origin as the FusionEngine before being passed here.
COORDINATE_FRAME_NOTE = "local ENU: x=east, y=north, heading=math angle (0=east, CCW)"



@dataclass(frozen=True)
class MapConstraint:
    """A bounded road-network correction in the local ENU frame."""

    x_m: float
    y_m: float
    heading_rad: float | None = None
    confidence: float = 1.0


class MapMatcher(Protocol):
    def match(self, x_m: float, y_m: float, heading_rad: float) -> MapConstraint | None:
        """Return a candidate road correction or None when no map match exists."""


class NoOpMapMatcher:
    def match(self, x_m: float, y_m: float, heading_rad: float) -> None:
        return None


@dataclass(frozen=True)
class RoadSegment:
    """A local-map road segment in metres, using x=east and y=north."""

    start_x_m: float
    start_y_m: float
    end_x_m: float
    end_y_m: float
    road_id: str = ""

    def __post_init__(self) -> None:
        if not all(
            value == value and abs(value) != float("inf")
            for value in (
                self.start_x_m,
                self.start_y_m,
                self.end_x_m,
                self.end_y_m,
            )
        ):
            raise ValueError("road segment coordinates must be finite")
        if self.start_x_m == self.end_x_m and self.start_y_m == self.end_y_m:
            raise ValueError("road segment must have non-zero length")


class SegmentMapMatcher:
    """Nearest-road matcher with heading-aware candidate rejection.

    This is intentionally small and deterministic so an offline OSM importer
    can convert its ways into ``RoadSegment`` values without adding a runtime
    dependency. A candidate is accepted only when its cross-track distance and
    heading difference are within configured limits.
    """

    def __init__(
        self,
        segments: Sequence[RoadSegment],
        *,
        max_distance_m: float = 20.0,
        max_heading_error_rad: float = 0.75,
    ) -> None:
        if not segments:
            raise ValueError("at least one road segment is required")
        if max_distance_m <= 0.0:
            raise ValueError("max_distance_m must be positive")
        if not 0.0 < max_heading_error_rad <= 3.141592653589793:
            raise ValueError("max_heading_error_rad must be in (0, pi]")
        self._segments = tuple(segments)
        self._max_distance_m = max_distance_m
        self._max_heading_error_rad = max_heading_error_rad

    def match(self, x_m: float, y_m: float, heading_rad: float) -> MapConstraint | None:
        best: tuple[float, MapConstraint] | None = None
        for segment in self._segments:
            dx = segment.end_x_m - segment.start_x_m
            dy = segment.end_y_m - segment.start_y_m
            length_squared = dx * dx + dy * dy
            projection = (
                (x_m - segment.start_x_m) * dx + (y_m - segment.start_y_m) * dy
            ) / length_squared
            projection = max(0.0, min(1.0, projection))
            candidate_x = segment.start_x_m + projection * dx
            candidate_y = segment.start_y_m + projection * dy
            distance = ((candidate_x - x_m) ** 2 + (candidate_y - y_m) ** 2) ** 0.5
            if distance > self._max_distance_m:
                continue
            segment_heading = atan2(dy, dx)
            heading_error = abs(
                atan2(sin(segment_heading - heading_rad), cos(segment_heading - heading_rad))
            )
            if heading_error > self._max_heading_error_rad:
                continue
            candidate = MapConstraint(
                candidate_x,
                candidate_y,
                heading_rad=segment_heading,
                confidence=max(0.0, 1.0 - distance / self._max_distance_m),
            )
            if best is None or distance < best[0]:
                best = (distance, candidate)
        return None if best is None else best[1]


class HmmMapMatcher(SegmentMapMatcher):
    """Small Viterbi matcher over road segments with graph transitions.

    ``connectivity`` maps a segment index to the indices reachable on the
    next sample. Candidates use the same distance and heading emission gates
    as ``SegmentMapMatcher``; the sequence solver adds transition continuity.
    """

    def __init__(
        self,
        segments: Sequence[RoadSegment],
        connectivity: dict[int, Sequence[int]],
        *,
        max_distance_m: float = 20.0,
        max_heading_error_rad: float = 0.75,
    ) -> None:
        super().__init__(
            segments,
            max_distance_m=max_distance_m,
            max_heading_error_rad=max_heading_error_rad,
        )
        self._segments = tuple(segments)
        self._connectivity = {
            index: tuple(neighbors) for index, neighbors in connectivity.items()
        }

    def match_sequence(
        self,
        observations: Sequence[tuple[float, float, float]],
    ) -> list[MapConstraint | None]:
        if not observations:
            return []
        layers: list[dict[int, tuple[float, int | None, MapConstraint]]] = []
        for x_m, y_m, heading_rad in observations:
            candidates: dict[int, tuple[float, MapConstraint]] = {}
            for index, segment in enumerate(self._segments):
                candidate = self._candidate(segment, x_m, y_m, heading_rad)
                if candidate is not None:
                    candidates[index] = candidate
            if not candidates:
                layers.append({})
                continue
            previous = layers[-1] if layers else {}
            current: dict[int, tuple[float, int | None, MapConstraint]] = {}
            for index, (emission, candidate) in candidates.items():
                if not previous:
                    current[index] = (emission, None, candidate)
                    continue
                options = [
                    (score + emission + self._transition_penalty(previous_index, index),
                     previous_index)
                    for previous_index, (score, _, _) in previous.items()
                    if index in self._connectivity.get(previous_index, ())
                ]
                if options:
                    score, previous_index = min(options)
                    current[index] = (score, previous_index, candidate)
            layers.append(current)
        if any(not layer for layer in layers):
            return [None for _ in observations]
        last_index = min(layers[-1], key=lambda index: layers[-1][index][0])
        result: list[MapConstraint | None] = [None] * len(layers)
        for layer_index in range(len(layers) - 1, -1, -1):
            score, previous_index, candidate = layers[layer_index][last_index]
            result[layer_index] = candidate
            if previous_index is None:
                break
            last_index = previous_index
        return result

    def _candidate(
        self,
        segment: RoadSegment,
        x_m: float,
        y_m: float,
        heading_rad: float,
    ) -> tuple[float, MapConstraint] | None:
        dx = segment.end_x_m - segment.start_x_m
        dy = segment.end_y_m - segment.start_y_m
        length_squared = dx * dx + dy * dy
        projection = max(
            0.0,
            min(
                1.0,
                ((x_m - segment.start_x_m) * dx + (y_m - segment.start_y_m) * dy)
                / length_squared,
            ),
        )
        candidate_x = segment.start_x_m + projection * dx
        candidate_y = segment.start_y_m + projection * dy
        distance = ((candidate_x - x_m) ** 2 + (candidate_y - y_m) ** 2) ** 0.5
        segment_heading = atan2(dy, dx)
        heading_error = abs(
            atan2(sin(segment_heading - heading_rad), cos(segment_heading - heading_rad))
        )
        if distance > self._max_distance_m or heading_error > self._max_heading_error_rad:
            return None
        return (
            distance + heading_error * self._max_distance_m,
            MapConstraint(
                candidate_x,
                candidate_y,
                heading_rad=segment_heading,
                confidence=max(0.0, 1.0 - distance / self._max_distance_m),
            ),
        )

    def _transition_penalty(self, previous_index: int, index: int) -> float:
        return 0.0 if previous_index == index else 1.0


class StreamingHmmMatcher:
    """Adapts :class:`HmmMapMatcher` for per-sample streaming calls.

    ``HmmMapMatcher.match_sequence()`` operates on a full observation sequence,
    but ``FusionEngine._apply_map_constraint()`` calls the ``MapMatcher``
    protocol's :meth:`match` once per sample.  This class bridges the gap by
    maintaining a sliding observation window and calling ``match_sequence()``
    on each new sample, returning only the last element of the result.

    The map coordinate frame must be the same local ENU frame used by the
    fusion engine (x=east, y=north).  See ``COORDINATE_FRAME_NOTE``.

    Parameters
    ----------
    hmm:
        A configured :class:`HmmMapMatcher` with road segments and connectivity.
    window:
        Maximum number of recent observations kept in the sliding buffer.
        Larger windows produce smoother sequence matching but increase latency.
    min_window:
        Minimum buffer length before returning a result.  Below this threshold
        ``match()`` returns ``None`` to avoid spurious early matches.
    """

    def __init__(
        self,
        hmm: HmmMapMatcher,
        window: int = 20,
        min_window: int = 3,
    ) -> None:
        if window < 1:
            raise ValueError("window must be at least 1")
        if min_window < 1 or min_window > window:
            raise ValueError("min_window must be in [1, window]")
        self._hmm = hmm
        self._window = window
        self._min_window = min_window
        self._buffer: list[tuple[float, float, float]] = []

    def match(self, x_m: float, y_m: float, heading_rad: float) -> MapConstraint | None:
        """Accept one sample and return a map constraint, or ``None``."""
        self._buffer.append((x_m, y_m, heading_rad))
        if len(self._buffer) > self._window:
            self._buffer.pop(0)
        if len(self._buffer) < self._min_window:
            return None
        try:
            candidates = self._hmm.match_sequence(self._buffer)
        except Exception:
            # Defensive: never let the matcher crash the navigation loop.
            return None
        return candidates[-1] if candidates else None


def blend_map_constraint(
    x_m: float,
    y_m: float,
    heading_rad: float,
    constraint: MapConstraint,
    gain: float,
) -> tuple[float, float, float]:
    if not 0.0 <= gain <= 1.0:
        raise ValueError("map correction gain must be between 0 and 1")
    confidence = max(0.0, min(1.0, constraint.confidence))
    effective_gain = gain * confidence
    corrected_x = x_m + (constraint.x_m - x_m) * effective_gain
    corrected_y = y_m + (constraint.y_m - y_m) * effective_gain
    if constraint.heading_rad is None:
        corrected_heading = heading_rad
    else:
        delta = atan2(sin(constraint.heading_rad - heading_rad), cos(constraint.heading_rad - heading_rad))
        corrected_heading = heading_rad + delta * effective_gain
    return corrected_x, corrected_y, corrected_heading
