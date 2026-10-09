# Mobile runtime

`idr_mobile.MobileRuntime` is the first testable mobile vertical slice. An
Android sensor callback should normalize device data into `RuntimeSample`,
submit it quickly, and let a worker drain the bounded queue into the shared
fusion engine.

The runtime:

- never runs estimation in `submit`, keeping callback work bounded
- drops oldest samples when the queue is full and reports the count
- rejects use before `start` and clears pending work on `stop`
- surfaces estimator input errors through diagnostics instead of returning a
  success-shaped fallback
- exposes processed count, queue depth, health, and last error for the UI

The current Python adapter is also the deterministic integration seam for the
future Android/Kotlin sensor implementation.

## Android shell

The native application shell is under `app/`. It currently provides:

- Gradle/Kotlin Android project configuration
- runtime location permission request
- a diagnostic-first navigation screen
- accelerometer, gyroscope, and GPS provider capture
- optional magnetometer capture for heading calibration
- lifecycle-safe sensor registration/unregistration
- explicit sample counts and provider health diagnostics

Build locally after installing Gradle and an Android SDK:

```powershell
gradlew.bat :app:assembleDebug
```

The current native callback emits calibrated-frame input prerequisites, but the
vehicle-frame alignment and engine adapter are still pending. It intentionally
does not present raw device-frame values as lane-level navigation output.

`VehicleCalibration` uses two stages: keep the phone/vehicle stationary for a
stable gravity estimate, then drive straight with a valid GNSS bearing and
speed. Failed stability checks enter an explicit failed state; calibration is
never silently assumed.

`VehicleFrameAdapter` now provides the explicit native conversion boundary. It
requires a configured vehicle heading and device forward axis before producing
longitudinal acceleration and yaw-rate samples. Until configured, the app shows
`Calibration required` rather than treating raw phone axes as vehicle axes.
