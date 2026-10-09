# SIH screening demo runbook

## Before the demo

1. Use a clean checkout and run the documented Python test command.
2. Run `scripts/release_check.py` and save its JSON output with the demo build.
3. Verify the selected Android device has sensor and location permissions,
   sufficient battery, and the offline map region cached.
4. Verify the engine, model, map, and trace versions shown in the diagnostic
   panel.
5. Keep the deterministic replay fallback available in case live GNSS or
   sensor conditions are unreliable.

## Live flow

1. Start with GNSS-aided mode visible and show update age, confidence, and
   current speed.
2. Begin the controlled route or replay trace.
3. Trigger the GNSS blackout or select the recorded tunnel interval.
4. Show transition to dead reckoning, confidence decay, and uninterrupted
   vehicle marker updates.
5. Show the map-constrained trajectory and diagnostics without claiming more
   accuracy than the benchmark report supports.
6. Restore GNSS and show recovery hysteresis before returning to GNSS-aided
   mode.
7. Open the benchmark report and explain drift, update rate, transition
   latency, and limitations.

## Failure fallback

If a live sensor, map, model, or permission fails, stop and show the explicit
diagnostic state. Run the deterministic replay instead of masking the failure
with stale data. The evaluator should see that the system fails visibly and
recovers predictably.
