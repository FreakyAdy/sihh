# SIH Deep Repository Audit: Intelligent Dead Reckoning

**Repository:** https://github.com/FreakyAdy/sihh  
**Audited branch:** `master`  
**Scope:** tracked-file inventory, Markdown and project guidance, core Python navigation engine, ML/data modules, native Android code, web demo, benchmark scripts, tests, and evidence artifacts.  
**Audit date:** 10 October 2026

## Executive verdict

The repository has a credible prototype foundation, but it is **not yet evidence-ready for the SIH screening criteria**. The clearest strengths are the separation of shared contracts, edge fusion, ML/data, Android, and documentation; explicit failure/diagnostic handling in parts of the system; and documentation that generally avoids passing synthetic success off as field accuracy.

The main blockers are not documentation volume. They are: (1) an invalid outage-drift calculation in the real-data evaluation path, (2) an Android sensor pipeline that reuses stale/asynchronous measurements and can count the same GNSS fix repeatedly, (3) incorrect/incomplete phone-to-vehicle-frame calibration, (4) no real IO-VNBD model/evaluation evidence, and (5) no demonstrated end-to-end Android + edge + map-matching behavior on hardware.

**Screening status:** engineering scaffold in place; core performance target and required preliminary IO-VNBD result remain unproven. Do not claim lane-level or real-world tunnel accuracy yet.

## Repository coverage

The recursive Git tree reports 104 tracked files, including 24 Markdown files, 38 Python files, 5 Kotlin files, and 11 test files. The audit mapped the tree and inspected the central READMEs/docs, core estimator and map matching, ML and dataset adapters, native Android sensor/calibration/estimator code, browser demo, evaluation/release scripts, representative tests, and project configuration. The GitHub clone could not be fetched into a local runtime due to this environment's network/DNS restriction, so the automated test suite and Android build were **not independently executed during this audit**.

Main code zones:

- `shared/idr/`: shared data contracts, replay, metrics, scenarios, throughput, synthetic fixtures.
- `edge-engine/idr_engine/`: 2D GNSS/INS propagation, corrections, constraints, map import, external IMU adapter.
- `ml/idr_ml/`: CSV adapter, session splits, quality flags, linear and fixed-window statistical baselines.
- `mobile/idr_mobile/`: bounded Python runtime adapter.
- `mobile/app/`: Android/Kotlin sensor capture, calibration, vehicle frame adapter, navigation state machine and simple UI.
- `web-demo/`: static deterministic presentation animation, not a live sensor engine.
- `scripts/`: outage evaluation, synthetic evidence generation, throughput and release checks.
- `docs/`: architecture, model card, limitations, SIH requirement matrix, evidence provenance, demo and judge playbook.

## Findings by severity

### P0: fix before trusting screening metrics

#### 1. Outage evaluator measures the wrong interval

**Files:** `scripts/eval_outage.py`, `shared/idr/metrics.py`, `tests/test_eval_outage.py`.

The evaluator masks GNSS for a selected outage, but then computes position error from the full session and divides maximum error by distance travelled over the full session. This is not the requested drift during the GNSS-denied interval. Pre-outage and post-outage frames can dilute or otherwise distort the value. `shared/idr/metrics.py` also aggregates errors/distance over the full input trace instead of isolating the outage window.

**Required change:** make outage start/end first-class evaluation bounds. Compute maximum/p50/p90 error only inside the outage interval, calculate travelled ground-truth distance only over the same interval, report outage duration and covered distance, and fail closed when ground-truth coverage is incomplete. Add tests where pre/post-outage errors are small but outage error is large, so this bug cannot recur. Include median, p90 and worst-case drift across independent sessions.

#### 2. Android uses repeated GNSS fixes as if they were new fixes

**Files:** `mobile/app/src/main/java/org/sih/idr/SensorCaptureController.kt`, `VehicleFrameAdapter.kt`, `NativeNavigationEngine.kt`, `MainActivity.kt`.

`SensorCaptureController` stores the latest location and attaches it to every accelerometer/gyroscope callback while it is within a freshness window. `VehicleFrameAdapter` replaces the IMU timestamp with the current sensor-event time but retains that same old `Location`. `NativeNavigationEngine` increments `recoveryCount` on every such sample. Consequently, one GNSS fix can be re-labelled as multiple new fixes and can satisfy the consecutive-fix recovery condition. It can also repeatedly pull the position toward the same stale coordinate while that fix is still considered fresh.

**Required change:** retain original GNSS measurement timestamps and sequence/fix identity. Fuse GNSS only when a genuinely new fix arrives; interpolate/hold it for display if needed, but do not count a reused fix as a new measurement. Separate the IMU stream from the lower-rate GNSS stream and test delayed, duplicated, stale and out-of-order fixes.

