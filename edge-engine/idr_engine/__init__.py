"""Platform-neutral GNSS/INS fusion engine."""

from .fusion import (
    FusionConfig,
    FusionCorrection,
    FusionCorrectionModel,
    FusionEngine,
    LinearFusionCorrection,
    NoOpFusionCorrection,
)
from .adapters import frame_from_external
from .constraints import (
    MapConstraint,
    MapMatcher,
    NoOpMapMatcher,
    RoadSegment,
    SegmentMapMatcher,
    HmmMapMatcher,
)

__all__ = [
    "FusionConfig",
    "FusionEngine",
    "FusionCorrection",
    "FusionCorrectionModel",
    "LinearFusionCorrection",
    "NoOpFusionCorrection",
    "MapConstraint",
    "MapMatcher",
    "NoOpMapMatcher",
    "RoadSegment",
    "SegmentMapMatcher",
    "HmmMapMatcher",
    "frame_from_external",
]
