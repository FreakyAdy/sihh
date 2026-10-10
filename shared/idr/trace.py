from __future__ import annotations

import json
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
from typing import Iterable, Iterator, Mapping, TextIO

from .models import GnssFix, ImuSample, SensorFrame


def frame_to_dict(frame: SensorFrame) -> dict[str, object]:
    payload: dict[str, object] = {
        "imu": asdict(frame.imu),
        "gnss": asdict(frame.gnss) if frame.gnss is not None else None,
    }
    if frame.truth_x_m is not None:
        payload["truth_x_m"] = frame.truth_x_m
    if frame.truth_y_m is not None:
        payload["truth_y_m"] = frame.truth_y_m
    return payload


def frame_from_dict(payload: Mapping[str, object]) -> SensorFrame:
    imu_payload = _mapping(payload, "imu")
    gnss_payload = payload.get("gnss")
    return SensorFrame(
        imu=ImuSample(**_float_fields(imu_payload, ("timestamp_s", "forward_acceleration_mps2", "yaw_rate_rps"))),
        gnss=(
            GnssFix(
                **_optional_float_fields(
                    _mapping_value(gnss_payload),
                    ("timestamp_s", "latitude_deg", "longitude_deg", "speed_mps", "horizontal_accuracy_m", "bearing_deg"),
                )
            )
            if gnss_payload is not None
            else None
        ),
        truth_x_m=_optional_float(payload, "truth_x_m"),
        truth_y_m=_optional_float(payload, "truth_y_m"),
    )


def write_jsonl(frames: Iterable[SensorFrame], destination: str | Path | TextIO) -> None:
    stream, should_close = _open_destination(destination, "w")
    try:
        previous_timestamp: float | None = None
        for frame in frames:
            timestamp = frame.imu.timestamp_s
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise ValueError("trace timestamps must be strictly increasing")
            previous_timestamp = timestamp
            stream.write(json.dumps(frame_to_dict(frame), separators=(",", ":")) + "\n")
    finally:
        if should_close:
            stream.close()


def read_jsonl(source: str | Path | TextIO) -> Iterator[SensorFrame]:
    stream, should_close = _open_destination(source, "r")
    try:
        previous_timestamp: float | None = None
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                frame = frame_from_dict(json.loads(line))
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(f"invalid trace record on line {line_number}: {error}") from error
            timestamp = frame.imu.timestamp_s
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise ValueError("trace timestamps must be strictly increasing")
            previous_timestamp = timestamp
            yield frame
    finally:
        if should_close:
            stream.close()


def _open_destination(
    value: str | Path | TextIO, mode: str
) -> tuple[TextIO, bool]:
    if hasattr(value, "read") or hasattr(value, "write"):
        return value, False  # type: ignore[return-value]
    return Path(value).open(mode, encoding="utf-8"), True


def _mapping(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    return _mapping_value(payload.get(key))


def _mapping_value(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("expected an object")
    return value


def _float_fields(payload: Mapping[str, object], names: tuple[str, ...]) -> dict[str, float]:
    return {name: float(payload[name]) for name in names}


def _optional_float_fields(
    payload: Mapping[str, object], names: tuple[str, ...]
) -> dict[str, float | None]:
    return {name: _optional_float(payload, name) for name in names}


def _optional_float(payload: Mapping[str, object], name: str) -> float | None:
    value = payload.get(name)
    return None if value is None else float(value)
