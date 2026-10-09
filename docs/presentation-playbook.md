# SIH judge presentation playbook

## Purpose

This playbook is for a 5–10 minute presentation to judges who may not have a
deep navigation or machine-learning background. The goal is to make the
problem visible in seconds, explain the solution in plain language, demonstrate
the working state transition, and make only evidence-backed claims.

The central sentence is:

> When GNSS disappears, IDR does not freeze. It uses the phone's motion
> sensors, vehicle alignment, speed estimation, and road constraints to keep
> the route moving, then hands control back to GNSS when the signal returns.

## Presentation rules

- Explain the human consequence before naming the algorithm.
- Use one idea per screen. Do not show source code during the main pitch.
- Prefer "motion sensors" over "IMU" until the technical explanation.
- Prefer "road shape constrains the estimate" over "HMM map matching".
- Show the mode label and confidence; never hide degraded conditions.
- Keep synthetic evidence labelled as a deterministic contract test.
- Do not claim lane-level accuracy, real tunnel accuracy, or IO-VNBD results
  until those measurements exist.
- Use large text, high contrast, a blue route, and a red/orange outage band.

## Five-to-ten-minute flow

### 0:00–0:45 — The human problem

**Visual:** Show a simple route entering a tunnel. The normal navigation marker
freezes or jumps after the tunnel entrance.

**Say:**

> Every day, delivery drivers, emergency responders, truck drivers, and
> two-wheeler riders depend on a phone for navigation. In a tunnel or dense
> urban area, the satellite signal can disappear. A normal navigation app may
> freeze, jump to a parallel road, or miss the next turn. The vehicle is still
> moving, but the app has lost its reference.

### 0:45–1:30 — The simple insight

**Visual:** Three large blocks:

```text
GNSS signal       Phone motion        Road structure
Where am I?       How am I moving?    Where can a vehicle be?
```

**Say:**

> The phone has another source of information. Its accelerometer and gyroscope
> can sense motion even when satellites cannot. The phone also knows that a
> vehicle moves forward on a road; it does not teleport sideways. IDR combines
> those facts instead of waiting for GNSS to return.

### 1:30–2:30 — How IDR works

**Visual:** Animate these five blocks left to right:

```text
Calibrate phone
      ↓
Understand forward motion
      ↓
Fuse GNSS + motion
      ↓
Constrain to road geometry
      ↓
Recover when GNSS returns
```

**Say:**

> First, we learn how the phone is mounted, so phone axes become vehicle axes.
> Next, we filter vibration and estimate forward motion. While GNSS is
> available, it corrects the estimate. During an outage, the motion estimate
> continues and the road geometry limits implausible drift. When GNSS returns,
> recovery is deliberate rather than an instant jump.

### 2:30–4:30 — Guided demo

Use [web-demo/index.html](../web-demo/index.html) as the guaranteed,
dependency-free presentation fallback. Use the Android app only when the APK,
device, permissions, and sensors have been checked before the presentation.

1. **Ready screen**
   - Point out the route, `READY` badge, speed, distance, and `10 Hz`.
   - Say: "This is the same visual language planned for the production mobile
     application, but this replay is deterministic and does not require a
     network map."
2. **Start replay**
   - Click `Start replay`.
   - Wait for `GNSS-AIDED`.
   - Say: "The system has a satellite reference and is correcting the motion
     estimate."
3. **Blackout state**
   - Wait until the badge reads `DEAD-RECKONING`.
   - Point to `GNSS unavailable`.
   - Say: "The satellite reference is gone. The vehicle marker keeps moving,
     confidence is visible, and the user receives a degraded-but-live state
     instead of a frozen map."
4. **Recovery**
   - Wait until the replay returns to `GNSS-AIDED`.
   - Say: "The signal is back. The fusion engine confirms recovery before
     returning to the aided state."
5. **Evidence**
   - Open [synthetic-1km-report.json](evidence/synthetic-1km-report.json)
     or [synthetic-1km-trajectory.svg](evidence/synthetic-1km-trajectory.svg).
   - Say: "This checked-in result is a deterministic contract test. It proves
     the replay and metrics pipeline, not field accuracy. Real IO-VNBD and
     device results are the next validation step."

### 4:30–6:00 — Why this is practical

**Visual:** Four audience outcomes:

```text
No OBD cable required | Phone or external IMU | Works offline by design | Visible recovery
```

**Say:**

