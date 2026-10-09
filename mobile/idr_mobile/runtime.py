from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Deque, Optional

from idr.models import GnssFix, ImuSample, NavigationState, SensorFrame
from idr_engine import FusionEngine


class RuntimeHealth(StrEnum):
    READY = "ready"
    WAITING_FOR_GNSS = "waiting_for_gnss"
    DROPPED_SAMPLES = "dropped_samples"
    SENSOR_ERROR = "sensor_error"


@dataclass(frozen=True)
class RuntimeSample:
    timestamp_s: float
    forward_acceleration_mps2: float
    yaw_rate_rps: float
    gnss: Optional[GnssFix] = None

    def to_frame(self) -> SensorFrame:
        return SensorFrame(
            imu=ImuSample(
                timestamp_s=self.timestamp_s,
                forward_acceleration_mps2=self.forward_acceleration_mps2,
                yaw_rate_rps=self.yaw_rate_rps,
            ),
            gnss=self.gnss,
        )


@dataclass(frozen=True)
class RuntimeDiagnostics:
    health: RuntimeHealth
    queue_depth: int
    dropped_samples: int
    processed_samples: int
    last_error: str | None


class MobileRuntime:
    """Bounded, lifecycle-friendly runtime facade for a mobile sensor loop.

    Android sensor callbacks should enqueue normalized samples here and drain
    them from a worker thread. The estimator never runs on the UI thread.
    """

    def __init__(self, engine: FusionEngine, max_queue_size: int = 128) -> None:
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be positive")
        self._engine = engine
        self._queue: Deque[RuntimeSample] = deque(maxlen=max_queue_size)
        self._dropped_samples = 0
        self._processed_samples = 0
        self._last_error: str | None = None
        self._started = False

    def start(self) -> None:
        self._started = True
        self._last_error = None

    def stop(self) -> None:
        self._started = False
        self._queue.clear()

    def submit(self, sample: RuntimeSample) -> None:
        if not self._started:
            raise RuntimeError("mobile runtime is not started")
        if len(self._queue) == self._queue.maxlen:
            self._dropped_samples += 1
        self._queue.append(sample)

    def drain(self, limit: int | None = None) -> list[NavigationState]:
        if not self._started:
            raise RuntimeError("mobile runtime is not started")
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive")
        states: list[NavigationState] = []
        while self._queue and (limit is None or len(states) < limit):
            sample = self._queue.popleft()
            try:
                state = self._engine.update(sample.to_frame())
            except (TypeError, ValueError) as error:
                self._last_error = str(error)
                continue
            self._processed_samples += 1
            states.append(state)
        return states

    @property
    def diagnostics(self) -> RuntimeDiagnostics:
        if self._last_error is not None:
            health = RuntimeHealth.SENSOR_ERROR
        elif self._dropped_samples:
            health = RuntimeHealth.DROPPED_SAMPLES
        elif self._processed_samples == 0:
            health = RuntimeHealth.WAITING_FOR_GNSS
        else:
            health = RuntimeHealth.READY
        return RuntimeDiagnostics(
            health=health,
            queue_depth=len(self._queue),
            dropped_samples=self._dropped_samples,
            processed_samples=self._processed_samples,
            last_error=self._last_error,
        )
