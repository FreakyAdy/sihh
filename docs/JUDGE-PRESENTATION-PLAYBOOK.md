# AgYaan & IDR — Hackathon Judge Presentation & Defense Playbook

> **Core Strategic Posture:**
> **Hardware Flex on the Table** (AgYaan 4WD Autonomous Lunar Rover) + **Mathematical Rigor on Screen** (IDR ISRO PS 26168 Engine & 2.42% Drift Benchmark).

---

## 1. The 60-Second Hook (Opening Words When Judges Arrive)

*(Hold the handheld joystick remote in hand. The AgYaan rover is resting on the table facing forward. The laptop screen is open to `http://localhost:8080/`, displaying the AgYaan 3D Isometric Lunar Hazard HUD.)*

> **Speaker 1 (Confident, engaging):**  
> "Honorable Judges, welcome to **Intelligent Dead Reckoning**.  
> The core question behind our project is: **How does an autonomous system navigate when satellite signals are completely zero?**
>
> On the lunar surface, there is **zero GNSS infrastructure by definition**—no GPS, no GLONASS, no NavIC. Every single centimeter traveled by ISRO’s *Pragyan* or our rover is **100% Dead Reckoning**.  
>
> To test our dead-reckoning fusion algorithms in the harshest zero-GNSS proving ground in the solar system, our team designed and built **AgYaan**—a custom 3D-printed 4WD autonomous lunar exploration rover.  
>
> And to solve **ISRO Problem Statement 26168 on Earth**, we ported this exact same dead-reckoning fusion engine into civilian automotive systems for 1 km highway tunnels and electronic warfare zones."

---

## 2. The 2-Minute Hardware Flex (AgYaan Rover Demonstration)

*(Gently move the joystick forward. The rover rolls smoothly forward on the table or floor. The 3D isometric trail on screen immediately tracks forward.)*

> **Speaker 2 (Technical lead):**  
> "Look at our Mission Control screen in real time:  
> 1. **Wheel Odometry:** Our dual optical encoders generate 330 pulses per revolution across $6.5\text{ cm}$ wheels, calculating incremental displacement $(\Delta X, \Delta Y)$.  
> 2. **Inertial Heading:** Our MPU6050 6-DOF IMU continuously integrates gyro-$Z$ yaw rate with stationary bias suppression.  
> 3. **LiDAR Raycasting:** Our Benewake TF-LiDAR scans 100 times per second over UART2. Watch the amber raycast cone on screen."

*(Place a hand or a water bottle 20 cm in front of the rover. The HUD flashes red: `TERRAIN HAZARD DETECTED < 30 cm` and a 3D red hazard pillar pops up on the canvas.)*

> **Speaker 1:**  
> "When a boulder or terrain crater appears within $30\text{ cm}$, AgYaan executes our **Autonomous Scan-and-Bypass algorithm**:  
> It halts, scans right, scans left, identifies the widest clearance flank, pivots, bypasses the obstacle, and re-aims toward its target waypoint—all computed on embedded ESP32 dual-core silicon without needing external cloud compute."

---

## 3. The Seamless Pivot to Problem Statement 26168 (The "Secret Weapon")

*(Click the top-bar button on screen: **`🌍 Earth Vehicle Nav (PS 26168)`**. The screen immediately transitions to the Apple Maps dark-mode vehicle navigation dashboard showing the Atal Tunnel route.)*

> **Speaker 1 (Smooth transition):**  
> "Now, some might ask: *'How does this extraterrestrial research solve our hackathon’s terrestrial road navigation problem?'*  
>
> **The answer is: The mathematical fusion core is identical.**  
> On Earth, GPS dropouts in 1 km highway tunnels, deep urban canyons, and military GPS-jammed zones cause catastrophic navigation loss.  
>
> We took the exact same four fusion pillars:
> 1. **Non-Holonomic Constraints (NHC):** Enforcing $v_{\text{lateral}} = 0$ on vehicle wheels.
> 2. **Zero Velocity Updates (ZUPT):** Clamping drift to $0.0\text{ m/s}$ during tunnel traffic jams.
> 3. **OpenStreetMap HMM Map Matching:** Bayesian segment alignment onto drivable roads.
> 4. **IO-VNBD Ridge ML Speed Correction:** Machine learning speed inference from IMU specific force."

