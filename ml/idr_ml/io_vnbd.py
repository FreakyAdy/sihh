from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, TextIO

from idr.models import GnssFix, ImuSample, SensorFrame

from .dataset import SessionTrace


@dataclass(frozen=True)
class ColumnMap:
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
    different column names. Source data remains outside the repository.
    """

    stream, should_close = _open_source(source)
    try:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("CSV source must contain a header")
        required = [columns.timestamp, columns.forward_acceleration, columns.yaw_rate]
        missing = [name for name in required if name not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV source is missing required columns: {', '.join(missing)}")
        grouped: dict[str, list[SensorFrame]] = {}
        for line_number, row in enumerate(reader, start=2):
            try:
                frame = _row_to_frame(row, columns)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"invalid IO-VNBD row on line {line_number}: {error}") from error
            session_id = row.get(columns.session, "default") if columns.session else "default"
            if not session_id:
                raise ValueError(f"empty session ID on line {line_number}")
            grouped.setdefault(session_id, []).append(frame)
        return [SessionTrace(session_id, tuple(frames)) for session_id, frames in grouped.items()]
    finally:
        if should_close:
            stream.close()


def _row_to_frame(row: Mapping[str, str], columns: ColumnMap) -> SensorFrame:
    timestamp = _required_float(row, columns.timestamp)
    gnss = None
    if columns.latitude and columns.longitude and row.get(columns.latitude) and row.get(columns.longitude):
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
