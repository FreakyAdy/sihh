from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from typing import Iterable, Sequence

from idr.models import SensorFrame
from idr.trace import read_jsonl


@dataclass(frozen=True)
class SessionTrace:
    session_id: str
    frames: tuple[SensorFrame, ...]

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if not self.frames:
            raise ValueError("a session must contain at least one frame")


def load_session(path: str | Path, session_id: str | None = None) -> SessionTrace:
    source = Path(path)
    resolved_id = session_id or source.stem
    return SessionTrace(resolved_id, tuple(read_jsonl(source)))


def split_sessions(
    sessions: Sequence[SessionTrace],
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    seed: int = 42,
) -> tuple[list[SessionTrace], list[SessionTrace], list[SessionTrace]]:
    """Split complete sessions, preventing adjacent-window leakage."""

    if not 0.0 <= validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in [0, 1)")
    if not 0.0 <= test_fraction < 1.0:
        raise ValueError("test_fraction must be in [0, 1)")
    if validation_fraction + test_fraction >= 1.0:
        raise ValueError("validation and test fractions must leave training data")
    if len({session.session_id for session in sessions}) != len(sessions):
        raise ValueError("session IDs must be unique")

    shuffled = list(sessions)
    random.Random(seed).shuffle(shuffled)
    test_count = round(len(shuffled) * test_fraction)
    validation_count = round(len(shuffled) * validation_fraction)
    if len(shuffled) >= 3:
        test_count = max(1, test_count)
        validation_count = max(1, validation_count)
    test = shuffled[:test_count]
    validation = shuffled[test_count : test_count + validation_count]
    train = shuffled[test_count + validation_count :]
    if not train:
        raise ValueError("split leaves no training sessions")
    return train, validation, test


def load_sessions(paths: Iterable[str | Path]) -> list[SessionTrace]:
    return [load_session(path) for path in paths]
