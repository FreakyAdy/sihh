# Fusion engine

`idr_engine.FusionEngine` is the platform-neutral streaming baseline. It
accepts the frozen `shared/idr.SensorFrame` contract and emits
`NavigationState` objects for phone or external-IMU replay.

The current implementation provides:

- timestamp and gap validation
- inertial speed/heading/position propagation
- explicit initialization, GNSS-aided, and dead-reckoning modes
- configurable outage confirmation and recovery hysteresis
- confidence decay during an outage
- GNSS position/speed correction when fixes are accepted
- bounded map-matcher corrections during dead reckoning
- transport-neutral external-IMU adapter

The propagation is non-holonomic by construction: the baseline only advances
along the current vehicle heading and does not introduce lateral or vertical
motion. A `MapMatcher` may provide a bounded local-road correction during an
outage. `NoOpMapMatcher` is the explicit fallback when offline map data is not
available.

The estimator intentionally remains classical while the ML zone develops
learned speed and sensor corrections. Map matching and non-holonomic
constraints should be added behind bounded correction interfaces rather than
silently replacing the estimator state.
