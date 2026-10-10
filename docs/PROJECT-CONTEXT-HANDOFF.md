# Intelligent Dead Reckoning — Complete IDE Handoff

## Document purpose

This document transfers the complete project context from the beginning of
implementation through the current presentation-preparation phase. Use it
when moving the project to another IDE, onboarding a teammate, or starting a
new coding agent.

It records:

- The original SIH problem and intended solution
- The implementation history and current repository structure
- The important contracts and state-machine behavior
- Evidence, tests, limitations, and unavailable validation
- Presentation positioning and tomorrow's demo plan
- Production frontend handoff rules
- ONEFORALL ownership and conflict-avoidance requirements
- Recommended next actions

This is an engineering and collaboration handoff, not a record of private
model reasoning. Claims below are based on repository files and completed
validation commands.

---

## 1. Project identity

**Project:** sih-intelligent-dead-reckoning  
**Repository:** `FreakyAdy/sihh`  
**Workspace:** `C:\Users\FreakyAdy\Documents\sihh`  
**Platform:** Windows  
**Problem domain:** smartphone and external-IMU navigation during GNSS outages  
**Submission context:** Smart India Hackathon Intelligent Dead Reckoning  
**Current stage:** screening prototype, presentation preparation, production UI
handoff

The project is designed to support:

- Smartphones mounted in cars, trucks, motorcycles, and scooters
- External IMUs connected to an edge computer
- GNSS-aided navigation when a valid signal exists
- Dead reckoning during tunnels, underpasses, parking structures, dense
  forests, valleys, urban canyons, and interference
- Offline road constraints and future OSM map data
- Pre-trained models running at the edge after cloud/desktop training

---

## 2. Original problem

Vehicle logistics, ride-hailing, quick-commerce, and emergency-response
vehicles rely on smartphone navigation. GNSS can disappear or become
unreliable in:

- Long underground tunnels
- Underpasses
- Multi-level parking structures
- Dense forests
- Deep valleys
- Urban canyons
- Intentional or unintentional interference environments

When GNSS fails, a conventional navigation application may:

- Freeze the vehicle marker
- Jump to a parallel road
- Miscalculate a turn
- Miss an exit
- Show stale position data

High-end vehicles may have wheel-connected inertial systems, but most Indian
vehicles do not expose a reliable speed feed. The target system therefore uses
the smartphone's:

- Accelerometer
- Gyroscope
- Magnetometer/compass where available
- GNSS when available

The key technical difficulty is that consumer MEMS sensors experience:

- Mounting-orientation variation
- Gravity projection
- Engine vibration
- Road vibration
- Pothole shocks
- Sudden braking
- Sensor bias
- Temperature and mechanical noise

Naive double integration of acceleration accumulates unacceptable error.

---

## 3. Core solution positioning

The project is positioned as:

> A smartphone-based Intelligent Dead Reckoning system that keeps vehicle
> navigation moving during GNSS outages using phone motion sensors,
> vehicle-frame calibration, speed estimation, GNSS/INS fusion, road
> constraints, and recovery when GNSS returns.

The public-facing explanation should remain simple:

> When GNSS disappears, IDR does not freeze. It uses the phone's motion
> sensors, vehicle alignment, speed estimation, and road constraints to keep
> the route moving, then hands control back to GNSS when the signal returns.

The project is not positioned as a replacement for normal navigation. It
fills the gap when navigation loses its satellite reference.

Important honesty rule:

- Do not claim lane-level accuracy without real measured evidence.
- Do not present synthetic zero drift as real tunnel performance.
- Do not claim a trained IO-VNBD neural model until one is trained and
  evaluated.
- Do not claim Android device validation until an APK is built and tested.

---

## 4. Expected SIH capabilities mapped to the project

### 4.1 In-vehicle alignment and calibration

The system should determine phone pitch, roll, yaw, and the signed forward
axis relative to the vehicle.

Implemented baseline:

- Stationary gravity-stability stage
- Forward-motion stage using GNSS bearing and speed
- Signed device-axis retention
- Explicit `COMPLETE` and `FAILED` states
- Reset support

Primary file:

[VehicleCalibration.kt](../mobile/app/src/main/java/org/sih/idr/VehicleCalibration.kt)

Remaining validation:

