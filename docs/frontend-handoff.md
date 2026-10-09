# Production frontend handoff

## Mission

Build the production-ready mobile presentation layer for IDR Navigation. The
frontend should make the state of the navigation engine immediately
understandable to a driver and to a non-technical judge, while preserving the
existing estimator behavior and evidence boundaries.

This document is the starting context for the frontend developer and their
coding agent. Read it before claiming a zone or editing a file.

## Project context

IDR is a smartphone/external-IMU navigation engine for GNSS-denied segments.
The system:

1. Calibrates the phone's orientation relative to vehicle motion.
2. Converts raw phone axes to a vehicle-frame sample.
3. Fuses GNSS and inertial motion.
4. Enters dead reckoning after a confirmed GNSS outage.
5. Applies non-holonomic and map constraints when available.
6. Recovers to GNSS-aided mode after consecutive valid fixes.
7. Exposes confidence and diagnostics instead of silently using stale data.

Current evidence is a deterministic Python baseline plus an Android runtime
seam. Real IO-VNBD results, a physical Android run, real OSM evaluation, and a
trained production artifact are not yet available. The frontend must not imply
that they exist.

Read first:

- [README.md](../README.md)
- [requirements-matrix.md](requirements-matrix.md)
- [limitations.md](limitations.md)
- [demo-runbook.md](demo-runbook.md)
- [architecture.md](architecture.md)
- [MainActivity.kt](../mobile/app/src/main/java/org/sih/idr/MainActivity.kt)
- [NativeNavigationEngine.kt](../mobile/app/src/main/java/org/sih/idr/NativeNavigationEngine.kt)
- [SensorCaptureController.kt](../mobile/app/src/main/java/org/sih/idr/SensorCaptureController.kt)
- [VehicleCalibration.kt](../mobile/app/src/main/java/org/sih/idr/VehicleCalibration.kt)

## Ownership and conflict prevention

ONEFORALL is the project ownership system. Check status before editing:

```powershell
ofa status
ofa claim mobile
```

The `mobile` zone is assigned to the main operator. A frontend contributor
must coordinate the claim with the main operator before starting work.

### Frontend-owned files

The frontend contributor may work on:

- `mobile/app/src/main/res/layout/`
- `mobile/app/src/main/res/drawable/`
- `mobile/app/src/main/res/mipmap/`
- `mobile/app/src/main/res/values/`
- Explicitly assigned UI-only Kotlin files under
  `mobile/app/src/main/java/org/sih/idr/`
- UI screenshots or local design assets that are explicitly requested

### Main-operator-owned files

Do not edit these without a coordinated interface change:

- `shared/`
- `edge-engine/`
- `ml/`
- `tests/`
- `scripts/`
- `docs/`
- `README.md`
- `rover/`
- `NativeNavigationEngine.kt`
- `VehicleFrameAdapter.kt`
- `VehicleCalibration.kt`
- `SensorCaptureController.kt`

If the UI needs a new field or state, write a short interface request for the
main operator. Do not add a direct dependency on internal engine fields.

### Branch and integration rules

1. Work on a feature branch named `frontend/<short-name>`.
2. Never commit directly to `main` or `master`.
3. Keep commits small and UI-focused.
4. Run `ofa guard --strict` before opening a PR.
5. Do not reformat or rewrite unrelated Kotlin/resources.
6. Resolve integration conflicts through the main operator; do not force-push
   over another person's branch.
7. The main operator owns the final merge and cross-zone test run.

## Safe integration boundary

The intended production design is a view-model adapter between engine callbacks
and Android views:

```text
SensorCaptureController
        |
        v
NativeNavigationEngine
        |
        v
NavigationUiStateAdapter  <-- frontend boundary
        |
        v
Activity / fragments / Compose UI
```

The adapter should expose immutable display state, not engine internals:

```text
NavigationUiState
  mode: INITIALIZING | CALIBRATING | GNSS_AIDED | DEAD_RECKONING | RECOVERING | ERROR
  latitude: optional number
  longitude: optional number
  speedMps: number
  headingRad: number
  confidence: 0..1
  updateRateHz: optional number
  gnssAgeSeconds: optional number
  calibrationMessage: string
  diagnostics: string
  routeProgress: optional number
  isRunning: boolean
  hasValidPosition: boolean
```

This is a proposed presentation contract. It must be implemented through a
small compatibility-preserving change by the main operator before the
frontend consumes fields that do not currently exist.

## State-to-visual mapping

| State | Primary visual | Required user message |
| --- | --- | --- |
| `INITIALIZING` | Neutral status card | `Starting sensors` |
| `CALIBRATING` | Calibration progress card | `Keep still, then drive straight` |
| `GNSS_AIDED` | Blue route and solid marker | `GNSS-aided navigation` |
| `DEAD_RECKONING` | Amber badge and continuous marker | `GNSS unavailable; inertial tracking active` |
| `RECOVERING` | Violet badge and signal pulse | `Reacquiring GNSS` |
| `ERROR` | Red diagnostic card | Specific failure and next action |

Never show `GNSS-AIDED` when the engine is in dead reckoning. Never hide a
stale-GNSS warning, calibration failure, dropped sample count, missing model,
or permission error behind an animation.

## UI requirements

- Map-first composition with a clear vehicle marker.
- Large, readable mode and confidence labels.
- Rounded bottom sheet for next action, speed, distance, and update rate.
- A visible calibration action before navigation starts.
- A visible stop/reset path.
- Accessible contrast and touch targets.
- No network map requirement for the deterministic demo.
- Use original route artwork and IDR branding.
- Keep diagnostics expandable but never unavailable.
- Do not display "lane-level accuracy" as a result unless a measured report
  supports that statement.

## What the frontend must not change

- Fusion equations, outage thresholds, recovery hysteresis, map correction
  limits, or confidence decay.
- Sensor normalization, vehicle-frame calibration, or timestamp validation.
- ML model JSON schema or fallback coefficients.
- Benchmark calculations, synthetic reports, or requirements statuses.
- Dataset provenance, license text, or performance numbers.

## Integration workflow

1. Read the project files listed above.
2. Confirm ownership and claim the mobile zone with the main operator.
3. Create the feature branch.
4. Build the UI against existing view IDs or a proposed adapter, not against
   private engine state.
5. Add UI-only resources and state rendering.
6. Test every state with deterministic sample data or a preview fixture.
7. Verify permission denial, calibration failure, stale GNSS, missing model,
   queue pressure, and recovery visuals.
8. Run `ofa guard --strict`.
9. Open a PR describing changed UI files and any requested interface change.
10. Let the main operator run cross-zone tests and integrate.

## Acceptance checklist

- [ ] No files outside the agreed frontend scope were modified.
- [ ] All required states have a visible label and safe fallback.
- [ ] No stale or invalid position is presented as current.
- [ ] Start, stop, reset, and calibrate actions are clear.
- [ ] UI remains usable on a small phone screen.
- [ ] TalkBack/content descriptions exist for critical controls.
- [ ] Browser demo visual language and Android visual language agree.
- [ ] `ofa guard --strict` passes.
- [ ] Android build/device limitations are documented if still blocked.
- [ ] No unsupported accuracy or AI claims were added.

## Handoff completion definition

The frontend task is complete when the production UI can render the immutable
navigation state, demonstrate all degraded/recovery modes, preserve the
existing estimator behavior, pass ownership checks, and be merged by the main
operator without conflicts. A visually polished screen without explicit
failure and confidence states is not complete.
