<!-- OFA:START -->

## ONEFORALL — Zone Ownership (Auto-generated)

> ⚠️ This section is managed by ONEFORALL (ofa). Do not edit manually.
> Edit `.ofa/config.yml` and run `ofa sync` to update.

This project uses zone-based ownership for multi-developer AI collaboration.

### Current Ownership Map

| Zone | Owner | Paths | Notes |
|------|-------|-------|-------|
| ml | @FreakyAdy | ml/ | IO-VNBD ingestion, preprocessing, training, evaluation, and model exports |
| engine | @FreakyAdy | edge-engine/ | Platform-neutral GNSS/INS fusion, dead reckoning, map constraints, and adapters |
| mobile | @FreakyAdy | mobile/ | Smartphone sensors, on-device inference, navigation UI, and offline maps |
| frontend | @FreakyAdy | web-demo/ | Web demo presentation layer, Apple Maps UI, telemetry HUD, and map canvas |
| shared | @FreakyAdy | shared/, tests/, docs/, maps/, .github/, .ofa/, .cursor/, README.md/, .gitignore/, AGENTS.md/, CLAUDE.md/, GEMINI.md/, scripts/, rover/, .obsidian/, run_demo.bat/, run_demo.ps1/ | Main-operator-owned contracts, fixtures, CI, documentation, and map tooling |

### Rules

1. **Check zone ownership before editing any file.**
2. **Do NOT modify files in zones owned by another developer.**
3. **Shared zones require review from all active zone owners.**
4. **Use feature branches, never commit to main directly.**
5. **Run `ofa guard` before committing to verify boundaries.**

<!-- OFA:END -->