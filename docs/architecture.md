# Architecture

## Runtime flow

```text
phone IMU/GNSS or external IMU
              |
              v
      sensor normalization
              |
              v
  calibration + quality detection
              |
              v
 learned speed/vibration correction
              |
              v
   GNSS/INS state estimator ---- offline road candidates
              |                         |
              +------ map/NHC constraints
              |
              v
 position, velocity, heading, mode, confidence, diagnostics
```

Training and evaluation run offline. Mobile inference must use bounded memory and compute, while the edge engine must accept higher-rate external IMU streams without changing the shared state contract.

## Ownership boundary

`shared/` defines data contracts and is reviewed by the main operator. `ml/`, `edge-engine/`, and `mobile/` consume those contracts and may evolve independently as long as compatibility tests pass.

## Frozen trace contract

Replay records are JSONL objects with one timestamped IMU sample and an
optional GNSS fix:

```json
{
  "imu": {
    "timestamp_s": 12.3,
    "forward_acceleration_mps2": 0.2,
    "yaw_rate_rps": 0.01
  },
  "gnss": {
    "timestamp_s": 12.3,
    "latitude_deg": 28.6139,
    "longitude_deg": 77.209,
    "speed_mps": 8.4,
    "horizontal_accuracy_m": 4.0
  },
  "truth_x_m": 103.2,
  "truth_y_m": 0.4
}
```

IMU acceleration and yaw rate are expressed in the calibrated vehicle frame.
The local replay frame uses east as `x` and north as `y`; geographic input is
WGS84 latitude/longitude in degrees. `truth_x_m` and `truth_y_m` are optional
evaluation-only fields and must not be used by runtime estimators.

The shared Python implementation is in `shared/idr/`. Use
`idr.trace.read_jsonl` and `idr.trace.write_jsonl` for interchange; both reject
malformed records and non-increasing timestamps.

## Safety and failure behavior

The estimator must expose confidence and mode rather than silently returning stale positions. If GNSS, IMU, map data, or model inputs become invalid, the runtime reports the degraded condition and preserves the last valid timestamped state.

The first edge-engine implementation is in `edge-engine/idr_engine/`. It keeps
outage detection and recovery hysteresis explicit, performs non-holonomic
forward propagation, and accepts optional bounded `MapMatcher` corrections.
External IMU transports should convert into `SensorFrame` through the adapter
without placing transport-specific code in the estimator.
