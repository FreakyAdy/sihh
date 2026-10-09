# ML and dataset baseline

This zone converts permitted vehicle traces into the frozen `shared/idr`
contract and provides a classical reference before learned corrections are
introduced.

## CSV conversion

IO-VNBD exports must remain outside Git. Provide an explicit column mapping
because dataset releases and local exports may use different names:

```python
from idr_ml.io_vnbd import ColumnMap, read_csv_sessions

sessions = read_csv_sessions(
    "data/iovnbd/session.csv",
    ColumnMap(
        timestamp="timestamp_s",
        forward_acceleration="accel_forward_mps2",
        yaw_rate="gyro_z_rps",
        latitude="latitude_deg",
        longitude="longitude_deg",
        speed="speed_mps",
        session="drive_id",
    ),
)
```

The adapter groups complete drives by session ID. Session-level splitting in
`idr_ml.dataset.split_sessions` must be used to prevent adjacent-window
leakage between training and evaluation.

The current baseline includes robust median acceleration smoothing, shock/gap
quality flags, GNSS-anchored speed estimation, and deterministic splits. It is
not the final learned model.
