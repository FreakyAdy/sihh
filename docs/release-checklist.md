# Screening release checklist

- [ ] `ofa doctor` passes for the main operator.
- [ ] `ofa guard --strict` passes with no ownership violations.
- [ ] Full test suite passes from a clean checkout.
- [ ] `scripts/release_check.py` reports `"passed": true`.
- [ ] Model card, architecture, benchmark methodology, and demo runbook are
      included with the release.
- [ ] Dataset source, checksum, split IDs, model version, and map version are
      recorded for every real benchmark.
- [ ] No source datasets, recordings, map extracts, credentials, keystores,
      or unreviewed model binaries are committed.
- [ ] Android package and edge package have version metadata and checksums.
- [ ] Deterministic replay fallback has been rehearsed.
- [ ] Unmet real-world targets and known failure modes are disclosed.
