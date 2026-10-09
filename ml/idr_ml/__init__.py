"""Dataset and classical signal-processing baseline for IDR."""

from .baseline import BaselineOutput, estimate_forward_speed
from .dataset import SessionTrace, load_session, split_sessions
from .io_vnbd import ColumnMap, read_csv_sessions
from .quality import QualityFlag, assess_quality, smooth_acceleration

__all__ = [
    "BaselineOutput",
    "ColumnMap",
    "QualityFlag",
    "SessionTrace",
    "assess_quality",
    "estimate_forward_speed",
    "load_session",
    "read_csv_sessions",
    "smooth_acceleration",
    "split_sessions",
]
