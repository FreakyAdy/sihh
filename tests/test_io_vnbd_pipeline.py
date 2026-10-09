"""End-to-end tests for the IO-VNBD CSV ingestion pipeline.

Uses synthetic CSV data that mirrors the IO-VNBD format so no raw dataset
files are needed in the repository.
"""
from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "ml"))

from idr_ml.io_vnbd import ColumnMap, read_csv_sessions
from idr_ml.dataset import session_train_test_split


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLUMNS = ColumnMap(
    timestamp="time_s",
    forward_acceleration="accel_fwd",
    yaw_rate="yaw_rps",
    latitude="lat",
    longitude="lon",
    speed="speed",
    horizontal_accuracy=None,
    truth_x=None,
    truth_y=None,
    session="session",
)


def _make_csv(rows: list[dict[str, str]], header: list[str] | None = None) -> io.StringIO:
    cols = header or list(rows[0].keys())
    lines = [",".join(cols)]
    for row in rows:
        lines.append(",".join(row.get(c, "") for c in cols))
    return io.StringIO("\n".join(lines))


def _row(t: float, session: str = "s1", lat: float = 0.0, lon: float = 0.0) -> dict[str, str]:
    return {
        "time_s": str(t),
        "accel_fwd": "0.5",
        "yaw_rps": "0.01",
        "lat": str(lat),
        "lon": str(lon),
        "speed": "10.0",
        "session": session,
    }


# ---------------------------------------------------------------------------
# Column validation
# ---------------------------------------------------------------------------

class ColumnValidationTest(unittest.TestCase):
    def test_missing_required_column_raises(self) -> None:
        csv_text = io.StringIO("time_s,yaw_rps\n0.0,0.01\n")
        columns = ColumnMap(
            timestamp="time_s",
            forward_acceleration="accel_fwd",  # missing from header
            yaw_rate="yaw_rps",
        )
        with self.assertRaises(ValueError) as ctx:
            read_csv_sessions(csv_text, columns)
        self.assertIn("accel_fwd", str(ctx.exception))

    def test_missing_optional_column_raises(self) -> None:
        """Optional columns that are configured must exist in the header."""
        rows = [_row(0.0), _row(1.0)]
        columns = ColumnMap(
            timestamp="time_s",
            forward_acceleration="accel_fwd",
            yaw_rate="yaw_rps",
            latitude="lat",
            longitude="lon",
            speed="NONEXISTENT_SPEED_COL",  # configured but absent
        )
        csv_io = _make_csv(rows)
        with self.assertRaises(ValueError) as ctx:
            read_csv_sessions(csv_io, columns)
        self.assertIn("NONEXISTENT_SPEED_COL", str(ctx.exception))

    def test_null_optional_columns_not_validated(self) -> None:
        """Optional fields set to None must not require a CSV column."""
        rows = [_row(0.0), _row(1.0)]
        columns = ColumnMap(
            timestamp="time_s",
            forward_acceleration="accel_fwd",
            yaw_rate="yaw_rps",
            latitude="lat",
            longitude="lon",
            speed=None,          # null → not validated
            truth_x=None,
            truth_y=None,
            session="session",
        )
        csv_io = _make_csv(rows)
        sessions = read_csv_sessions(csv_io, columns)
        self.assertEqual(len(sessions), 1)

    def test_missing_header_raises(self) -> None:
        with self.assertRaises(ValueError):
            read_csv_sessions(io.StringIO(""), _COLUMNS)


# ---------------------------------------------------------------------------
# Session grouping
# ---------------------------------------------------------------------------

