# IO-VNBD Outage Evaluation

[`scripts/eval_outage.py`](../scripts/eval_outage.py) is the fail-closed
evaluation entry point for permitted IO-VNBD or compatible CSV exports.

It requires:

- the original CSV outside the repository;
- a JSON `ColumnMap` created after inspecting that CSV;
- forward acceleration, yaw rate, timestamps, and truth local-frame `x/y`;
- GNSS latitude/longitude before and after the injected outage.

Example:

```powershell
python scripts/eval_outage.py `
  --input C:/data/io-vnbd/session.csv `
  --columns C:/data/io-vnbd/columns.json `
  --outage-seconds 60 `
  --output docs/evidence/io-vnbd-60s.json
```

The evaluator masks GNSS inside repeated outage windows, replays the
classical fusion baseline, and reports per-window drift plus median, p90, and
worst-case drift. It refuses to produce a result when truth coordinates or a
pre-outage GNSS fix are unavailable.

The current repository has no IO-VNBD files, verified schema, or permitted
column mapping. Therefore no real-data result is claimed in the README.