*(Click **Start Navigation** on the Earth demo. The car travels smoothly into the 600m tunnel. Point to the HUD gauges.)*

> **Speaker 2:**  
> "Notice the naïve unconstrained accelerometer drift (red ghost car) veers off into the tunnel wall within 15 seconds.  
> But our **IDR fusion engine (cyan vehicle)** tracks the tunnel centerline with **only 2.42% drift over 1 km**—safely exceeding the SIH 10% maximum drift requirement.  
> On the real-world **IO-VNBD automotive dataset**, our model achieved a remarkable **0.20% median drift**."

*(Hold up your Android smartphone with the installed `IDR Navigation` app.)*

> **Speaker 1:**  
> "And this is not just a simulator. We compiled our native Android engine into `idr-navigation.apk`, installed here on this phone. We can turn off GPS location right now, walk across this room, and show you live physical dead reckoning in your hands."

---

## 4. The Judge Objection & Defense Matrix (How to Win Any Technical Grilling)

### Q1: "Why did you build a lunar rover when the Problem Statement asks for urban road navigation?"
> **Winning Answer:**  
> "Because the lunar surface is the purest, most uncompromising proving ground for dead reckoning. In urban navigation, teams often rely on intermittent GPS fixes to hide algorithmic drift. On the Moon, GPS does not exist—so every flaw in odometry, every gyro bias, is exposed immediately. Proving our fusion engine on physical rover hardware demonstrates that our core math is robust enough to survive when there is zero satellite signal, which makes solving 1 km terrestrial tunnels a natural subset of our system."

### Q2: "Isn't skid-steering different from car steering kinematics?"
> **Winning Answer:**  
> "Yes, absolutely! Skid-steering introduces lateral wheel scrub during turns, which violates the strict non-holonomic assumption ($v_y = 0$). That is precisely why our architecture is modular: on the rover, our EKF uses differential wheel slip compensation; on terrestrial road vehicles, our engine enforces strict Non-Holonomic Constraints ($v_y = 0$) aligned with the vehicle body frame. Both configurations share our platform-neutral `idr_engine` fusion core."

### Q3: "What happened to the Raspberry Pi on the rover?"
> **Winning Answer:**  
> "Our original architecture featured a Raspberry Pi 4 running OpenCV StereoSGBM for 3D point cloud generation. During pre-deployment stress testing, a power surge compromised the SBC. Rather than giving up, our team demonstrated engineering survivability: we ported the entire kinematics, LiDAR UART parsing, MPU6050 I2C integration, and ESP-NOW teleoperation directly onto a distributed ESP32 network within 48 hours. The physical rover on this table proves that our system can operate on low-power embedded microcontrollers."

### Q4: "How do you prevent IMU drift when the vehicle is stopped in traffic?"
> **Winning Answer:**  
> "Through our **Zero Velocity Update (ZUPT)** algorithm. When accelerometer variance falls below $0.05\text{ m/s}^2$ and gyro rate is below $0.02\text{ rad/s}$ for $>0.5\text{ s}$, the engine detects standstill and freezes velocity to exactly $0.0\text{ m/s}$. This stops the quadratic position error ($x = \frac{1}{2} a t^2$) from blowing up when idling in a tunnel traffic jam."

### Q5: "Can you prove your model wasn't overfitted?"
> **Winning Answer:**  
> "Yes! In `tests/test_ml_baseline.py` and `scripts/generate_iovnbd_evidence.py`, our IO-VNBD dataset is partitioned strictly by **complete driving sessions**, not random time slices. Zero frames from test sessions ever appear in the training split. Our Ridge regression model uses $L_2$ regularization ($\alpha = 100.0$) and achieved 0.20% drift across 60-second tunnel outages on unseen real-world road data."

---

## 5. Live Demo Checklist Before the Judges Approach

- [ ] Laptop connected to Wi-Fi / Hotspot.
- [ ] Server running: `python -u scripts/live_sensor_bridge.py --port 8080`.
- [ ] Browser open to `http://localhost:8080/` (AgYaan 3D Rover HUD active).
- [ ] Rover battery powered on (or USB connected if on desk).
- [ ] Handheld ESP-NOW remote powered on.
- [ ] Android phone with `IDR Navigation` app running and ready to show.
- [ ] Top-bar **`Earth Vehicle Nav`** button tested and working with 1 click.
