from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ThroughputReport:
    sample_count: int
    elapsed_s: float
    update_rate_hz: float
    target_rate_hz: float
    meets_target: bool
    dropped_samples: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "elapsed_s": self.elapsed_s,
            "update_rate_hz": self.update_rate_hz,
            "target_rate_hz": self.target_rate_hz,
            "meets_target": self.meets_target,
            "dropped_samples": self.dropped_samples,
        }


def measure_throughput(
    samples: Iterable[T],
    update: Callable[[T], object],
    *,
    target_rate_hz: float,
    dropped_samples: int = 0,
) -> ThroughputReport:
    if target_rate_hz <= 0.0 or dropped_samples < 0:
        raise ValueError("target rate must be positive and drops non-negative")
    count = 0
    started = perf_counter()
    for sample in samples:
        update(sample)
        count += 1
    elapsed = max(perf_counter() - started, 1e-12)
    rate = count / elapsed
    return ThroughputReport(count, elapsed, rate, target_rate_hz, rate >= target_rate_hz, dropped_samples)
