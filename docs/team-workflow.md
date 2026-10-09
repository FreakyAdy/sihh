# Team workflow

1. The main operator assigns a zone and confirms the contributor's GitHub identity.
2. The contributor claims only that zone with `ofa claim <zone>`.
3. Work is developed on a short-lived branch and checked with `ofa guard --staged`.
4. Pull requests must include tests or replay evidence for behavior changes.
5. Changes to `shared/`, `tests/`, CI, or public interfaces require main-operator review.
6. The main operator integrates branches, runs the cross-zone benchmark, and owns release/demo branches.

Do not resolve a boundary violation by editing another zone. Coordinate an interface change through a PR owned by the main operator.
