# Intelligent Dead Reckoning for GNSS-Denied Navigation

An edge-deployable navigation engine and Android application for continuous
vehicle positioning when GNSS is unavailable in tunnels, underpasses, parking
structures, forests, and urban canyons.

The project is designed for smartphone IMUs and external IMUs. It combines
calibration, inertial propagation, speed and vibration baselines, adaptive
GNSS/INS correction, non-holonomic constraints, and offline road-geometry
matching.

## Problem

Consumer smartphones do not provide a vehicle speed feed. Their accelerometers
and gyroscopes are affected by mounting orientation, gravity projection,
engine vibration, potholes, braking, and sensor bias. Naive double integration
therefore accumulates unacceptable position error during a GNSS outage.

The system addresses this with:

1. Explicit vehicle-frame calibration.
2. A speed-correction model contract shared by training and Android runtime.
3. Streaming GNSS/INS state management with outage and recovery hysteresis.
4. Non-holonomic forward propagation and bounded map corrections.
5. Deterministic replay and benchmark certification before device deployment.
6. Fail-closed evaluation and provenance rules for real datasets.

## Capabilities

### Navigation engine

- GNSS-aided initialization and recovery.
- Confirmed GNSS-outage transition to dead reckoning.
- Confidence decay during outage.
- Forward-motion and yaw propagation.
- Timestamp, finite-value, and sensor-gap validation.
- External-IMU payload adapter.
- Active bounded fusion-correction seam for acceleration scale, yaw bias, and
  GNSS gain.
- Dependency-free `SegmentMapMatcher` with nearest-road projection,
  cross-track gating, heading gating, and confidence scoring.
- `HmmMapMatcher` with candidate emissions and connected-road sequence
  matching.
- JSON/OSM XML road-way import into local metre-frame segments through
  `load_road_segments`.
- Deterministic throughput reporting for phone-rate and edge-rate replay.

### Machine learning and data

- Explicit IO-VNBD CSV adapter with configurable column mappings.
- Session-level leakage-safe train and evaluation splits.
- Timestamp and vibration quality flags.
- GNSS-anchored speed baseline.
- Ridge-regularized speed-correction model with JSON export and import.
- Fixed-window temporal speed and vibration baseline with JSON export.
- Matching Android `SpeedCorrectionModel` interface and JSON loader.
- Explicit outage evaluation harness with median, p90, and worst-case drift
  aggregation.

### Android application

- Accelerometer, gyroscope, magnetometer, and GPS capture.
- Lifecycle-safe registration and shutdown.
- Stationary gravity stability calibration.
- Forward-motion calibration using GNSS bearing and speed.
- Signed device-axis selection for reversed phone orientations.
- Vehicle-frame acceleration and yaw-rate conversion.
- Native GNSS/INS runtime with visible diagnostic failures.
- Stale-GNSS detection rather than silently reusing an old fix.

## Architecture

```text
Phone IMU / External IMU
          |
          v
Calibration and vehicle-frame adapter
          |
          +--> Speed correction model
          |
          v
GNSS/INS fusion and non-holonomic propagation
          |
          +--> Segment and HMM road-graph map matcher
          |
          v
Navigation state, confidence, diagnostics, and UI
```

Repository layers:

| Layer | Responsibility |
| --- | --- |
| `shared/idr` | Contracts, traces, replay, metrics, synthetic fixtures |
| `ml/idr_ml` | Dataset conversion, quality processing, model training/export |
| `edge-engine/idr_engine` | Streaming fusion, constraints, map matching, adapters |
| `mobile/idr_mobile` | Bounded Python runtime seam for mobile integration |
| `mobile/app` | Native Android capture, calibration, UI, and runtime binding |
| `rover` | Versioned CRC-protected physical-testbed telemetry contract |
| `tests/` | Cross-layer deterministic tests |
| `docs/` | Architecture, model card, benchmark, demo, and release evidence |

## Screening benchmark

The checked-in benchmark is reproducible and intentionally labelled as a
synthetic contract test, not field performance.

| Scenario | Drift | Update rate | Outage transition | Result |
| --- | ---: | ---: | ---: | --- |
| Synthetic 1 km at 60 km/h with 40 s GNSS outage | 0.000% | 10.0 Hz | 0.0 s | Pass |

The generated report records 601 samples, 1,000 m travelled distance, and
recovery at 50.1 s. Floating-point replay error is approximately
`9.3e-13%`. This result does not establish lane-level accuracy, smartphone
performance, tunnel performance, or real IO-VNBD performance.

Evidence:

- [Benchmark report](docs/evidence/synthetic-1km-report.json)
- [Trajectory plot](docs/evidence/synthetic-1km-trajectory.svg)
- [Benchmark methodology](docs/benchmarking.md)
- [Model card](docs/model-card.md)
- [Requirements matrix](docs/requirements-matrix.md)
- [Limitations](docs/limitations.md)
- [Data provenance record](docs/data-provenance.md)
- [IO-VNBD evaluation harness](docs/io-vnbd-evaluation.md)

Generate the evidence again:

```powershell
& 'C:/Program Files/Python314/python.exe' scripts/generate_screening_evidence.py
```

## Quick start

Run the dependency-free Python validation suite:

```powershell
& 'C:/Program Files/Python314/python.exe' -m unittest discover -s tests -v
```

Run release certification:

```powershell
& 'C:/Program Files/Python314/python.exe' scripts/release_check.py
```

Expected current result: 39 tests pass and the synthetic release benchmark
passes the drift and 10 Hz update-rate thresholds.

## Model workflow

The training-side baseline is implemented in
[ml/idr_ml/model.py](ml/idr_ml/model.py). It consumes calibrated forward
acceleration, yaw rate, and absolute acceleration and exports a versioned JSON
artifact containing feature names and weights.

The Android runtime consumes the same schema through
`LinearSpeedCorrectionModel.fromJson` in
[NativeNavigationEngine.kt](mobile/app/src/main/java/org/sih/idr/NativeNavigationEngine.kt).
The current Android shell uses neutral coefficients until a permitted
IO-VNBD-trained artifact is supplied. This is deliberate: the repository does
not claim trained phone performance without a dataset, model version, and
measured evaluation report.

The dependency-free temporal baseline is implemented in
[temporal_model.py](ml/idr_ml/temporal_model.py). It consumes fixed windows
of forward acceleration and yaw rate and emits speed plus vibration
probability. It is a reproducible baseline, not a neural model or trained
IO-VNBD result. The adaptive fusion seam is implemented in
[fusion.py](edge-engine/idr_engine/fusion.py) through
`FusionCorrectionModel`; `LinearFusionCorrection` is active when explicitly
configured, while the default remains the classical no-op correction.

For real data, use the [outage evaluation harness](docs/io-vnbd-evaluation.md):

```powershell
& 'C:/Program Files/Python314/python.exe' scripts/eval_outage.py `
  --input C:/data/io-vnbd/session.csv `
  --columns C:/data/io-vnbd/columns.json `
  --outage-seconds 60 `
  --output docs/evidence/io-vnbd-60s.json
```

The command requires an inspected explicit column mapping and truth
coordinates. It refuses to produce a result when required evidence is absent.

## Demo flow

1. Start the Android app and grant location permission.
2. Keep the device stationary for gravity stability calibration.
3. Drive straight with a valid GNSS bearing and speed.
4. Confirm vehicle-frame calibration and GNSS-aided mode.
5. Trigger a GNSS blackout or replay the deterministic outage trace.
6. Show dead-reckoning mode, confidence decay, and map-constrained output.
7. Restore GNSS and show recovery hysteresis.
8. Open the benchmark report and state its limitations.

See the [demo runbook](docs/demo-runbook.md) for failure handling and the
[release checklist](docs/release-checklist.md) for packaging requirements.

## Current limitations

- The checked-in performance evidence is synthetic.
- IO-VNBD data and trained production weights are not committed.
- OSM import and offline map packaging remain data-preparation steps.
- APK compilation and physical-device validation require a local Android SDK,
  Gradle, and a test device.
- Real tunnel, multipath, vibration, and remounting performance is not yet
  certified.
- The system is a screening prototype and not a safety-critical navigation
  system.

## Project status

Implemented:

- Shared contracts and deterministic replay.
- ML/data baseline and exportable model schema.
- GNSS/INS fusion and external-IMU adapter.
- Concrete road-segment map matcher.
- HMM connected-road map matcher.
- Active adaptive fusion-correction seam.
- Temporal speed/vibration baseline and parity tests.
- Fail-closed IO-VNBD outage evaluator.
- Python mobile runtime.
- Android capture, staged calibration, and native runtime seam.
- Benchmark report and trajectory evidence.
- Rover telemetry protocol with CRC and version validation.

Next validation milestones:

1. Obtain and document a permitted IO-VNBD subset, schema, license, and checksums.
2. Train and evaluate the temporal and adaptive fusion models on held-out sessions.
3. Convert a measured model artifact into the Android JSON schema and measure latency.
4. Import an offline OSM extract into local road segments and evaluate HMM matching.
5. Build and install the Android APK, then validate mounted orientations,
   GNSS outages, and recovery on hardware.
6. Implement the rover ESP32 firmware and Raspberry Pi bridge, then run
   marked-course experiments.

The optional [rover testbed](rover/README.md) is a controlled validation
platform, not a replacement for smartphone or road-speed evidence.

## Governance and contribution

ONEFORALL defines ownership boundaries in
[`.ofa/config.yml`](.ofa/config.yml). The project zones are:

| Zone | Scope |
| --- | --- |
| `ml` | Dataset, preprocessing, training, evaluation, model export |
| `engine` | Fusion, constraints, map matching, external-IMU adapters |
| `mobile` | Android sensors, runtime, UI, and offline maps |
| `shared` | Contracts, tests, documentation, CI, and releases |
| `rover` | Physical-testbed protocol and future firmware/bridge integration |

Before submitting changes:

```powershell
ofa doctor
ofa guard --strict
```

Do not commit complete datasets, proprietary recordings, map extracts,
credentials, signing keys, or oversized generated model binaries.

## License and disclosure

This repository is a Smart India Hackathon screening implementation. Dataset
licenses, map licenses, model provenance, and real-world benchmark conditions
must be recorded before external distribution or performance claims.
