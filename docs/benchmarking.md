# Benchmark certification

`idr.benchmark.certify_replay` is the common report path for synthetic,
IO-VNBD, phone, and external-IMU traces.

## Metrics

- **Travelled distance:** sum of consecutive ground-truth local-frame
  displacements.
- **Maximum position error:** maximum Euclidean distance between estimated and
  ground-truth local-frame positions.
- **Drift percentage:** maximum position error divided by travelled distance,
  multiplied by 100.
- **Update rate:** `(sample_count - 1) / duration_seconds`.
- **Outage transition latency:** time from the first GNSS-missing frame to the
  first frame emitted in `dead_reckoning` mode.
- **Recovery timestamp:** first GNSS-aided state immediately following a
  dead-reckoning state.

The default certification thresholds are drift under 10% and at least 10 Hz.
These thresholds are evaluated as explicit booleans in the JSON report; a
passing report does not imply lane-level accuracy unless the input trace has
lane-level ground truth.

## Current synthetic baseline

The straight-line synthetic test uses 10 Hz samples, 10 m/s speed, and a
four-second GNSS outage. The classical replay baseline currently passes the
drift and update-rate thresholds with zero synthetic position error because
the generated inertial conditions are ideal. This is a contract/replay
sanity check, not evidence of real-world smartphone performance.

Real IO-VNBD and phone recordings must be certified separately, with the
session ID, source checksum, outage interval, estimator/model version, and
map configuration recorded alongside the report.