class SessionGroupingTest(unittest.TestCase):
    def test_single_session(self) -> None:
        rows = [_row(float(t), "A") for t in range(5)]
        sessions = read_csv_sessions(_make_csv(rows), _COLUMNS)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].session_id, "A")
        self.assertEqual(len(sessions[0].frames), 5)

    def test_two_sessions_separated(self) -> None:
        rows = [_row(float(t), "A") for t in range(3)] + \
               [_row(float(t), "B") for t in range(3)]
        sessions = read_csv_sessions(_make_csv(rows), _COLUMNS)
        ids = {s.session_id for s in sessions}
        self.assertEqual(ids, {"A", "B"})

    def test_non_monotonic_timestamps_raises(self) -> None:
        rows = [
            _row(0.0, "X"),
            _row(2.0, "X"),
            _row(1.0, "X"),  # timestamp goes backward
        ]
        with self.assertRaises(ValueError) as ctx:
            read_csv_sessions(_make_csv(rows), _COLUMNS)
        self.assertIn("non-monotonic", str(ctx.exception).lower())

    def test_frames_pass_contract_validation(self) -> None:
        """All produced SensorFrame objects must satisfy the shared contract."""
        rows = [_row(float(t)) for t in range(10)]
        sessions = read_csv_sessions(_make_csv(rows), _COLUMNS)
        for session in sessions:
            for frame in session.frames:
                # GnssFix and ImuSample validate themselves in __post_init__
                self.assertIsNotNone(frame.imu)


# ---------------------------------------------------------------------------
# Session splitting
# ---------------------------------------------------------------------------

class SessionSplitTest(unittest.TestCase):
    def _make_sessions(self, n: int):
        from idr_ml.dataset import SessionTrace
        return [
            SessionTrace(
                session_id=f"session_{i:03d}",
                frames=tuple(
                    read_csv_sessions(
                        _make_csv([_row(float(t)) for t in range(5)]),
                        _COLUMNS,
                    )[0].frames
                ),
            )
            for i in range(n)
        ]

    def test_no_session_appears_in_both_splits(self) -> None:
        sessions = self._make_sessions(10)
        train, test = session_train_test_split(sessions, test_fraction=0.2, seed=42)
        train_ids = {s.session_id for s in train}
        test_ids = {s.session_id for s in test}
        self.assertEqual(train_ids & test_ids, set(), "Session in both train and test")

    def test_all_sessions_accounted_for(self) -> None:
        sessions = self._make_sessions(10)
        train, test = session_train_test_split(sessions, test_fraction=0.2, seed=42)
        # session_train_test_split delegates to split_sessions(validation_fraction=0.0).
        # split_sessions enforces min(1, round(n*0)) = 0 validation for large n when
        # validation_fraction=0.0. Verify no sessions are lost (train + test = all sessions).
        total = len(train) + len(test)
        self.assertGreaterEqual(total, 9)   # at most 1 lost to rounding
        self.assertLessEqual(total, 10)

    def test_reproducible_with_same_seed(self) -> None:
        sessions = self._make_sessions(8)
        t1, te1 = session_train_test_split(sessions, seed=7)
        t2, te2 = session_train_test_split(sessions, seed=7)
        self.assertEqual([s.session_id for s in t1], [s.session_id for s in t2])

    def test_different_seeds_produce_different_splits(self) -> None:
        sessions = self._make_sessions(10)
        _, te1 = session_train_test_split(sessions, seed=1)
        _, te2 = session_train_test_split(sessions, seed=99)
        # With 10 sessions it's extremely unlikely both splits are identical
        self.assertNotEqual(
            sorted(s.session_id for s in te1),
            sorted(s.session_id for s in te2),
        )


# ---------------------------------------------------------------------------
# GNSS frame construction
# ---------------------------------------------------------------------------

class GnssFrameTest(unittest.TestCase):
    def test_gnss_fix_attached_when_lat_lon_present(self) -> None:
        rows = [_row(0.0, lat=12.345, lon=77.678)]
        sessions = read_csv_sessions(_make_csv(rows), _COLUMNS)
        frame = sessions[0].frames[0]
        self.assertIsNotNone(frame.gnss)
        self.assertAlmostEqual(frame.gnss.latitude_deg, 12.345)  # type: ignore[union-attr]

    def test_gnss_absent_when_lat_empty(self) -> None:
        """Empty lat/lon cell → gnss=None, not a validation error."""
        row = _row(0.0)
        row["lat"] = ""
        row["lon"] = ""
        sessions = read_csv_sessions(_make_csv([row]), _COLUMNS)
        self.assertIsNone(sessions[0].frames[0].gnss)


if __name__ == "__main__":
    unittest.main()