> The first target is accessibility. The approach does not require a factory
> vehicle computer or an OBD cable. The same engine accepts phone sensors or
> an external IMU. Training can happen before deployment; the runtime is
> designed for edge execution. The interface also makes degraded operation
> visible instead of silently displaying stale data.

### 6:00–7:30 — Evidence and boundaries

**Visual:** Split screen: "Implemented now" and "Validation next".

**Implemented now:**

- Shared sensor and navigation contracts
- Calibration and vehicle-frame conversion
- GNSS/INS state machine and recovery hysteresis
- Non-holonomic and road-segment constraints
- Deterministic replay, metrics, and fail-closed evaluation
- Android capture/runtime seam and browser demo

**Validation next:**

- Permitted IO-VNBD subset and held-out model results
- Android APK and physical phone measurement
- Offline OSM extract and real road-trace comparison
- External-IMU/FOG throughput measurement

**Say:**

> We are deliberately separating a working engineering baseline from claims
> that require a dataset or physical test. The architecture is ready for those
> measurements, and the repository refuses to generate a real result when the
> required evidence is missing.

### 7:30–9:00 — Close with impact

**Say:**

> IDR is not trying to replace navigation. It fills the dangerous gap when
> navigation loses its reference. For a delivery driver, that can mean keeping
> the next turn visible. For an emergency responder, it can mean preserving
> route continuity in an underpass. For a two-wheeler or older vehicle, it
> avoids requiring specialized factory hardware.

**Closing sentence:**

> The key promise is simple: when the sky goes silent, the vehicle should not
> become invisible to its navigation system.

## Visual storyboard

### Slide 1 — The blackout

- Light map background
- Blue route entering a dark tunnel
- Marker frozen on the conventional side
- Large caption: `GNSS lost. Vehicle still moving.`

### Slide 2 — The IDR idea

- Phone icon with accelerometer and gyroscope labels
- Road line and vehicle marker
- Three words: `Sense. Constrain. Recover.`

### Slide 3 — The pipeline

- Five rounded cards matching the app palette
- No equations
- One short subtitle under each card

### Slide 4 — The live state machine

- `GNSS-AIDED` in blue
- `DEAD-RECKONING` in amber
- `RECOVERING` in violet
- `GNSS-AIDED` again in blue
- Confidence line visible throughout

### Slide 5 — Evidence boundary

- One real-looking chart only when it has provenance
- Synthetic charts labelled `DETERMINISTIC CONTRACT TEST`
- Two columns: `Measured` and `Not yet measured`

## Backup plan

If Android fails to build, permissions fail, a sensor is unavailable, or the
device behaves unpredictably:

1. Do not hide the error or claim a successful live run.
2. Open `web-demo/index.html`.
3. Run the deterministic replay and show all state transitions.
4. Open the benchmark report and explain the evidence boundary.
5. State that physical-device validation is a declared next milestone.

## Likely judge questions

### Is this just GPS?

No. GNSS is one input when available. During an outage, the engine propagates
the state from calibrated accelerometer and gyroscope motion, then uses road
constraints and later GNSS recovery.

### Where is the AI?

The repository includes speed/vibration model contracts, training-side
baselines, export schemas, and an adaptive fusion seam. The current checked-in
model is a transparent baseline, not a claimed trained IO-VNBD neural model.

### How do you know the phone orientation?

The calibration workflow first observes stationary gravity, then uses
forward-motion GNSS bearing and speed to identify the signed vehicle-forward
axis. A failed calibration remains visible.

### What happens when the map is wrong?

Map matching is gated by distance and heading. If no candidate is credible,
the engine does not force a correction; it preserves the inertial state and
reports the degraded condition.

### Is the 0% drift result real?

It is a deterministic synthetic contract-test result. It validates replay and
metric plumbing. It is not a claim about a real tunnel, phone, IO-VNBD, or
lane-level accuracy.

### Can it work with an external IMU?

The edge engine accepts a transport-neutral external-IMU frame and the rover
protocol is versioned and CRC-protected. A physical 200 Hz measurement remains
to be collected.

## Presenter checklist

- [ ] Browser demo opens before the judges arrive.
- [ ] Reset the demo to `READY`.
- [ ] Benchmark report and trajectory plot are open in separate tabs.
- [ ] Android fallback has permissions, battery, and sensor checks complete.
- [ ] No unsupported performance number appears on a slide.
- [ ] Every claim can be linked to a repository file or labelled as a plan.
- [ ] One person presents; one person operates the demo and watches the
  fallback path.
