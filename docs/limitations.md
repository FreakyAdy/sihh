# Limitations and Validation Boundary

## Evidence currently available

The repository contains deterministic Python tests, a synthetic 1 km outage
report, a dependency-free road-segment matcher, Android sensor/calibration
code, and an injectable model schema.

## Not yet demonstrated

- Performance on a real IO-VNBD subset.
- A trained temporal speed or vibration model.
- Android inference latency from a trained artifact.
- APK installation and physical-phone behavior.
- Real tunnel or urban-canyon behavior.
- OSM import and HMM road-graph matching.
- A learned adaptive GNSS/INS fusion correction.
- Approximately 200 Hz FOG or external-IMU measurement.
- Rover firmware, bridge, truth course, or slip experiments.

## Interpretation rules

- Synthetic zero drift is a contract-test result, not a field result.
- The ridge model is a baseline and fallback, not a final AI claim.
- Segment projection is map matching at the local geometry level, not HMM
  graph matching.
- The Android runtime is not certified until it is built and tested on a
  physical device.
- LiDAR and camera are not dead-reckoning sensors in the current system.
