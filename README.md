# SIH Intelligent Dead Reckoning

Navigation application and edge engine for GNSS-denied vehicle positioning using smartphone or external IMU data.

## Repository governance

This repository uses [ONEFORALL](https://github.com/FreakyAdy/ONEFORALL) as its ownership and AI-agent coordination layer. The source of truth for boundaries is `[.ofa/config.yml](.ofa/config.yml)`.

The main operator owns integration, shared contracts, CI, documentation, releases, and the final SIH demo. Contributors work only in their claimed zone:

| Zone | Scope | Owner |
| --- | --- | --- |
| `ml` | IO-VNBD data, preprocessing, training, evaluation, model exports | Assigned teammate |
| `engine` | GNSS/INS fusion, dead reckoning, map constraints, external-IMU adapters | Assigned teammate |
| `mobile` | Android sensors, on-device runtime, UI, offline maps | Assigned teammate |
| `shared` | Contracts, fixtures, tests, CI, docs, map tooling | Main operator |

Before making changes:

```powershell
npm install -g github:FreakyAdy/ONEFORALL
ofa whoami --set <your-github-handle>
ofa status
ofa claim <your-zone>
ofa guard --staged
```

Never commit the full IO-VNBD dataset, proprietary recordings, map extracts, credentials, signing keys, or generated model files that exceed repository limits. Use documented local download/cache steps instead.

## Planned packages

- `shared/`: versioned IMU, GNSS, calibration, state, trajectory, and diagnostics contracts
- `edge-engine/`: platform-neutral estimator and external-IMU adapters
- `ml/`: reproducible dataset, training, export, and benchmark pipelines
- `mobile/`: smartphone capture, on-device inference, offline map display, and diagnostics
- `tests/`: deterministic replay fixtures and cross-package validation
- `docs/`: architecture, setup, demo, and benchmark evidence
- `maps/`: offline map import and cache tooling

The first vertical slice must replay a permitted IO-VNBD subset, produce a GNSS-aided/dead-reckoning trajectory, and report drift percentage, update rate, outage transition latency, and recovery behavior.

## Run the replay baseline

The first shared vertical slice is dependency-free Python and can run before the
mobile and ML toolchains are installed:

```powershell
py -m unittest discover -s tests -v
```

The public contracts live in [shared/idr/models.py](shared/idr/models.py), the
classical replay baseline is in [shared/idr/replay.py](shared/idr/replay.py),
benchmark calculations are in [shared/idr/metrics.py](shared/idr/metrics.py),
and JSONL interchange is in [shared/idr/trace.py](shared/idr/trace.py).
Cross-zone scenarios are documented in
[docs/integration-testing.md](docs/integration-testing.md).
