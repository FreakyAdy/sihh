# AgYaan — Autonomous Lunar Exploration Rover (Chandrayaan-3 Proving Ground)

**AgYaan** is the physical hardware testbed of the **Intelligent Dead Reckoning (IDR)** platform.
Inspired by ISRO’s *Pragyan* rover (Chandrayaan-3), AgYaan is engineered to explore the ultimate extreme GNSS-denied environment: **the lunar surface, where zero satellite positioning constellations exist**.

Every centimeter traversed on the Moon is 100% Dead Reckoning. AgYaan demonstrates our embedded sensor fusion core directly on physical hardware, while our terrestrial mobile application adapts the exact same mathematical core to civilian vehicles navigating tunnels and GPS-jammed road networks.

---

## 1. Chassis & Additive Manufacturing
- **100% Custom CAD Design:** Engineered over **90+ hours of precision additive manufacturing (3D printing)**.
- **Internal Cellular Infill:** Specialized infill pattern designed for structural shock dampening, thermal isolation, and rigid optical baseline stability.
- **Drive Train:** 4-Wheel Drive (4WD) Skid-Steer configuration driven by dual TB6612FNG dual H-bridge motor drivers.

---

## 2. Active Hardware Pin Mappings (ESP32 Master Node)

### Dual TB6612FNG Motor Drivers
| Motor Channel | PWM Pin | IN1 Pin | IN2 Pin | Function |
| :--- | :--- | :--- | :--- | :--- |
| **Front Left (FL)** | `GPIO 32` | `GPIO 33` | `GPIO 25` | Left Drive Rail |
| **Front Right (FR)** | `GPIO 26` | `GPIO 27` | `GPIO 14` | Right Drive Rail |
| **Back Left (BL)** | `GPIO 13` | `GPIO 18` | `GPIO 19` | Left Drive Rail |
| **Back Right (BR)** | `GPIO 23` | `GPIO 5` | `GPIO 4` | Right Drive Rail |

### Sensors & Perception
| Sensor Subsystem | Hardware Interface | Pins | Description |
| :--- | :--- | :--- | :--- |
| **Benewake TF-LiDAR** | Hardware UART2 | `RX2 -> GPIO 16`<br>`TX2 -> GPIO 17` | 115200 baud, non-blocking frame parsing, 30 cm hazard limit |
| **MPU6050 6-DOF IMU** | Hardware I2C | `SDA -> GPIO 21`<br>`SCL -> GPIO 22` | I2C Addr `0x68`, continuous gyro-$Z$ heading integration & ZUPT deadband |
| **Left Wheel Encoders** | GPIO Interrupts | `Phase A -> GPIO 34`<br>`Phase B -> GPIO 35` | 330 PPR quadrature ticks, $6.5\text{ cm}$ diameter wheel |
| **Right Wheel Encoders** | GPIO Interrupts | `Phase A -> GPIO 36`<br>`Phase B -> GPIO 39` | 330 PPR quadrature ticks, $6.5\text{ cm}$ diameter wheel |
| **Port Haz-Cam** | Wi-Fi Stream | `192.168.204.228:81/stream` | QVGA double-buffered, low-latency forward hazard imaging |
| **Starboard Haz-Cam** | Wi-Fi Stream | `192.168.204.192:81/stream` | $120\text{ mm}$ optical baseline stereoscopic pair |

### Handheld Remote Controller (ESP-NOW)
- Dedicated transmitter ESP32 broadcasting to Rover MAC address `28:05:A5:2F:9E:3C` (<5 ms latency).
- Analog Joystick: `VRx -> GPIO 34`, `VRy -> GPIO 35`, `SW -> GPIO 4`.
- Pushbutton toggles between `MANUAL` teleoperation and `AUTONOMOUS` mode.

---

## 3. Firmware & Web Control Structure

```text
rover/
├── README.md                           # Hardware specifications, pinout table, and pitch narrative
├── protocol.py                         # Versioned RoverTelemetry contract with CRC-32 verification
├── firmware/
│   ├── roversektch/
│   │   ├── roversektch.ino             # Main ESP32 kinematics, LiDAR UART, IMU I2C, WebServer, and ESP-NOW
│   │   └── index.h                     # AgYaan Command HUD with PROGMEM embedded 3D Isometric Canvas
│   └── Joystick_Code/
│       └── Joystick_Code.ino           # ESP32 handheld joystick remote (ESP-NOW Tx)
└── web/
    ├── agyaan_hud.html                 # Mission Control Web HUD with 3D Canvas, Dual Haz-Cams, and Domain Switcher
    ├── agyaan_hud.css                  # Mission control sci-fi theme
    └── agyaan_hud.js                   # 3D isometric renderer, kinematics engine, and telemetry loop
```

---

## 4. Live Running & Demo Modes
Launch the centralized bridge server from the repository root:
```powershell
python scripts/live_sensor_bridge.py --port 8080
```
- **AgYaan Mission Control HUD (Default):** Open [http://localhost:8080/](http://localhost:8080/)
- **Earth Vehicle Nav (PS 26168):** Open [http://localhost:8080/index.html](http://localhost:8080/index.html)
- **1-Tap Android APK Download:** Open [http://localhost:8080/idr-navigation.apk](http://localhost:8080/idr-navigation.apk)
