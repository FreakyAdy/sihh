# Live Real-Device Demonstration Runbook

## The Scenario: When a Judge Tests Real-World Practicality

During the evaluation, an ISRO or industry judge will challenge your team:
> *"Turn off your location right now on your phone. Show me a live, real demonstration in real time—not a pre-recorded trace or simulation."*

This runbook gives you **three battle-tested ways** to perform this demonstration live at your booth.

---

## 🏆 Method 1: Phone-in-Hand Streamed to Big Screen (Recommended)

This setup creates an unforgettable impression: **the judge holds the phone in their own hands**, and your laptop or booth projector displays the full Apple Maps IDR navigation dashboard updating in real time from the phone's physical sensors.

### Setup (Before the Judge Arrives):
1. Connect your laptop and phone to the same Wi-Fi (or turn on your phone's Wi-Fi hotspot and connect your laptop to it).
2. On your laptop, launch the live bridge:
   ```bash
   python scripts/live_sensor_bridge.py
   ```
   *The terminal will display your laptop's local IP address, e.g.:*
   `📱 Phone Streamer URL : http://192.168.1.42:8080/phone-streamer.html`
3. On the laptop browser, open:
   `http://localhost:8080/index.html`
   Click the **`🔴 Live Phone`** tab.
4. On the phone browser (Safari or Chrome), open the streamer URL:
   `http://192.168.1.42:8080/phone-streamer.html`
5. Tap **`🚀 Start Sensor Transmission`** and grant motion/location permissions.

### When the Judge Says: *"Turn off your location!"*
1. **Hand the phone to the judge.**
2. Show them that as they tilt and rotate the phone, the vehicle cursor on the laptop screen rotates synchronously in real time.
3. Have the judge swipe down their phone's quick settings and **turn off Location** (or tap the red **`🚨 Cut Location`** button on the phone screen).
4. **Point to the laptop screen:**
   - The Dynamic Island instantly morphs into an amber warning pill:
     `⚠️ GNSS Denied • Blackout Active`
   - The mode changes to **`DEAD-RECKONING`**.
   - Confidence gracefully begins its decay curve.
5. **Ask the judge to take 10 steps forward:**
   - The phone's accelerometer detects walking acceleration.
   - The vehicle on screen propagates smoothly along the road.
6. **Ask the judge to stop completely:**
   - Point to the telemetry HUD: **`ZUPT Clamped (0 m/s)`**.
   - Explain: *"Notice how the car doesn't drift when you stand still? Our Zero-Velocity Update (ZUPT) detects stationary acceleration variance and clamps drift accumulation to zero."*
7. **Turn Location back ON:**
   - Watch the recovery hysteresis validate consecutive fixes before smoothly restoring green **`GNSS Locked`** status.

---

## 📱 Method 2: Standalone Mobile Browser Demo (Direct on Device)

If you don't have a secondary laptop screen set up, you can run the entire interactive presentation directly in the phone's browser:

1. Open `http://<laptop-ip>:8080/index.html` directly on the phone.
2. Select **`🔴 Live Phone`**.
3. Tap the floating **`Cut GNSS`** button on the right side of the screen.
4. Move the phone to show live real-time dead reckoning.

---

## 🤖 Method 3: Android Native Application on Phone

If demonstrating the native Android Kotlin application:

1. Launch the **IDR** app on the Android phone.
2. **Indoor Venue Origin Anchor:**
   - Inside concrete exhibition halls, GPS satellites cannot penetrate the roof ($<20\text{ dB-Hz}$).
   - **Tap the "Position" label** at the top of the screen:
     This instantly anchors the venue starting coordinate origin ($P_0 = 28.6139^\circ, 77.2090^\circ$).
3. Show the judge:
   - Rotate the phone: the vehicle chevron rotates with your physical compass.
   - **Tap the "Mode" label** (or swipe down Android settings and disable Location):
     The engine immediately transitions to:
     `Mode: DEAD RECKONING (confidence 0.98)`
   - Walk forward: inertial acceleration propagates distance.

---

## 💬 What to Say to the Judge (The Verbatim Pitch)

> **Judge:** *"Why can't dead reckoning start without an initial GPS fix?"*  
> **You:**  
> *"Dead reckoning is fundamentally an incremental vector integration ($P_t = P_0 + \int v \, dt$). You cannot calculate where you are on Earth without knowing where you started. That's why in our system, nominal GNSS anchors the origin ($P_0$), and the moment satellites disappear in a tunnel, our high-rate inertial fusion carries the trajectory forward without interruption."*

> **Judge:** *"Why doesn't the position explode when the user stands still?"*  
> **You:**  
> *"Without algorithmic constraints, raw accelerometer double-integration experiences quadratic drift ($x = \frac{1}{2} a_{bias} t^2$), which causes $>50\text{ m}$ of error in just 40 seconds. We solve this with two core pillars: Non-Holonomic Constraints (NHC) that enforce zero lateral velocity, and Zero-Velocity Updates (ZUPT) that detect standstill variance and freeze velocity to exactly 0.0 m/s."*