- Known-orientation automated test coverage
- Remount detection
- Multiple phone-holder orientations
- Physical phone validation

### 4.2 Speed and vibration estimation

The model pipeline contains:

- GNSS-anchored speed baseline
- Quality flags
- Acceleration smoothing
- Ridge speed-correction model
- Fixed-window temporal speed/vibration baseline
- JSON export/import
- Kotlin-compatible model schema

Primary files:

- [model.py](../ml/idr_ml/model.py)
- [temporal_model.py](../ml/idr_ml/temporal_model.py)
- [quality.py](../ml/idr_ml/quality.py)

Current status:

- Transparent statistical baselines exist.
- No permitted IO-VNBD dataset is present.
- No trained production neural model is present.
- No ONNX/TFLite artifact is present.
- Android inference latency is not measured.

### 4.3 Non-holonomic constraints and map matching

The engine supports:

- Forward-only vehicle propagation
- Segment projection
- Cross-track gating
- Heading gating
- Confidence scoring
- HMM-style connected road sequence matching
- JSON way import
- Small OSM XML import

Primary files:

- [fusion.py](../edge-engine/idr_engine/fusion.py)
- [constraints.py](../edge-engine/idr_engine/constraints.py)
- [map_io.py](../edge-engine/idr_engine/map_io.py)

Current status:

- The geometry and matcher primitives are implemented and tested.
- A real OSM extract is not committed.
- Real road-trace comparison has not been performed.
- Offline map packaging remains a data-preparation task.

### 4.4 GNSS/INS fusion

The fusion engine provides:

- GNSS initialization
- GNSS-aided mode
- Outage confirmation
- Dead-reckoning mode
- Confidence decay
- Timestamp validation
- Recovery hysteresis
- GNSS correction
- Optional map correction
- Optional bounded fusion-correction model

Primary file:

[fusion.py](../edge-engine/idr_engine/fusion.py)

Default behavior is classical and safe. The default correction model is a
no-op unless an explicit correction model is configured.

### 4.5 Seamless outage and recovery

The state machine intentionally avoids an immediate false transition:

1. A valid GNSS fix initializes the engine.
2. Missing GNSS starts an outage timer.
3. Dead reckoning begins after the configured confirmation interval.
4. Confidence decays during the outage.
5. GNSS recovery requires consecutive valid fixes.
6. Position correction resumes only after the recovery condition is met.

The Android controller separately detects stale GNSS and does not silently
reuse an old fix as a current measurement.

### 4.6 Real-time navigation interface

Implemented surfaces:

- Android map-first shell
- Browser-based deterministic replay demo

The Android UI contains:

- Route/map presentation
- Vehicle/status card
- Mode label
- Position label
- Diagnostics
- Start navigation action
- Calibration action
- Floating controls
- Rounded bottom sheet

The browser demo contains:

- GNSS-aided mode
- Dead-reckoning mode
- Recovery
- Confidence display
- Speed, distance, and update-rate display
- Reset and replay controls

Browser entry point:

[web-demo/index.html](../web-demo/index.html)

The browser demo is a presentation fallback, not a live sensor runtime.

---

## 5. Repository structure

```text
.
├── .ofa/                         ONEFORALL ownership and identity
├── .github/                      CI and repository automation
├── docs/                         Architecture, evidence, runbooks, handoffs
├── edge-engine/
│   ├── idr_engine/
│   │   ├── fusion.py             GNSS/INS state machine
│   │   ├── constraints.py        NHC and map matching
│   │   ├── adapters.py           External-IMU adapter
│   │   └── map_io.py             JSON/OSM XML road import
│   └── README.md
├── ml/
│   ├── idr_ml/
│   │   ├── dataset.py            Session loading and splits
│   │   ├── io_vnbd.py            Explicit CSV/IO-VNBD mapping
│   │   ├── model.py              Ridge speed model
│   │   ├── temporal_model.py     Temporal baseline
│   │   └── quality.py            Signal quality processing
│   └── README.md
├── mobile/
│   ├── idr_mobile/               Python mobile runtime seam
│   └── app/
│       └── src/main/
│           ├── java/org/sih/idr/
│           │   ├── MainActivity.kt
│           │   ├── SensorCaptureController.kt
│           │   ├── VehicleCalibration.kt
│           │   ├── VehicleFrameAdapter.kt
│           │   └── NativeNavigationEngine.kt
│           └── res/
│               ├── layout/
│               ├── drawable/
│               └── values/
├── rover/
│   ├── protocol.py               CRC/versioned telemetry contract
│   └── README.md
├── scripts/
│   ├── release_check.py
│   ├── generate_screening_evidence.py
│   ├── eval_outage.py
│   └── measure_throughput.py
├── shared/
│   └── idr/
│       ├── models.py             Frozen contracts
│       ├── replay.py             Deterministic replay
│       ├── metrics.py            Metrics
│       ├── benchmark.py          Benchmark report
│       ├── scenarios.py          Integration scenarios
│       ├── synthetic.py          Synthetic fixtures
│       ├── trace.py              JSONL traces
│       └── throughput.py         Rate measurement
├── tests/                        Cross-layer Python tests
└── web-demo/                     Dependency-free browser presentation
```

