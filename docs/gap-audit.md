# Phase 0 Gap Audit

This audit compares the current repository against the SIH intelligent
dead-reckoning requirements. It is based on the implementation and evidence
currently present in the repository. No real IO-VNBD, Android-device, or rover
result is inferred from synthetic tests.

## Summary

| Area | Status | Current evidence | Main gap |
| --- | --- | --- | --- |
| Shared contracts and replay | Done | [`shared/idr`](../shared/idr) and 39 tests | None for the baseline contract |
| Android capture and staged calibration | Partial | [`mobile/app`](../mobile/app) | APK build and physical-device validation |
| Speed estimation | Partial | [`ml/idr_ml/model.py`](../ml/idr_ml/model.py) | Trained temporal model and measured phone inference |
| GNSS/INS fusion | Partial | [`edge-engine/idr_engine/fusion.py`](../edge-engine/idr_engine/fusion.py) | Learned adaptive fusion correction and real-trace evaluation |
| Non-holonomic constraints | Done for baseline | [`fusion.py`](../edge-engine/idr_engine/fusion.py) | ESKF/UKF-grade uncertainty model |
| Map matching | Partial | [`constraints.py`](../edge-engine/idr_engine/constraints.py) with segment and HMM matchers | OSM import and real-trace evaluation |
| External IMU support | Partial | [`adapters.py`](../edge-engine/idr_engine/adapters.py) | 200 Hz contract and high-rate replay evidence |
| IO-VNBD evaluation | Missing | [`io_vnbd.py`](../ml/idr_ml/io_vnbd.py) is an adapter only | Dataset cache, verified schema, outage evaluation |
| Position plots | Partial | [`docs/evidence`](evidence) | Current plot is synthetic only; three real-trace plots missing |
| Android on-device ML | Partial | [`NativeNavigationEngine.kt`](../mobile/app/src/main/java/org/sih/idr/NativeNavigationEngine.kt) | Artifact loading exists, trained artifact and latency measurement missing |
| Rover testbed | Partial | [`rover/protocol.py`](../rover/protocol.py) and [`rover/README.md`](../rover/README.md) | Hardware, firmware, bridge, truth course, and experiments |
| Release reproducibility | Partial | [`scripts/release_check.py`](../scripts/release_check.py) | Regeneration and README-number consistency checks |

## Requirement-by-requirement audit

### In-vehicle alignment and calibration

**Status: Partial.**

Implemented:

- Stationary gravity stability collection.
- Forward-motion collection requiring GNSS bearing and speed.
- Pitch, roll, heading, and signed device-axis output.
- Explicit `COMPLETE` and `FAILED` states.
- Vehicle-frame conversion boundary.

Evidence:

- [`VehicleCalibration.kt`](../mobile/app/src/main/java/org/sih/idr/VehicleCalibration.kt)
- [`VehicleFrameAdapter.kt`](../mobile/app/src/main/java/org/sih/idr/VehicleFrameAdapter.kt)

Missing:

- Calibration tests with known random mount rotations.
- Remounting detection and automatic recalibration during a drive.
- Physical phone validation across dashboard and holder orientations.

### AI speed and vibration filter

**Status: Partial.**

Implemented:

- Quality flags and acceleration smoothing.
- GNSS-labelled ridge speed-correction baseline.
- Versioned JSON export/import.
- Android-side model interface and JSON loader.

Evidence:

- [`ml/idr_ml/quality.py`](../ml/idr_ml/quality.py)
- [`ml/idr_ml/model.py`](../ml/idr_ml/model.py)
- [`NativeNavigationEngine.kt`](../mobile/app/src/main/java/org/sih/idr/NativeNavigationEngine.kt)

Missing:

- Compact temporal model trained on held-out complete sessions.
- Vibration/non-navigation-motion classification.
- Pothole, idle-vibration, noise, and mount-rotation augmentation.
- ONNX/TFLite artifact and parity test.
- Measured Android inference latency.

### Map matching and kinematic constraints

**Status: Partial.**

Implemented:

- Forward-only non-holonomic propagation.
- Bounded map correction interface.
- Deterministic segment projection with distance and heading gates.

Evidence:

- [`fusion.py`](../edge-engine/idr_engine/fusion.py)
- [`constraints.py`](../edge-engine/idr_engine/constraints.py)
- [`tests/test_fusion.py`](../tests/test_fusion.py)

Missing:

- OSM extraction/import pipeline.
- Road graph connectivity and HMM candidate transitions.
- Evaluation on a real trace with and without map matching.
- Explicit UKF/ESKF covariance treatment.

### AI-based GNSS/INS fusion

**Status: Partial.**

Implemented:

- Streaming GNSS-aided, initialization, dead-reckoning, and recovery modes.
- Outage confirmation and recovery hysteresis.
- Confidence decay and map correction.
- External payload conversion.

Evidence:

- [`fusion.py`](../edge-engine/idr_engine/fusion.py)
- [`tests/test_integration_scenarios.py`](../tests/test_integration_scenarios.py)

Missing:

- Learned component inside fusion.
- Adaptive process/measurement covariance prediction.
- Comparison against a learned fusion correction on real outage windows.
- Device-measured transition latency in milliseconds.

### Seamless GNSS-deficit handling

**Status: Partial.**

Implemented:

- Explicit GNSS-missing detection.
- Hysteresis for outage and recovery.
- Stale-GNSS rejection in the Android capture path.

Evidence:

- [`fusion.py`](../edge-engine/idr_engine/fusion.py)
- [`SensorCaptureController.kt`](../mobile/app/src/main/java/org/sih/idr/SensorCaptureController.kt)

Missing:

- Millisecond-scale device measurement.
- Recorded Android blackout/recovery trace.
- Recovery position-jump acceptance test on hardware.

### Real-time mobile interface

**Status: Partial.**

Implemented:

- Android diagnostic UI.
- Sensor and permission lifecycle handling.
- Navigation mode, position, confidence, and sample diagnostics.

Evidence:

- [`MainActivity.kt`](../mobile/app/src/main/java/org/sih/idr/MainActivity.kt)
- [`activity_main.xml`](../mobile/app/src/main/res/layout/activity_main.xml)

Missing:

- Built APK.
- Physical-device test.
- Smooth vehicle marker rendering.
- In-app inference latency and 10 Hz display.
- Offline map display.

### Benchmark targets

**Status: Partial.**

Implemented:

- Drift, distance, update-rate, outage-latency, and recovery metrics.
- Synthetic 1 km at 60 km/h contract report.

Evidence:

- [`benchmark.py`](../shared/idr/benchmark.py)
- [`synthetic-1km-report.json`](evidence/synthetic-1km-report.json)
- [`synthetic-1km-trajectory.svg`](evidence/synthetic-1km-trajectory.svg)

Missing:

- Real IO-VNBD outage windows.
- Median, p90, and worst-case aggregation across sessions.
- Phone and approximately 200 Hz external-IMU measurements.
- Honest miss reports where targets are not met.

### IO-VNBD preliminary model and plots

**Status: Missing for screening evidence.**

Implemented:

- Explicit mapping adapter that refuses to guess column names.
- Session-level split primitives.

Evidence:

- [`io_vnbd.py`](../ml/idr_ml/io_vnbd.py)
- [`dataset.py`](../ml/idr_ml/dataset.py)

Missing:

- Actual permitted dataset files or documented cache download.
- Verified schema and column mapping from those files.
- Real model training and held-out evaluation.
- Three representative trajectory plots.
- Dataset checksum, version, license, seed, and training commit metadata.

### External IMU edge engine

**Status: Partial.**

Implemented:

- Transport-neutral external payload adapter.
- Shared frame validation.

Evidence:

- [`adapters.py`](../edge-engine/idr_engine/adapters.py)
- [`tests/test_fusion.py`](../tests/test_fusion.py)

Missing:

- Versioned 200 Hz payload specification.
- High-rate replay and throughput report.
- FOG-specific evaluation.

### Rover physical testbed

**Status: Missing.**

No `rover/` implementation exists. The following remain unimplemented:

- ESP32 firmware and watchdog telemetry protocol.
- Raspberry Pi bridge and JSONL session logging.
- GNSS outage switch.
- Marked-course or surveyed reference truth.
- Repeated straight, square, figure-eight, and loop experiments.
- Slip-aware skid-steer model.
- Rover-specific learned slip model.

## Claims requiring correction or qualification

The README now labels the 0.000% result as a synthetic contract test and
states that real phone, tunnel, and IO-VNBD performance is unverified. The
model and architecture documentation also identifies the Android neutral
coefficient fallback.

The following terms must remain qualified until their evidence exists:

- “AI speed model”: currently a transparent ridge baseline, not a trained
  temporal neural model.
- “AI-based fusion”: current fusion is classical with an injectable model
  seam; no learned fusion correction is active.
- “Map matching”: segment and HMM matching primitives exist, but OSM import
  and real-trace graph evaluation are not complete.
- “Real-time mobile navigation”: Android code exists, but APK and hardware
  execution are unverified in this environment.
- “External IMU at 200 Hz”: the adapter is transport-neutral, but no 200 Hz
  measured run is committed.

## Recommended execution order

1. Obtain and document the permitted IO-VNBD subset and schema.
2. Implement real outage evaluation and aggregate statistics.
3. Train and export the speed model, then measure Android parity and latency.
4. Add OSM import and evaluate the HMM graph matcher on a real trace.
5. Build and validate the Android application on a physical phone.
6. Add the rover firmware, bridge, truth course, and experiments.
7. Regenerate all evidence and update the requirements matrix before release.
