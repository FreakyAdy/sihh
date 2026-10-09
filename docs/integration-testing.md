# Integrated scenario testing

The cross-zone suite in `tests/test_integration_scenarios.py` runs the shared
contract, fusion engine, and mobile runtime together. It covers:

- GNSS blackout and recovery through the mobile queue
- intermittent GNSS fixes
- out-of-order timestamps with explicit failure reporting
- bounded mobile queue pressure and dropped-sample diagnostics

Run all scenarios with:

```powershell
& 'C:/Program Files/Python314/python.exe' -m unittest discover -s tests -v
```

Scenario failures must remain visible in the result. Do not convert invalid
input, stale state, or sensor gaps into a successful navigation state.
