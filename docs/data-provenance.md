# Dataset and Model Provenance

This file is intentionally incomplete until the permitted IO-VNBD subset is
provided. The repository does not guess the dataset schema or claim results
from unavailable files.

## Required record for each evaluation

| Field | Value |
| --- | --- |
| Dataset name | IO-VNBD |
| Subset or release | `REQUIRED` |
| Source URL or transfer record | `REQUIRED` |
| License and permitted use | `REQUIRED` |
| Local cache path | `REQUIRED; never commit the dataset` |
| File checksums | `REQUIRED` |
| Verified columns | `REQUIRED after inspecting files` |
| Session IDs used | `REQUIRED` |
| Train/evaluation split | Complete sessions only |
| Random seed | `REQUIRED` |
| Evaluation script commit | `REQUIRED` |
| Model artifact version | `REQUIRED` |
| Map source and version | `REQUIRED if map matching is evaluated` |

## Integrity rules

1. Inspect the supplied files before writing `ColumnMap` values.
2. Keep complete sessions, not adjacent windows, in one split.
3. Compute normalization statistics from training sessions only.
4. Store checksums and configuration beside generated evidence.
5. Do not commit source data, private recordings, map extracts, credentials,
   or oversized model binaries.

The current [`io_vnbd.py`](../ml/idr_ml/io_vnbd.py) adapter requires an
explicit mapping and fails rather than guessing field names.

## Generated evidence contract

Every real-data report should be accompanied by a JSON metadata object with:

```json
{
  "dataset": {"name": "IO-VNBD", "release": "REQUIRED", "sha256": "REQUIRED"},
  "mapping": "columns.json",
  "sessions": {"train": [], "evaluation": []},
  "model": {"type": "linear_speed_correction", "version": "REQUIRED"},
  "evaluation": {"outage_seconds": 60, "seed": "REQUIRED"},
  "map": {"source": "REQUIRED", "version": "REQUIRED"}
}
```

The repository may contain this metadata and derived plots, but not the raw
dataset or restricted map extract. Missing required values must remain
`REQUIRED`; they must not be replaced with guessed provenance.
