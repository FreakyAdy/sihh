from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, TextIO

from idr.models import GnssFix, ImuSample, SensorFrame

from .dataset import SessionTrace

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ColumnMap:
    """Explicit mapping from IO-VNBD CSV column names to shared contract fields.

    Column names vary between IO-VNBD release versions and local exports.
    This dataclass must be filled in by the operator after inspecting the CSV
    header. Do not use guessed or default column names — always inspect first.

    Required fields
    ---------------
    timestamp           : seconds since epoch or session start
    forward_acceleration: longitudinal acceleration (m/s²)
    yaw_rate            : yaw angular rate (rad/s)

    Optional fields
    ---------------
    latitude / longitude: GNSS coordinates in degrees
    speed               : GNSS speed (m/s)
    horizontal_accuracy : GNSS horizontal accuracy (m)
    truth_x / truth_y   : ground-truth local position (m), if available
    session             : session identifier column (groups rows into sessions)
    """

    timestamp: str
    forward_acceleration: str
    yaw_rate: str
    latitude: str | None = None
    longitude: str | None = None
    speed: str | None = None
    horizontal_accuracy: str | None = None
    truth_x: str | None = None
    truth_y: str | None = None
    session: str | None = None


def read_csv_sessions(
    source: str | Path | TextIO,
    columns: ColumnMap,
) -> list[SessionTrace]:
    """Convert a CSV export into contract-compliant session traces.

    The mapping is explicit because IO-VNBD releases and local exports may use
    different column names.  Source data must remain outside the repository.

    Raises
    ------
    ValueError
        If any configured column (required or optional) is absent from the CSV
        header, or if a session's timestamps are not monotonically increasing.
    """
    stream, should_close = _open_source(source)
    try:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("CSV source must contain a header row")

        # Validate ALL configured columns — not just the three required ones.
        # Missing optional columns are a misconfiguration, not a silent fallback.
        all_configured: list[str] = [
            v for v in (
                columns.timestamp,
                columns.forward_acceleration,
                columns.yaw_rate,
                columns.latitude,
                columns.longitude,
                columns.speed,
                columns.horizontal_accuracy,
                columns.truth_x,
                columns.truth_y,
                columns.session,
            )
            if v is not None
        ]
        missing = [name for name in all_configured if name not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"CSV source is missing configured columns: {', '.join(sorted(missing))}. "
                "Inspect the CSV header and update the ColumnMap."
            )

        grouped: dict[str, list[SensorFrame]] = {}
        row_counts: dict[str, int] = {}
        gnss_counts: dict[str, int] = {}

        for line_number, row in enumerate(reader, start=2):
            try:
                frame = _row_to_frame(row, columns)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"invalid IO-VNBD row on line {line_number}: {error}"
                ) from error

            session_id = (
                row.get(columns.session, "default")
                if columns.session
                else "default"
            )
            if not session_id:
                raise ValueError(f"empty session ID on line {line_number}")

            grouped.setdefault(session_id, []).append(frame)
            row_counts[session_id] = row_counts.get(session_id, 0) + 1
            if frame.gnss is not None:
                gnss_counts[session_id] = gnss_counts.get(session_id, 0) + 1

        sessions: list[SessionTrace] = []
        for session_id, frames in grouped.items():
            # Validate monotonic timestamps; reject rather than silently sort.
            for prev, curr in zip(frames, frames[1:]):
                if curr.imu.timestamp_s <= prev.imu.timestamp_s:
                    raise ValueError(
                        f"session {session_id!r} contains non-monotonic timestamps: "
                        f"{prev.imu.timestamp_s} followed by {curr.imu.timestamp_s}. "
                        "Sort the CSV by timestamp before ingestion."
                    )

            total = row_counts[session_id]
            gnss = gnss_counts.get(session_id, 0)
            truth = sum(
                1 for f in frames
                if f.truth_x_m is not None and f.truth_y_m is not None
            )
            gnss_frac = gnss / total if total else 0.0
            truth_frac = truth / total if total else 0.0
            logger.info(
                "Session %r: %d frames, GNSS coverage %.1f%%, truth coverage %.1f%%",
                session_id, total, gnss_frac * 100, truth_frac * 100,
            )
            if gnss_frac < 0.05:
                logger.warning(
                    "Session %r has very low GNSS coverage (%.1f%%). "
                    "Engine initialization may fail.",
                    session_id, gnss_frac * 100,
                )

            sessions.append(SessionTrace(session_id, tuple(frames)))

        return sessions
    finally:
        if should_close:
            stream.close()


def _row_to_frame(row: Mapping[str, str], columns: ColumnMap) -> SensorFrame:
    timestamp = _required_float(row, columns.timestamp)
    gnss = None
    if (
        columns.latitude
        and columns.longitude
        and row.get(columns.latitude, "").strip()
        and row.get(columns.longitude, "").strip()
    ):
        gnss = GnssFix(
            timestamp_s=timestamp,
            latitude_deg=_required_float(row, columns.latitude),
            longitude_deg=_required_float(row, columns.longitude),
            speed_mps=_optional_float(row, columns.speed),
            horizontal_accuracy_m=_optional_float(row, columns.horizontal_accuracy),
        )
    return SensorFrame(
        imu=ImuSample(
            timestamp_s=timestamp,
            forward_acceleration_mps2=_required_float(row, columns.forward_acceleration),
            yaw_rate_rps=_required_float(row, columns.yaw_rate),
        ),
        gnss=gnss,
        truth_x_m=_optional_float(row, columns.truth_x),
        truth_y_m=_optional_float(row, columns.truth_y),
    )


def _required_float(row: Mapping[str, str], column: str) -> float:
    value = row[column].strip()
    if not value:
        raise ValueError(f"column {column!r} is empty")
    return float(value)


def _optional_float(row: Mapping[str, str], column: str | None) -> float | None:
    if column is None or not row.get(column, "").strip():
        return None
    return float(row[column])


def _open_source(source: str | Path | TextIO) -> tuple[TextIO, bool]:
    if hasattr(source, "read"):
        return source, False  # type: ignore[return-value]
    return Path(source).open("r", encoding="utf-8", newline=""), True
