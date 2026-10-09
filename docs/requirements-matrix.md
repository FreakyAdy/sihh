# SIH Requirement Matrix

Statuses are evidence-based:

- **Done**: implemented and covered by repository evidence.
- **Partial**: a working baseline exists, but a required production or physical
  validation element is missing.
- **Missing**: no implementation or evidence exists.

| Requirement | Status | Evidence | Remaining evidence |
| --- | --- | --- | --- |
| In-vehicle pitch, roll, and yaw calibration | Partial | [`VehicleCalibration.kt`](../mobile/app/src/main/java/org/sih/idr/VehicleCalibration.kt) | Known-orientation tests, remount detection, phone validation |
| AI speed and vibration filtering | Partial | [`model.py`](../ml/idr_ml/model.py), [`temporal_model.py`](../ml/idr_ml/temporal_model.py), [`quality.py`](../ml/idr_ml/quality.py) | IO-VNBD-trained temporal model, held-out sessions, Android artifact |
| NHC and map matching | Partial | [`fusion.py`](../edge-engine/idr_engine/fusion.py), [`constraints.py`](../edge-engine/idr_engine/constraints.py) including `HmmMapMatcher`, [`map_io.py`](../edge-engine/idr_engine/map_io.py) | Real OSM extract and real-trace comparison |
| AI-based GNSS/INS fusion | Partial | [`fusion.py`](../edge-engine/idr_engine/fusion.py) active `FusionCorrectionModel` seam | Trained adaptive fusion correction and real outage comparison |
| Seamless outage and recovery | Partial | [`fusion.py`](../edge-engine/idr_engine/fusion.py), [`SensorCaptureController.kt`](../mobile/app/src/main/java/org/sih/idr/SensorCaptureController.kt) | Device latency and recovery-jump measurements |
| Real-time mobile UI | Partial | [`MainActivity.kt`](../mobile/app/src/main/java/org/sih/idr/MainActivity.kt), [`activity_main.xml`](../mobile/app/src/main/res/layout/activity_main.xml), [`web-demo`](../web-demo/) | APK build, physical device, live map tiles, smooth marker |
| Drift under 10% | Partial | [`synthetic-1km-report.json`](evidence/synthetic-1km-report.json) | Real IO-VNBD and phone traces |
| 10 Hz phone fusion | Partial | [`benchmark.py`](../shared/idr/benchmark.py) | Device measurement |
| Approximately 200 Hz edge path | Partial | [`adapters.py`](../edge-engine/idr_engine/adapters.py), [`measure_throughput.py`](../scripts/measure_throughput.py) | Hardware/high-rate sensor measurement |
| IO-VNBD model and plots | Missing | [`io_vnbd.py`](../ml/idr_ml/io_vnbd.py) adapter only | Dataset, verified mapping, training, evaluation, plots |
| External IMU support | Partial | [`adapters.py`](../edge-engine/idr_engine/adapters.py), [`rover/protocol.py`](../rover/protocol.py) | Versioned 200 Hz measured run |
| Rover physical testbed | Partial | [`rover/README.md`](../rover/README.md), [`rover/protocol.py`](../rover/protocol.py) | Hardware, firmware, bridge, truth course, experiments |

## Current certification boundary

The synthetic evidence certifies only deterministic replay behavior and metric
plumbing. It does not certify smartphone, tunnel, IO-VNBD, lane-level, FOG,
rover, or physical Android performance.
