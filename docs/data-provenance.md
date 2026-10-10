# Dataset and Model Provenance

This file is intentionally incomplete until the permitted IO-VNBD subset is
provided. The repository does not guess the dataset schema or claim results
from unavailable files.

## Required record for each evaluation

| Field | Value |
| --- | --- |
| Dataset name | IO-VNBD |
| Subset or release | `REQUIRED` |
| Source URL or transfer record | https://github.com/onyekpeu/IO-VNBD |
| License and permitted use | `REQUIRED — confirm from dataset README before evaluation` |
| Local cache path | `REQUIRED; never commit the dataset` |
| File checksums (SHA-256) | `REQUIRED` |
| Verified column names | `REQUIRED after inspecting CSV header` |
| Session IDs used | `REQUIRED` |
| Train/evaluation split | Complete sessions only (seed=42 by default) |
| Random seed | 42 (configurable via `--seed` in `train_io_vnbd.py`) |
| Evaluation script commit | `REQUIRED` |
| Model artifact version | `REQUIRED` |
| Map source and version | `REQUIRED if map matching is evaluated` |

## Column map

After downloading IO-VNBD, inspect the CSV header with:

```powershell
python -c "
import csv
r = csv.DictReader(open('C:/data/io-vnbd/session.csv'))
print(r.fieldnames)
"
```

Then update `ml/idr_ml/io_vnbd_columns_template.json` with the real column
names and save a copy beside each evaluation report.

## Integrity rules

1. Inspect the supplied files before writing `ColumnMap` values.
2. Keep complete sessions, not adjacent windows, in one split.
3. Compute normalization statistics from training sessions only.
4. Store checksums and configuration beside generated evidence.
5. Do not commit source data, private recordings, map extracts, credentials,
   or oversized model binaries.
6. **Drift measurement** must use the outage-only window metric (Phase 1 fix in
   `scripts/eval_outage.py` and `shared/idr/metrics.py`).  Never use full-session
   error as a proxy for GNSS-denied performance.

The current [`io_vnbd.py`](../ml/idr_ml/io_vnbd.py) adapter validates all
configured columns and rejects non-monotonic timestamps.

## Training and evaluation workflow

```powershell
# Step 1: Inspect CSV header and update column map
# Step 2: Run training + evaluation pipeline
python scripts/train_io_vnbd.py `
    --input      C:/data/io-vnbd/session.csv `
    --columns    ml/idr_ml/io_vnbd_columns_template.json `
    --outage-seconds 60 `
    --output-dir docs/evidence/io-vnbd/

# Outputs committed to repository:
#   docs/evidence/io-vnbd/model.json
#   docs/evidence/io-vnbd/evaluation-report.json
#   docs/evidence/io-vnbd/trajectory-<session_id>.svg
```

## Generated evidence contract

Every real-data report must be accompanied by a JSON metadata object with:

```json
{
  "dataset": {"name": "IO-VNBD", "release": "REQUIRED", "sha256": "REQUIRED"},
  "mapping": "io_vnbd_columns_template.json",
  "sessions": {"train": [], "evaluation": []},
  "model": {"type": "linear_speed_correction", "version": "REQUIRED"},
  "evaluation": {"outage_seconds": 60, "seed": 42},
  "map": {"source": "REQUIRED", "version": "REQUIRED"}
}
```

The repository may contain this metadata and derived plots, but not the raw
dataset or restricted map extract. Missing required values must remain
`REQUIRED`; they must not be replaced with guessed provenance.