#### 3. Phone-to-vehicle calibration is not yet a reliable 3D frame transform

**Files:** `VehicleCalibration.kt`, `VehicleFrameAdapter.kt`, `SensorCaptureController.kt`.

The calibration collects a fixed number of callbacks rather than independent, time-resampled samples. Because callbacks are triggered by both accelerometer and gyroscope events, the other sensor's latest value is often reused. The motion-stage sample count can likewise be satisfied by repeats of a single GNSS fix. Forward-axis selection is based on mean raw X/Y acceleration differences during forward motion, where acceleration may be close to zero and gravity/tilt still contaminates the reading. Pitch and roll are calculated but are not used by `VehicleFrameAdapter`; raw accelerometer X/Y is projected using a formula that mixes global GPS course with the selected phone axis rather than applying a properly estimated device-to-vehicle rotation. Z gyro is assumed to be vehicle yaw regardless of phone tilt.

**Required change:** estimate orientation with an explicit phone/device-to-vehicle transform (e.g., gravity/magnetometer/gyro attitude or robust movement calibration), remove gravity using the full 3D transform, align acceleration and angular-rate samples by timestamps, and use independent GNSS fixes only for course reference. Calibrate with known mount rotations and dashboard/holder placements. Report calibration quality and refuse navigation when orientation is under-observed.

#### 4. Python fusion does not initialize heading from GNSS course

**File:** `edge-engine/idr_engine/fusion.py`, shared contracts in `shared/idr/models.py`.

The engine starts `_heading_rad` at `0.0`; its local coordinate convention is x=east/y=north, so zero propagates east. The `GnssFix` contract has no bearing/course field and `_handle_gnss` corrects position/speed but does not infer heading from consecutive fixes. The straight-line fixtures are eastward with zero yaw, so existing tests do not expose the error. Starting a GNSS outage after northbound or another-direction travel can result in the wrong propagation heading.

**Required change:** add a validated heading/course initialization method, infer course from successive sufficiently separated reliable GNSS fixes where safe, track heading uncertainty/observability, and test outages starting in north, south, east, west, and turns. Keep the Python (east/north) and Android (currently north/east) coordinate-frame conventions consistent or document/convert explicitly at the interface.

### P1: required SIH evidence and runtime integration

#### 5. No actual IO-VNBD-trained result is checked in

**Files:** `ml/idr_ml/io_vnbd.py`, `ml/idr_ml/model.py`, `ml/idr_ml/temporal_model.py`, `docs/data-provenance.md`, `docs/io-vnbd-evaluation.md`, `docs/model-card.md`, `docs/evidence/`.

The adapter and provenance template exist, but there is no verified local schema/column map, permitted subset metadata, trained real-data artifact, held-out results, or real-data trajectory plot. The only checked-in trajectory is synthetic. SIH explicitly requires preliminary model output and a position plot inferred from an IO-VNBD subset; this is the largest screening deliverable still missing.

**Required change:** obtain the dataset and verify the local file schema before defining `ColumnMap`. Record source/release, permitted use, checksum, units, session IDs, model/code version and split seed. Split entire sessions, not adjacent windows. Train and evaluate on held-out sessions and generate a position plot plus a report that makes the outage-only interval and algorithm variant explicit. Do not commit large raw data if avoidable; document reproducible cache paths/checksums.

