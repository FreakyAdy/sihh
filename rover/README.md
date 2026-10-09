# Autonomous Ground Rover Testbed

The rover is a controlled physical testbed for validating the IDR pipeline.
It is not the identity of the project and does not replace road-speed or
smartphone validation.

Planned hardware:

- ESP32 motor controller with encoder, IMU, PID, and watchdog telemetry.
- Raspberry Pi bridge for logging, replay, fusion, and inference.
- Marked floor course or surveyed visual reference for ground truth.

The current repository provides the versioned telemetry contract in
[`protocol.py`](protocol.py). Firmware and hardware experiments are not
claimed until the physical platform is assembled and measured.

Skid steering introduces lateral slip, so rover results must not be presented
as proof of the phone non-holonomic assumption. MPU6050 results are low-cost
MEMS results, not FOG-grade results. LiDAR and cameras remain obstacle
perception sensors unless visual odometry is separately implemented and
evaluated.
