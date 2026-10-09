"""Shared contracts and deterministic replay primitives for the IDR system."""

from .models import GnssFix, ImuSample, NavigationState, SensorFrame
from .replay import DeadReckoningReplay
from .scenarios import ScenarioResult, ScenarioStatus, run_scenario
from .synthetic import straight_line_trace
from .trace import frame_from_dict, frame_to_dict, read_jsonl, write_jsonl

__all__ = [
    "DeadReckoningReplay",
    "GnssFix",
    "ImuSample",
    "NavigationState",
    "ScenarioResult",
    "ScenarioStatus",
    "SensorFrame",
    "frame_from_dict",
    "frame_to_dict",
    "read_jsonl",
    "straight_line_trace",
    "write_jsonl",
    "run_scenario",
]
