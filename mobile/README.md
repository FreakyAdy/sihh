# Mobile runtime

`idr_mobile.MobileRuntime` is the first testable mobile vertical slice. An
Android sensor callback should normalize device data into `RuntimeSample`,
submit it quickly, and let a worker drain the bounded queue into the shared
fusion engine.

The runtime:

- never runs estimation in `submit`, keeping callback work bounded
- drops oldest samples when the queue is full and reports the count
- rejects use before `start` and clears pending work on `stop`
- surfaces estimator input errors through diagnostics instead of returning a
  success-shaped fallback
- exposes processed count, queue depth, health, and last error for the UI

The current Python adapter is also the deterministic integration seam for the
future Android/Kotlin sensor implementation.
