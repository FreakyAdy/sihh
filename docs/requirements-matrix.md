# SIH Requirement Matrix

Statuses are evidence-based:

- **Done**: implemented and covered by repository evidence.
- **Partial**: a working baseline exists, but a required production or physical
  validation element is missing.
- **Missing**: no implementation or evidence exists.

| Requirement | Status | Evidence | Remaining evidence |
| --- | --- | --- | --- |
| In-vehicle pitch, roll, and yaw calibration | Partial | [`VehicleCalibration.kt`](../mobile/app/src/main/java/org/sih/idr/VehicleCalibration.kt) | Full 3D device-to-vehicle transform, gravity compensation, known-orientation tests, remount detection, phone validation |
| AI speed and vibration filtering | Partial | [`model.py`](../ml/idr_ml/model.py), [`temporal_model.py`](../ml/idr_ml/temporal_model.py), [`quality.py`](../ml/idr_ml/quality.py) | IO-VNBD-trained model on real data, held-out session evaluation, Android ONNX/TFLite artifact, device inference latency |
| NHC and map matching (live streaming path) | Partial | [`fusion.py`](../edge-engine/idr_engine/fusion.py), [`constraints.py`](../edge-engine/idr_engine/constraints.py) — `HmmMapMatcher` + new `StreamingHmmMatcher`, [`map_io.py`](../edge-engine/idr_engine/map_io.py) | Real OSM extract, road-graph connectivity, real-trace comparison of segment vs HMM vs no-map |
| AI-based GNSS/INS fusion | Partial | [`fusion.py`](../edge-engine/idr_engine/fusion.py) — `FusionCorrectionModel` seam, `LinearFusionCorrection` | Trained adaptive fusion correction model and real outage comparison vs classical baseline |
| Heading initialization from GNSS | **Done** | [`fusion.py`](../edge-engine/idr_engine/fusion.py) — `_heading_initialized` logic, [`models.py`](../shared/idr/models.py) — `bearing_deg` field, [`test_heading_init.py`](../tests/test_heading_init.py) | Phone validation across North/South/East/West headings |
| Seamless outage and recovery | Partial | [`fusion.py`](../edge-engine/idr_engine/fusion.py), [`SensorCaptureController.kt`](../mobile/app/src/main/java/org/sih/idr/SensorCaptureController.kt) | Unique GNSS fix deduplication fix (Android zone), device blackout transition latency, recovery-jump measurement |
| Outage-only drift metric | **Done** | [`eval_outage.py`](../scripts/eval_outage.py) — window-restricted calculation, [`metrics.py`](../shared/idr/metrics.py) — `OutageMetrics` + `measure_outage()`, [`test_outage_metrics.py`](../tests/test_outage_metrics.py) | Real-data run on IO-VNBD |
| Real-time mobile UI | Partial | [`MainActivity.kt`](../mobile/app/src/main/java/org/sih/idr/MainActivity.kt), [`activity_main.xml`](../mobile/app/src/main/res/layout/activity_main.xml), [`web-demo`](../web-demo/) | APK build, physical device, live map rendering, moving vehicle marker, worker-thread execution |
| Drift under 10% of distance during outage | Partial | [`synthetic-1km-report.json`](evidence/synthetic-1km-report.json) — synthetic contract test | Real IO-VNBD outage-only drift report, phone tunnel traces |
| 10 Hz phone fusion update rate | Partial | [`benchmark.py`](../shared/idr/benchmark.py), deterministic harness passes | Measured timestamps from physical Android device |
| Approximately 200 Hz edge path | Partial | [`adapters.py`](../edge-engine/idr_engine/adapters.py), [`measure_throughput.py`](../scripts/measure_throughput.py) | Measured on target edge hardware with real FOG/high-rate IMU |
| IO-VNBD model and trajectory plots | Partial | [`io_vnbd.py`](../ml/idr_ml/io_vnbd.py) — validated adapter, [`train_io_vnbd.py`](../scripts/train_io_vnbd.py) — training/evaluation pipeline | Dataset download, column mapping, real training run, `evaluation-report.json`, trajectory SVGs |
| External IMU support | Partial | [`adapters.py`](../edge-engine/idr_engine/adapters.py), [`rover/protocol.py`](../rover/protocol.py) | Measured 200 Hz run on real hardware |
| Rover physical testbed | Partial | [`rover/README.md`](../rover/README.md), [`rover/protocol.py`](../rover/protocol.py) | Hardware, firmware, bridge, truth course, experiments |

## What changed in this sprint

| Fix | Impact |
| --- | --- |
| `eval_outage.py` now measures drift inside the outage window only | Correctness: previous full-session calculation was invalid |
| `shared/idr/metrics.py` adds `OutageMetrics` / `measure_outage()` | Any caller can compute the correct windowed metric |
| `GnssFix.bearing_deg` field added | GNSS receivers that supply course-over-ground now initialize heading instantly |
| `FusionEngine` heading initialization from GNSS bearing and separated fixes | Fixes northbound/non-east DR divergence at outage start |
| `VehicleFrameAdapter` mount decoupling & gravity compensation | Fixes catastrophic bug where chassis acceleration rotated with Earth compass bearing |
| `SensorCaptureController` & `NativeNavigationEngine` GNSS deduplication | Eliminates 150 Hz fix replication and ensures recovery count retention |
| `FusionEngine` Zero Velocity Updates (ZUPT) & speed model blending | Clamps stationary drift during red lights/tunnel traffic jams |
| `generate_screening_evidence.py` upgraded to `FusionEngine` | Eliminates misleading 0% drift artifact; reports realistic 2.4% drift with naive comparison |
| `web-demo` complete UI/UX overhaul for judges | Delivers high-impact interactive simulation with tunnel blackout, ghost baseline comparison, and HUD |
| `io_vnbd.py` validates all configured columns and rejects non-monotonic timestamps | Prevents silent data corruption during ingestion |
| `dataset.py` adds `session_train_test_split` convenience function | Training script can split without writing boilerplate |
| `scripts/train_io_vnbd.py` — end-to-end pipeline | Enables one command to train, evaluate and generate SVG plots once data is provided |
| `StreamingHmmMatcher` added to `constraints.py` and exported | HMM sequence matcher now usable in live streaming path via `MapMatcher` protocol |
| `map_io.py` coordinate-frame documented | Prevents frame mismatch when loading OSM data at a different geographic origin |

## Current certification boundary

The synthetic evidence certifies only deterministic replay behavior and metric
plumbing. It does not certify smartphone, tunnel, IO-VNBD, lane-level, FOG,
rover, or physical Android performance.

Real-data results (IO-VNBD) will be added to `docs/evidence/io-vnbd/` once
the dataset is downloaded and the training pipeline is run.