The dataset paper describes smartphone inertial measurements at about 10 Hz and smartphone GNSS updates at about 1 Hz, with multiple smartphone axes and vehicle-derived signals in the broader dataset. Treat the lower-rate GNSS labels carefully, and never use vehicle CAN/wheel-speed channels as inference features for a smartphone-only target. They may only be used as declared supervision/reference where the evaluation protocol permits it. Sources: [IO-VNBD paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7907232/) and [official dataset repository](https://github.com/onyekpeu/IO-VNBD).

#### 6. Current “AI speed” model learns absolute speed from weak instantaneous features

**Files:** `ml/idr_ml/model.py`, `ml/idr_ml/temporal_model.py`, `mobile/app/.../NativeNavigationEngine.kt`, `docs/model-card.md`.

`train_speed_model` fits absolute GNSS speed using instantaneous acceleration, yaw rate and absolute acceleration. Those values do not uniquely determine absolute vehicle speed. The tests prove the regression can fit a synthetic algebraic relationship, not that speed is observable from real smartphone IMU data. The temporal model is a fixed-window statistical/ridge baseline, not a deep network; its vibration target is generated from maximum acceleration in the window, so it is a heuristic pseudo-label rather than independent ground-truth vibration classification. The temporal features use a centered window in training, which may not match causal on-device inference latency.

On Android, the `modelSpeed` prediction is used only inside a `coerceAtMost(max(modelSpeed, oldSpeed + 5))` upper bound; because `oldSpeed + 5` typically dominates for realistic accelerations, the model usually does not correct speed in a useful way. The default coefficients are neutral and no trained artifact is loaded into the native application.

**Required change:** use GNSS speed/course as intermittent initialization/measurement, integrate calibrated acceleration with bias estimation and uncertainty, and train the ML component to estimate a physically meaningful correction (e.g., residual acceleration/bias/scale, velocity increment, motion/vibration quality or uncertainty) with causal input windows. Compare no-model vs model on held-out real outages. Implement a tested artifact export/import path used by Android and report device inference latency.

#### 7. Edge HMM map matcher is not used by the streaming fusion engine

**Files:** `edge-engine/idr_engine/constraints.py`, `fusion.py`, `map_io.py`.

`HmmMapMatcher.match_sequence()` performs sequence matching, but it does not override the per-sample `.match()` interface that `FusionEngine._apply_map_constraint()` calls. Passing an `HmmMapMatcher` to the live engine therefore uses the inherited nearest-segment matcher, not the HMM sequence solver. Additionally, OSM import creates local metre-frame segments around the first node but does not return/store that origin or transform those coordinates into the fusion engine's GNSS-anchored local frame. The engine's map coordinates and imported OSM coordinates can therefore be incompatible. OSM import also does not currently select only usable `highway` ways or construct graph connectivity for HMM transitions.

**Required change:** define a map-origin/coordinate-transform contract, parse/filter road classes and direction, create road connectivity, and connect a stateful streaming matcher (or a well-defined sliding sequence matcher) to the actual fusion update path. Add end-to-end tests with known GNSS origin, OSM ways, wrong-road alternatives, turns and reverse-direction travel. Compare no-map, segment-match and HMM results on real traces.

#### 8. Android app does not yet demonstrate the requested full navigation surface

**Files:** `mobile/app/.../MainActivity.kt`, `NativeNavigationEngine.kt`, `activity_main.xml`, `docs/demo-runbook.md`.

The current Android screen has a decorative grid/route and text labels; the plus/minus controls are non-functional `TextView`s, there is no real offline map, and there is no moving vehicle marker tied to the estimator. The Kotlin engine does not call the Python edge map matcher and has no actual NHC/map-correction pipeline. The code updates the estimator and UI directly from the sensor callback, likely on the UI looper because the listeners are registered from the main thread; this does not match the documented worker-queue integration architecture. The document suggests checking a cached offline-map region, but an offline map implementation/package is not present.

**Required change:** move fusion/model inference off the UI/sensor callback onto a bounded worker, preserve diagnostics for queue drops, connect the UI to a defined immutable navigation-state contract, implement an actual vehicle marker/map or explicitly label the current UI as a replay prototype. Wire the trained model and streaming map-matching path into the runtime before claiming the full solution.

#### 9. Throughput/demo labels are not measurement evidence

**Files:** `scripts/measure_throughput.py`, `web-demo/app.js`, `web-demo/index.html`, `docs/evidence/synthetic-1km-report.json`.

The throughput script measures Python engine processing on the machine running it, not Android 10 Hz or an external FOG/edge sensor stream at 200 Hz. The browser demo advances every 450 ms (about 2.2 updates/second) while showing a static `10 Hz` metric and describing replay samples as 10 Hz. It is deterministic visual simulation, not a live estimator trace. The synthetic report itself is an ideal straight-line run through `DeadReckoningReplay`; it proves contract/metric plumbing, not real drift or even full `FusionEngine` performance. The README correctly discloses this, but the static UI label could still mislead a viewer.

**Required change:** label the browser demo's numbers as illustrative, or replay a timestamped trace and display simulation time distinctly from real processing rate. Measure 10 Hz on the actual phone and 200 Hz on actual target edge hardware, logging sample timestamps, dropped samples, compute latency and power/thermal behavior. Keep synthetic results separate from measured data.

### P2: reliability, completeness and documentation drift

#### 10. CSV adapter silently accepts some missing configured columns

**File:** `ml/idr_ml/io_vnbd.py`.

Only timestamp/forward acceleration/yaw-rate headers are checked as required. If optional fields are configured but not present (session, latitude/longitude, speed, truth), they can silently degrade to missing data or merge sessions into `default`. Per-session input order is not validated at ingestion; non-monotonic samples may fail later in the engine.

**Required change:** validate every configured mapping against actual headers, validate units, sort only if justified by source semantics or otherwise reject non-monotonic timestamps, report per-session counts and missingness, and require adequate GNSS/truth coverage before evaluation.

#### 11. Coordinate conventions and confidence need one shared contract

Python edge coordinates use x=east/y=north; the native Android code currently uses x=north/y=east when converting local meters to latitude/longitude. Map matcher confidence does not meaningfully change the estimator's confidence, which mainly decays linearly with elapsed outage time. Heading, map, sensor-quality and time uncertainty are not carried in a shared covariance model.

**Required change:** standardize the frame convention, add explicit coordinate conversion tests, and report quality/uncertainty from sensor validity, outage duration and map-match gating. Never hard-snap to a candidate road solely because it is geometrically nearby.

#### 12. Repository build/governance inconsistencies

- Actual GitHub default branch is `master`, while `.ofa/config.yml` says `default_branch: main`.
- No Gradle wrapper files appear in the tracked tree, though mobile docs recommend `gradlew.bat :app:assembleDebug`; a clean clone cannot use that command unless a wrapper is added or system Gradle is installed and invoked directly.
- `.github/CODEOWNERS` uses trailing slashes on root file paths such as `/README.md/`; check/fix single-file rules and verify with GitHub's CODEOWNERS validation.
- The Python quick-start commands are specific to one Windows Python 3.14 install path; document portable `python -m unittest`/environment setup as well.
- The test suite is valuable for contracts and synthetic integration, but no test currently measures the actual real-data outage interval correctly, phone orientation accuracy, duplicate GNSS fix recovery, or real Android execution.

## SIH requirement status

| SIH requirement | Audit status | Evidence needed next |
|---|---|---|
| Phone pitch/roll/yaw-to-vehicle alignment | **Partial / high risk** | Full frame transform, gravity compensation, mount-rotation/device tests |
| AI speed and vibration filter | **Partial baseline only** | Real IO-VNBD trained model, causal inference, held-out validation, phone latency |
| NHC/advanced map matching | **Partial** | Live HMM integration, matching coordinate frame, offline OSM extract, road-graph test |
| AI-based GNSS/INS fusion | **Partial classical baseline** | Trained correction/uncertainty model and real outage comparison |
| Seamless blackout/recovery | **Partial and recovery bug risk** | Unique GNSS fix handling and measured phone blackout/recovery timings |
| Functional mobile navigation UI | **Partial shell** | Actual moving marker, map/map matching integration, worker execution and APK/device test |
| Drift below 10% | **Unproven on real data** | Correct outage-only metrics on IO-VNBD and phone traces |
| 10 Hz smartphone update | **Unproven on device** | Android timestamp/latency/drop report |
| ~200 Hz external IMU/edge path | **Adapter and desktop harness only** | Measured high-rate sensor/hardware report |
| IO-VNBD preliminary model + trajectory plot | **Missing** | Real-data model, provenance, held-out position plot and results |

## Recommended execution order

1. **Repair the metric first.** Make outage-only drift/position error a unit-tested report. This is the foundation for every later claim.
2. **Fix sensor truthfulness.** Consume each IMU sample correctly, retain true GNSS timestamps/IDs, count only new GNSS fixes, and repair the 3D device-to-vehicle calibration.
3. **Get one IO-VNBD subset running end-to-end.** Verify release/schema/units, document checksums and session splits, produce a baseline report and real trajectory plot. Do not wait for a neural network before creating a valid baseline.
4. **Improve the physical model.** Fit meaningful corrections and uncertainty on training sessions; compare against classical baseline on held-out sessions and outage-only windows.
5. **Integrate OSM/HMM correctly.** Convert OSM to the estimator's local frame, build road connectivity, and test the actual streaming path.
6. **Run on the target device.** Build APK, test orientations and sensor rates, record 10 Hz, blackout transition latency, drift and recovery jump, then save logs/artifact hashes.
7. **Close the evidence loop.** Update `README.md`, `docs/requirements-matrix.md`, `docs/model-card.md`, `docs/data-provenance.md`, `docs/limitations.md`, and judge playbook from measured reports only. Keep synthetic, dataset replay and physical device results in separate tables.
8. **Then tune the presentation.** The existing documentation is already more honest than many hackathon repos; engineering evidence should lead, not another round of claims or decorative UI.

## Bottom line

Keep the current repository structure. Do not rewrite everything. First fix the measurement path and sensor calibration; then generate one reproducible IO-VNBD result; then connect the trained model and road matcher to a built Android app. That sequence turns the current prototype into something SIH judges can actually verify.