---

## 6. Shared data contracts

The shared layer is intentionally strict.

Contracts validate:

- Finite numeric values
- Latitude and longitude ranges
- Non-negative speed and accuracy
- Matching timestamps
- Confidence in `[0, 1]`
- Strictly increasing replay timestamps

Important shared objects:

- `ImuSample`
- `GnssFix`
- `SensorFrame`
- `NavigationState`
- `NavigationMode`
- Replay and trace structures

Do not loosen validation to make a demo appear successful. Invalid input must
produce a visible error or rejected sample.

---

## 7. Python engine behavior

The `FusionEngine` is platform-neutral. It receives a `SensorFrame` and
returns a navigation state.

Important defaults and behavior:

- An initial GNSS fix is required before inertial propagation.
- Outage confirmation defaults to a short configured interval.
- Recovery requires consecutive valid fixes.
- Confidence decays during an outage.
- Map correction is bounded by configuration and confidence.
- Timestamp gaps are rejected.
- Invalid finite values are rejected.
- `NoOpFusionCorrection` preserves classical behavior.
- `LinearFusionCorrection` can change acceleration scale, yaw bias, and GNSS
  gain within validated bounds.

External input:

- [adapters.py](../edge-engine/idr_engine/adapters.py) converts transport
  payloads into shared frames.
- [rover/protocol.py](../rover/protocol.py) defines a versioned, CRC-protected
  JSON-line telemetry envelope.

---

## 8. ML/data behavior

The IO-VNBD adapter requires explicit user-supplied column mappings. It does
not guess column names.

The evaluator requires:

- Input CSV
- Explicit column mapping JSON
- Timestamp
- IMU acceleration
- Yaw rate
- Truth coordinates
- Pre-outage GNSS initialization
- Requested outage interval

The evaluator fails closed when required evidence is absent.

Example:

```powershell
python scripts/eval_outage.py `
  --input C:/data/io-vnbd/session.csv `
  --columns C:/data/io-vnbd/columns.json `
  --outage-seconds 60 `
  --output docs/evidence/io-vnbd-60s.json
```

Do not commit:

- Raw IO-VNBD data
- Restricted recordings
- Private recordings
- Map extracts
- Credentials
- Signing keys
- Oversized binary model files

Record provenance in:

[data-provenance.md](data-provenance.md)

---

## 9. Android implementation

### Existing files

- [MainActivity.kt](../mobile/app/src/main/java/org/sih/idr/MainActivity.kt)
- [SensorCaptureController.kt](../mobile/app/src/main/java/org/sih/idr/SensorCaptureController.kt)
- [VehicleCalibration.kt](../mobile/app/src/main/java/org/sih/idr/VehicleCalibration.kt)
- [VehicleFrameAdapter.kt](../mobile/app/src/main/java/org/sih/idr/VehicleFrameAdapter.kt)
- [NativeNavigationEngine.kt](../mobile/app/src/main/java/org/sih/idr/NativeNavigationEngine.kt)
- [activity_main.xml](../mobile/app/src/main/res/layout/activity_main.xml)

### Native model contract

The Android model loader expects JSON with:

```json
{
  "model_type": "linear_speed_correction",
  "version": "0.1.0",
  "feature_names": [
    "bias",
    "forward_acceleration_mps2",
    "yaw_rate_rps",
    "absolute_acceleration_mps2"
  ],
  "weights": [0.0, 0.0, 0.0, 0.0]
}
```

