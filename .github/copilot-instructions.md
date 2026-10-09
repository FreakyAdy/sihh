# ONEFORALL ownership instructions

This repository is coordinated through `.ofa/config.yml`. Before editing a file, identify its zone with `ofa status`.

- `ml/` is reserved for the ML/data contributor.
- `edge-engine/` is reserved for the fusion-engine contributor.
- `mobile/` is reserved for the mobile contributor.
- `shared/`, `tests/`, `docs/`, `maps/`, and `.github/` are owned by the main operator, `@FreakyAdy`.

Do not edit another contributor's zone. If an interface change is needed, describe it in a pull request and let the main operator update shared contracts. Work on feature branches, run `ofa guard` before committing, and include tests or replay evidence for behavior changes.

The navigation system must report explicit sensor/model/map degradation and confidence; do not silently substitute stale or invalid position data.
