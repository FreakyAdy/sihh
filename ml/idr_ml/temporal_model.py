from __future__ import annotations

from dataclasses import dataclass
import json
from math import sqrt
from pathlib import Path
from typing import Sequence, TextIO

from idr.models import SensorFrame


FEATURE_NAMES = (
    "bias",
    "mean_forward_acceleration_mps2",
    "acceleration_std_mps2",
    "mean_absolute_acceleration_mps2",
    "mean_yaw_rate_rps",
    "yaw_rate_std_rps",
)


@dataclass(frozen=True)
class TemporalPrediction:
    speed_mps: float
    vibration_probability: float


@dataclass(frozen=True)
class TemporalSpeedModel:
    speed_weights: tuple[float, ...]
    vibration_weights: tuple[float, ...]
    window_size: int = 11
    version: str = "temporal-statistical-0.1.0"

    def __post_init__(self) -> None:
        if len(self.speed_weights) != len(FEATURE_NAMES):
            raise ValueError("speed weights must match feature names")
        if len(self.vibration_weights) != len(FEATURE_NAMES):
            raise ValueError("vibration weights must match feature names")
        if self.window_size < 3 or self.window_size % 2 == 0:
            raise ValueError("window_size must be an odd value of at least three")

    def predict(self, frames: Sequence[SensorFrame]) -> TemporalPrediction:
        features = extract_window_features(frames, self.window_size)
        speed = max(0.0, _dot(self.speed_weights, features))
        vibration = _sigmoid(_dot(self.vibration_weights, features))
        return TemporalPrediction(speed, vibration)

    def to_dict(self) -> dict[str, object]:
        return {
            "model_type": "temporal_statistical_speed_vibration",
            "version": self.version,
            "window_size": self.window_size,
            "feature_names": list(FEATURE_NAMES),
            "speed_weights": list(self.speed_weights),
            "vibration_weights": list(self.vibration_weights),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TemporalSpeedModel:
        if payload.get("model_type") != "temporal_statistical_speed_vibration":
            raise ValueError("unsupported temporal model type")
        names = tuple(str(name) for name in payload["feature_names"])
        if names != FEATURE_NAMES:
            raise ValueError("temporal model feature schema does not match runtime")
        return cls(
            speed_weights=tuple(float(value) for value in payload["speed_weights"]),
            vibration_weights=tuple(float(value) for value in payload["vibration_weights"]),
            window_size=int(payload["window_size"]),
            version=str(payload["version"]),
        )

    def save(self, destination: str | Path | TextIO) -> None:
        stream, close = _open(destination, "w")
        try:
            json.dump(self.to_dict(), stream, separators=(",", ":"))
        finally:
            if close:
                stream.close()


def extract_window_features(
    frames: Sequence[SensorFrame],
    window_size: int,
) -> tuple[float, ...]:
    if len(frames) != window_size:
        raise ValueError("frame count must equal model window_size")
    acceleration = [frame.imu.forward_acceleration_mps2 for frame in frames]
    yaw = [frame.imu.yaw_rate_rps for frame in frames]
    return (
        1.0,
        sum(acceleration) / window_size,
        _standard_deviation(acceleration),
        sum(abs(value) for value in acceleration) / window_size,
        sum(yaw) / window_size,
        _standard_deviation(yaw),
    )


def train_temporal_speed_model(
    frames: Sequence[SensorFrame],
    *,
    window_size: int = 11,
    vibration_threshold_mps2: float = 4.0,
    ridge: float = 1e-6,
) -> TemporalSpeedModel:
    if len(frames) < window_size:
        raise ValueError("at least one complete model window is required")
    if vibration_threshold_mps2 <= 0.0 or ridge < 0.0:
        raise ValueError("vibration threshold must be positive and ridge non-negative")
    samples: list[tuple[tuple[float, ...], float, float]] = []
    half = window_size // 2
    for center in range(half, len(frames) - half):
        window = frames[center - half : center + half + 1]
        speed = frames[center].gnss.speed_mps if frames[center].gnss else None
        if speed is None:
            continue
        features = extract_window_features(window, window_size)
        vibration = min(
            1.0,
            max(abs(frame.imu.forward_acceleration_mps2) for frame in window)
            / vibration_threshold_mps2,
        )
        samples.append((features, speed, vibration))
    if len(samples) < len(FEATURE_NAMES):
        raise ValueError("at least six GNSS-labelled windows are required")
    speed_weights = _fit_ridge([(features, speed) for features, speed, _ in samples], ridge)
    vibration_weights = _fit_ridge(
        [(features, _logit(vibration)) for features, _, vibration in samples],
        ridge,
    )
    return TemporalSpeedModel(tuple(speed_weights), tuple(vibration_weights), window_size)


def _fit_ridge(samples: Sequence[tuple[tuple[float, ...], float]], ridge: float) -> list[float]:
    size = len(FEATURE_NAMES)
    gram = [[0.0] * size for _ in range(size)]
    target = [0.0] * size
    for features, label in samples:
        for row in range(size):
            target[row] += features[row] * label
            for column in range(size):
                gram[row][column] += features[row] * features[column]
    for index in range(size):
        gram[index][index] += ridge
    from .model import _solve_linear_system

    return _solve_linear_system(gram, target)


def _standard_deviation(values: Sequence[float]) -> float:
    mean = sum(values) / len(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        scale = 2.718281828459045 ** -value
        return 1.0 / (1.0 + scale)
    scale = 2.718281828459045 ** value
    return scale / (1.0 + scale)


def _logit(value: float) -> float:
    bounded = min(1.0 - 1e-6, max(1e-6, value))
    from math import log

    return log(bounded / (1.0 - bounded))


def _open(value: str | Path | TextIO, mode: str) -> tuple[TextIO, bool]:
    if hasattr(value, "read") or hasattr(value, "write"):
        return value, False  # type: ignore[return-value]
    return Path(value).open(mode, encoding="utf-8"), True
