from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import zlib
from typing import TextIO


PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class RoverTelemetry:
    timestamp_ns: int
    acceleration_x_mps2: float
    acceleration_y_mps2: float
    acceleration_z_mps2: float
    gyro_z_rps: float
    encoder_fl_ticks: int
    encoder_fr_ticks: int
    encoder_rl_ticks: int
    encoder_rr_ticks: int
    motor_left_pwm: int
    motor_right_pwm: int

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")
        if not all(
            isinstance(value, (int, float)) and float(value) == float(value)
            for value in (
                self.acceleration_x_mps2,
                self.acceleration_y_mps2,
                self.acceleration_z_mps2,
                self.gyro_z_rps,
            )
        ):
            raise ValueError("sensor values must be finite")


def encode_json_line(sample: RoverTelemetry) -> str:
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "telemetry": asdict(sample),
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    checksum = zlib.crc32(body.encode("utf-8")) & 0xFFFFFFFF
    return json.dumps({"body": body, "crc32": checksum}, separators=(",", ":")) + "\n"


def decode_json_line(line: str) -> RoverTelemetry:
    envelope = json.loads(line)
    body = str(envelope["body"])
    checksum = int(envelope["crc32"])
    actual = zlib.crc32(body.encode("utf-8")) & 0xFFFFFFFF
    if checksum != actual:
        raise ValueError("rover telemetry CRC mismatch")
    payload = json.loads(body)
    if payload.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("unsupported rover telemetry protocol version")
    return RoverTelemetry(**payload["telemetry"])


def decode_stream(stream: TextIO) -> list[RoverTelemetry]:
    return [decode_json_line(line) for line in stream if line.strip()]
