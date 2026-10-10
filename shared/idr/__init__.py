"""Shared contracts and deterministic replay primitives for the IDR system."""

from .models import GnssFix, ImuSample, NavigationState, SensorFrame
from .benchmark import BenchmarkReport, certify_replay
from .replay import DeadReckoningReplay
from .scenarios import ScenarioResult, ScenarioStatus, run_scenario
from .synthetic import straight_line_trace
from .trace import frame_from_dict, frame_to_dict, read_jsonl, write_jsonl
from .throughput import ThroughputReport, measure_throughput
from .rag import IdrKnowledgeBase, IdrRagEngine, IdrRetriever, KnowledgeChunk, RagResponse

__all__ = [
    "DeadReckoningReplay",
    "BenchmarkReport",
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
    "certify_replay",
    "ThroughputReport",
    "measure_throughput",
    "IdrKnowledgeBase",
    "IdrRagEngine",
    "IdrRetriever",
    "KnowledgeChunk",
    "RagResponse",
]