The loader rejects:

- Wrong model type
- Missing version
- Feature/weight length mismatch
- Unknown feature names

The default Android model is neutral until a permitted trained artifact is
supplied.

### Android validation blocker

The environment previously reported:

```text
gradle=NOT_FOUND
adb=NOT_FOUND
kotlinc=NOT_FOUND
```

Therefore APK compilation, installation, device sensor behavior, Android
latency, and physical tunnel behavior remain unverified.

---

## 10. Browser demo

Open:

[web-demo/index.html](../web-demo/index.html)

Files:

- [index.html](../web-demo/index.html)
- [styles.css](../web-demo/styles.css)
- [app.js](../web-demo/app.js)
- [README.md](../web-demo/README.md)

Demo flow:

1. Initial `READY` state
2. Click `Start replay`
3. `GNSS-AIDED`
4. `DEAD-RECKONING`
5. `GNSS unavailable`
6. Confidence decreases visibly
7. `RECOVERING`
8. Return to `GNSS-AIDED`

It uses original SVG/CSS artwork and does not fetch map tiles or require an
API key.

---

## 11. Evidence and validation

Current verified state:

- **39 Python tests pass**
- Release certification passes
- Browser JavaScript syntax check passes
- UI asset check passes
- JSON/OSM map-import tests pass
- Model schema validation tests pass
- Deterministic throughput harness passes the configured 200 Hz target

Run tests:

```powershell
pytest -q
```

Run release certification:

```powershell
python scripts/release_check.py
```

Run throughput harness:

```powershell
python scripts/measure_throughput.py `
  --samples 2000 `
  --target-hz 200
```

Current synthetic report:

- 1 km synthetic route
- 60 km/h scenario
- 40-second GNSS outage
- 10 Hz replay
- Approximately zero numerical error
- Recovery around 50.1 seconds

Interpretation:

This validates deterministic replay and metric plumbing. It does not validate
smartphone, tunnel, IO-VNBD, lane-level, FOG, rover, or physical Android
performance.

Primary evidence:

- [synthetic-1km-report.json](evidence/synthetic-1km-report.json)
- [synthetic-1km-trajectory.svg](evidence/synthetic-1km-trajectory.svg)
- [benchmarking.md](benchmarking.md)
- [requirements-matrix.md](requirements-matrix.md)
- [limitations.md](limitations.md)
- [gap-audit.md](gap-audit.md)

---

## 12. Current requirement status

### Working baseline

- Shared contracts
- Deterministic replay
- Vehicle calibration
- Sensor capture seam
- GNSS/INS state machine
- Dead reckoning
- Confidence decay
- Recovery hysteresis
- Non-holonomic propagation
- Segment map matcher
- HMM-style matcher
- JSON/OSM XML map import boundary
- External-IMU adapter
- Rover telemetry protocol
- ML baseline model schemas
- Outage evaluation harness
- Android UI shell
- Browser demo
- Documentation and governance

### Partial or unverified

- Real IO-VNBD training and evaluation
- Production neural model
- ONNX/TFLite packaging
- Android APK build
- Physical Android device behavior
- Real GNSS blackout performance
- Real OSM extract evaluation
- Physical external-IMU/FOG measurement
- Rover hardware and firmware
- Lane-level accuracy

Full matrix:

[requirements-matrix.md](requirements-matrix.md)

---

## 13. Presentation plan for tomorrow

The presentation is designed for a 5–10 minute judge session with limited
technical background.

Main story:

1. A vehicle enters a tunnel.
2. GNSS disappears.
3. Normal navigation freezes or jumps.
4. The phone still senses motion.
5. IDR continues with calibrated motion and road constraints.
6. GNSS returns and the system recovers.
7. The team explains evidence and next validation honestly.

Recommended wording:

> When GNSS disappears, IDR does not freeze. It uses the phone's motion
> sensors, vehicle alignment, speed estimation, and road constraints to keep
> the route moving, then hands control back to GNSS when the signal returns.

Presentation guide:

[presentation-playbook.md](presentation-playbook.md)

Demo runbook:

[demo-runbook.md](demo-runbook.md)

Do not lead with:

- Equations
- Package structure
- Kalman-filter terminology
- Model architecture diagrams with no visual explanation
- Synthetic zero-drift numbers without the contract-test label

Lead with:

- Human problem
- Moving vehicle despite missing satellites
- Visible state transition
- Practical impact
- Honest validation boundary

---

## 14. Production frontend handoff

The production-ready mobile UI is intentionally being delegated to a
frontend-focused teammate. Their work must remain separate from the estimator
core.

Full handoff:

[frontend-handoff.md](frontend-handoff.md)

Frontend may change:

- Android XML/Compose layout
- Colors
- Typography
- Drawables
- Icons
- Animations
- Map artwork
- UI copy
- State presentation

Frontend must not directly change without coordination:

- `NativeNavigationEngine.kt`
- `VehicleFrameAdapter.kt`
- `VehicleCalibration.kt`
- `SensorCaptureController.kt`
- `shared/`
- `edge-engine/`
- `ml/`
- `tests/`
- `scripts/`
- Evidence and requirements documents

Recommended boundary:

```text
SensorCaptureController
        |
        v
NativeNavigationEngine
        |
        v
NavigationUiStateAdapter
        |
        v
Production Android UI
```

The UI should consume immutable state such as:

- Mode
- Position
- Speed
- Heading
- Confidence
- Update rate
- GNSS age
- Calibration message
- Diagnostics
- Route progress
- Running status
- Position validity

The frontend developer should:

1. Read [frontend-handoff.md](frontend-handoff.md).
2. Check `ofa status`.
3. Coordinate the mobile-zone claim.
4. Use a feature branch named `frontend/<short-name>`.
5. Modify only agreed frontend files.
6. Avoid formatting unrelated Kotlin/resources.
7. Run `ofa guard --strict`.
8. Open a focused PR.
9. Let the main operator run cross-zone tests and merge.

---

## 15. ONEFORALL collaboration rules

Current ownership:

- `ml/`: available; ML/data contributor zone
- `edge-engine/`: available; fusion-engine contributor zone
- `mobile/`: claimed by `@FreakyAdy`
- `shared/`: claimed by `@FreakyAdy`

Shared/main-operator paths include:

- `shared/`
- `tests/`
- `docs/`
- `maps/`
- `.github/`
- `.ofa/`
- `.cursor/`
- `README.md`
- `scripts/`
- `rover/`

Before changing files:

```powershell
ofa status
```

Before committing:

```powershell
ofa guard --strict
```

Never:

- Commit directly to `main` or `master`
- Edit another contributor's zone without coordination
- Revert unrelated work
- Commit secrets
- Commit raw datasets
- Commit private recordings
- Commit restricted map extracts
- Claim unverified performance
- Hide sensor, model, map, or calibration failures

---

## 16. Recommended next actions

### Tonight / presentation preparation

1. Open the browser demo and reset it to `READY`.
2. Verify the replay reaches `DEAD-RECKONING`.
3. Keep the trajectory plot and benchmark report in separate tabs.
4. Rehearse the 5–10 minute script once with one presenter and one operator.
5. Prepare the Android fallback only if the APK/device is already available.
6. Do not change core logic immediately before the presentation.

### After presentation

1. Obtain a permitted IO-VNBD subset.
2. Record source, license, checksum, mapping, and session split.
3. Train and evaluate the speed/vibration model.
4. Generate real outage reports and plots.
5. Export and measure an Android artifact.
6. Build and install the APK.
7. Measure phone 10 Hz behavior.
8. Import a real offline OSM region.
9. Evaluate real road traces.
10. Measure external-IMU/FOG throughput.
11. Implement rover firmware and bridge if hardware is available.

---

## 17. Final handoff summary

The repository is a real, tested navigation prototype with clear evidence
boundaries. It is stronger when presented as an honest engineering system
rather than as an already-certified lane-level product.

The immediate success criterion is a clear judge experience:

1. They understand the failure of GNSS-only navigation.
2. They understand why phone motion sensors help.
3. They see the route continue during blackout.
4. They see explicit recovery.
5. They understand the system can work without OBD hardware.
6. They trust the team because limitations are stated clearly.

The production frontend can proceed independently when it follows the
state-adapter and ownership rules in
[frontend-handoff.md](frontend-handoff.md).
