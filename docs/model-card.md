# IDR baseline model card

## Model

The screening build uses a transparent, ridge-regularized linear speed
correction baseline from `ml/idr_ml/model.py`. It consumes calibrated
forward acceleration, yaw rate, and absolute acceleration features and emits a
non-negative forward-speed estimate.

The model is deliberately not represented as evidence of final AI performance.
It is a deterministic integration artifact and fallback while the compact
temporal model is trained on approved IO-VNBD and phone recordings.

## Training and evaluation

- Training labels: GNSS speed where available and valid.
- Split policy: complete drive/session IDs, never adjacent windows.
- Input normalization: must be computed from training sessions only once the
  learned temporal model is introduced.
- Export metadata: model type, version, feature names, and weights.
- Runtime parity: JSON save/load prediction parity is covered by tests.

The Android runtime accepts this same schema through
`LinearSpeedCorrectionModel.fromJson`, keeping export and on-device feature
names aligned. The current shell uses neutral coefficients until a permitted
IO-VNBD-trained artifact is supplied; no untrained artifact is presented as
measured performance.

The repository also includes a dependency-free fixed-window temporal baseline
in `ml/idr_ml/temporal_model.py`. It emits speed and vibration probability and
has JSON round-trip parity tests. It is a research baseline only: no real
dataset training, neural export, Android latency measurement, or held-out
session result is claimed yet.

## Limitations

- The baseline does not model full 3D orientation, bias random walk, wheel
  slip, lane topology, or map semantics.
- Synthetic benchmark success is not real-world smartphone accuracy.
- GNSS speed labels may be unavailable or degraded during multipath and must be
  filtered before training.
- The estimator must expose degraded confidence during outages rather than
  claiming lane-level accuracy without suitable observability.

## Intended use

Screening demonstration, deterministic replay, integration testing, and
fallback speed correction. It is not a certified safety-critical navigation
system.
