from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence, TextIO

from idr.models import SensorFrame


FEATURE_NAMES = (
    "bias",
    "forward_acceleration_mps2",
    "yaw_rate_rps",
    "absolute_acceleration_mps2",
)


def extract_features(frame: SensorFrame) -> tuple[float, ...]:
    acceleration = frame.imu.forward_acceleration_mps2
    return (
        1.0,
        acceleration,
        frame.imu.yaw_rate_rps,
        abs(acceleration),
    )


@dataclass(frozen=True)
class SpeedCorrectionModel:
    """Small deterministic linear model for on-device speed estimation.

    It is intentionally a transparent baseline. The exported schema can later
    be replaced by a TFLite/ONNX model without changing the input contract.
    """

    weights: tuple[float, ...]
    feature_names: tuple[str, ...] = FEATURE_NAMES
    version: str = "0.1.0"

    def __post_init__(self) -> None:
        if len(self.weights) != len(self.feature_names):
            raise ValueError("weights and feature_names must have equal length")
        if not self.weights:
            raise ValueError("model must contain at least one weight")

    def predict(self, frame: SensorFrame) -> float:
        features = extract_features(frame)
        return max(0.0, sum(weight * value for weight, value in zip(self.weights, features)))

    def to_dict(self) -> dict[str, object]:
        return {
            "model_type": "linear_speed_correction",
            "version": self.version,
            "feature_names": list(self.feature_names),
            "weights": list(self.weights),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SpeedCorrectionModel:
        if payload.get("model_type") != "linear_speed_correction":
            raise ValueError("unsupported model_type")
        raw_names = payload.get("feature_names")
        raw_weights = payload.get("weights")
        version = payload.get("version")
        if not isinstance(raw_names, list) or not isinstance(raw_weights, list):
            raise ValueError("model feature_names and weights must be arrays")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("model version must be a non-empty string")
        names = tuple(str(name) for name in raw_names)
        weights = tuple(float(weight) for weight in raw_weights)
        if names != FEATURE_NAMES:
            raise ValueError("model feature_names do not match the runtime contract")
        if not all(weight == weight and abs(weight) != float("inf") for weight in weights):
            raise ValueError("model weights must be finite")
        return cls(weights=weights, feature_names=names, version=version)

    def save(self, destination: str | Path | TextIO) -> None:
        stream, should_close = _open(destination, "w")
        try:
            json.dump(self.to_dict(), stream, separators=(",", ":"))
        finally:
            if should_close:
                stream.close()

    @classmethod
    def load(cls, source: str | Path | TextIO) -> SpeedCorrectionModel:
        stream, should_close = _open(source, "r")
        try:
            return cls.from_dict(json.load(stream))
        finally:
            if should_close:
                stream.close()


def train_speed_model(
    frames: Sequence[SensorFrame],
    ridge: float = 1e-6,
) -> SpeedCorrectionModel:
    """Fit a ridge-regularized linear model on frames with GNSS speed labels."""

    if ridge < 0.0:
        raise ValueError("ridge must be non-negative")
    samples = [
        (extract_features(frame), frame.gnss.speed_mps)
        for frame in frames
        if frame.gnss is not None and frame.gnss.speed_mps is not None
    ]
    if len(samples) < len(FEATURE_NAMES):
        raise ValueError("at least four GNSS-labelled frames are required")
    gram = [[0.0 for _ in FEATURE_NAMES] for _ in FEATURE_NAMES]
    target = [0.0 for _ in FEATURE_NAMES]
    for features, label in samples:
        for row in range(len(FEATURE_NAMES)):
            target[row] += features[row] * label
            for column in range(len(FEATURE_NAMES)):
                gram[row][column] += features[row] * features[column]
    for index in range(len(FEATURE_NAMES)):
        gram[index][index] += ridge
    return SpeedCorrectionModel(tuple(_solve_linear_system(gram, target)))


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for pivot in range(size):
        pivot_row = max(range(pivot, size), key=lambda index: abs(augmented[index][pivot]))
        if abs(augmented[pivot_row][pivot]) < 1e-12:
            raise ValueError("training features are rank deficient")
        augmented[pivot], augmented[pivot_row] = augmented[pivot_row], augmented[pivot]
        divisor = augmented[pivot][pivot]
        augmented[pivot] = [value / divisor for value in augmented[pivot]]
        for row in range(size):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            augmented[row] = [
                left - factor * right
                for left, right in zip(augmented[row], augmented[pivot])
            ]
    return [augmented[index][-1] for index in range(size)]


def _open(value: str | Path | TextIO, mode: str) -> tuple[TextIO, bool]:
    if hasattr(value, "read") or hasattr(value, "write"):
        return value, False  # type: ignore[return-value]
    return Path(value).open(mode, encoding="utf-8"), True
