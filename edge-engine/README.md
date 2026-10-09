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
- dependency-free segment map matching with distance and heading gating
- transport-neutral external-IMU adapter
- active bounded fusion-correction model seam for acceleration, yaw bias, and
  GNSS gain

The propagation is non-holonomic by construction: the baseline only advances
along the current vehicle heading and does not introduce lateral or vertical
motion. A `MapMatcher` may provide a bounded local-road correction during an
outage. `NoOpMapMatcher` is the explicit fallback when offline map data is not
available. `SegmentMapMatcher` is the included deterministic local-map
implementation. An offline OSM importer can convert road way geometry into
`RoadSegment` values without changing the fusion state machine. Candidates are
projected onto the nearest segment and rejected when cross-track distance or
heading error exceeds configured limits.

`LinearFusionCorrection` is a transparent adaptive baseline that is applied
inside propagation and GNSS recovery. It is the integration point for a
trained model to predict acceleration scale, yaw drift, and measurement gain.
The default `NoOpFusionCorrection` preserves the classical behavior until
trained weights and real-trace evidence are available.
