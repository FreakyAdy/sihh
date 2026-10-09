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
not the final neural model.

## Exported correction model

`idr_ml.model.train_speed_model` fits a small ridge-regularized linear speed
correction model using GNSS speed labels. The artifact is JSON with explicit
feature names, weights, version, and model type:

```python
from idr_ml.model import train_speed_model

model = train_speed_model(session.frames)
model.save("models/speed-correction.json")
```

The runtime uses the same `predict` implementation as the training artifact
loader, and the test suite verifies JSON round-trip parity. This transparent
model is the first deployable baseline; a compact TFLite/ONNX temporal model
can replace it later while preserving the shared input contract.

## Temporal speed and vibration baseline

`idr_ml.temporal_model` adds a fixed-window statistical model that consumes
forward acceleration and yaw-rate history. It emits both a non-negative speed
estimate and a vibration probability. The implementation is dependency-free
and exports explicit feature names, window length, weights, and version.

```python
from idr_ml.temporal_model import train_temporal_speed_model

model = train_temporal_speed_model(session.frames, window_size=11)
model.save("models/temporal-speed-vibration.json")
```

This is a deterministic temporal baseline, not a neural network or a claim of
trained IO-VNBD performance. It must be trained on complete permitted
sessions, evaluated on held-out sessions, and converted to the Android
runtime schema before it is presented as the production phone model.
