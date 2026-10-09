from __future__ import annotations

from typing import Mapping

from idr.models import GnssFix, ImuSample, SensorFrame


def frame_from_external(
    payload: Mapping[str, object],
    *,
    timestamp_key: str = "timestamp_s",
    acceleration_key: str = "forward_acceleration_mps2",
    yaw_rate_key: str = "yaw_rate_rps",
) -> SensorFrame:
    """Adapt a transport-neutral external IMU payload to the shared contract."""

    timestamp = float(payload[timestamp_key])
    imu = ImuSample(
        timestamp_s=timestamp,
        forward_acceleration_mps2=float(payload[acceleration_key]),
        yaw_rate_rps=float(payload[yaw_rate_key]),
    )
    gnss_payload = payload.get("gnss")
    if gnss_payload is None:
        return SensorFrame(imu=imu)
    if not isinstance(gnss_payload, Mapping):
        raise ValueError("gnss payload must be an object")
    gnss = GnssFix(
        timestamp_s=timestamp,
        latitude_deg=float(gnss_payload["latitude_deg"]),
        longitude_deg=float(gnss_payload["longitude_deg"]),
        speed_mps=_optional_float(gnss_payload, "speed_mps"),
        horizontal_accuracy_m=_optional_float(gnss_payload, "horizontal_accuracy_m"),
    )
    return SensorFrame(imu=imu, gnss=gnss)


def _optional_float(payload: Mapping[str, object], key: str) -> float | None:
    value = payload.get(key)
    return None if value is None else float(value)
