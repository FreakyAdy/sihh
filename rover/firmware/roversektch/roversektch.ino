/* =========================================================================
 *  AgYaan — Autonomous Lunar Exploration Rover (Chandrayaan-3 Inspired)
 *  Master Controller Firmware for Dual-Core ESP32 Node
 *
 *  Hardware Configuration:
 *  - 4WD Skid-Steer via Dual TB6612FNG Motor Drivers
 *  - Benewake TF-LiDAR (Hardware UART2: RX2=16, TX2=17, 115200 baud)
 *  - MPU6050 6-DOF IMU (Hardware I2C: SDA=21, SCL=22, 0x68)
 *  - Quadrature Wheel Odometry (330 PPR, 6.5 cm diameter wheels)
 *    * Left: Phase A=34, Phase B=35
 *    * Right: Phase A=36, Phase B=39
 *  - Dual ESP32-CAM Haz-Cams (Port & Starboard MJPEG streams on :81/stream)
 *  - ESP-NOW Peer-to-Peer Teleoperation Receiver (Sub-5ms latency)
 *  - WebServer (WIFI_AP_STA mode) serving AgYaan Command HUD (index.h)
 * ========================================================================= */

#include <WiFi.h>
#include <WebServer.h>
#include <esp_now.h>
#include <Wire.h>
#include "index.h"

// ---------------------------------------------------------------------------
// 1. PIN DEFINITIONS
// ---------------------------------------------------------------------------

// Motor Driver 1 (Front Motors)
#define FL_PWM  32
#define FL_IN1  33
#define FL_IN2  25
#define FR_PWM  26
#define FR_IN1  27
#define FR_IN2  14

// Motor Driver 2 (Back Motors)
#define BL_PWM  13
#define BL_IN1  18
#define BL_IN2  19
#define BR_PWM  23
#define BR_IN1  5
#define BR_IN2  4

// TF-LiDAR (UART2)
#define LIDAR_RX 16
#define LIDAR_TX 17

// MPU6050 IMU (I2C)
#define I2C_SDA  21
#define I2C_SCL  22
#define MPU_ADDR 0x68

// Wheel Encoders (Interrupt Pins)
#define ENC_L_A  34
#define ENC_L_B  35
#define ENC_R_A  36
#define ENC_R_B  39

// Physical Constants
#define WHEEL_DIAMETER_CM  6.5
#define WHEEL_CIRCUM_CM    (3.14159265 * WHEEL_DIAMETER_CM)
#define ENCODER_PPR        330.0
#define WHEEL_BASE_CM      18.0

// PWM Channels (ESP32 LEDC)
#define CH_FL 0
#define CH_FR 1
#define CH_BL 2
#define CH_BR 3
#define PWM_FREQ 5000
#define PWM_RES  8

// ---------------------------------------------------------------------------
// 2. GLOBAL SYSTEM STATE & VOLATILE COUNTERS
// ---------------------------------------------------------------------------

volatile long left_encoder_ticks = 0;
volatile long right_encoder_ticks = 0;

void IRAM_ATTR isr_enc_l() {
    int b = digitalRead(ENC_L_B);
    if (b > 0) left_encoder_ticks++;
    else left_encoder_ticks--;
}

void IRAM_ATTR isr_enc_r() {
    int b = digitalRead(ENC_R_B);
    if (b > 0) right_encoder_ticks++;
    else right_encoder_ticks--;
}

// LiDAR State
HardwareSerial LidarSerial(2);
uint16_t lidar_distance_cm = 0;
uint16_t lidar_strength = 0;

// IMU State
float gyro_z_bias = 0.0;
float current_heading_deg = 0.0;
unsigned long last_imu_time_ms = 0;

// Odometry Pose
float pose_x_cm = 0.0;
float pose_y_cm = 0.0;
long prev_l_ticks = 0;
long prev_r_ticks = 0;

// Operational Modes
enum RoverMode { MODE_MANUAL, MODE_AUTONOMOUS, MODE_SCAN_BYPASS, MODE_FAILSAFE };
RoverMode current_mode = MODE_MANUAL;

// Web Server
WebServer server(80);

// ESP-NOW Joystick Remote Payload
typedef struct struct_message {
    int x;       // 0 to 4095 (Center ~2048)
    int y;       // 0 to 4095 (Center ~2048)
    bool button; // Pressed = true
} struct_message;

struct_message remoteData;
unsigned long last_remote_rx_ms = 0;

// ---------------------------------------------------------------------------
// 3. MOTOR CONTROL PRIMITIVES
// ---------------------------------------------------------------------------

void set_motor_speed(int pwm_pin, int ch, int in1, int in2, int speed) {
    if (speed > 255) speed = 255;
    if (speed < -255) speed = -255;

    if (speed > 0) {
        digitalWrite(in1, HIGH);
        digitalWrite(in2, LOW);
        ledcWrite(ch, speed);
    } else if (speed < 0) {
        digitalWrite(in1, LOW);
        digitalWrite(in2, HIGH);
        ledcWrite(ch, -speed);
    } else {
        digitalWrite(in1, LOW);
        digitalWrite(in2, LOW);
        ledcWrite(ch, 0);
    }
}

void skid_steer(int left_speed, int right_speed) {
    set_motor_speed(FL_PWM, CH_FL, FL_IN1, FL_IN2, left_speed);
    set_motor_speed(BL_PWM, CH_BL, BL_IN1, BL_IN2, left_speed);
    set_motor_speed(FR_PWM, CH_FR, FR_IN1, FR_IN2, right_speed);
    set_motor_speed(BR_PWM, CH_BR, BR_IN1, BR_IN2, right_speed);
}

void stop_motors() {
    skid_steer(0, 0);
}

// ---------------------------------------------------------------------------
// 4. TF-LIDAR PARSER (Non-Blocking Frame Protocol)
// ---------------------------------------------------------------------------

void read_tf_lidar() {
    while (LidarSerial.available() >= 9) {
        if (LidarSerial.read() == 0x59 && LidarSerial.peek() == 0x59) {
            LidarSerial.read(); // consume second 0x59
            uint8_t buf[7];
            LidarSerial.readBytes(buf, 7);
            
            uint8_t checksum = 0x59 + 0x59;
            for (int i = 0; i < 6; i++) checksum += buf[i];
            
            if (checksum == buf[6]) {
                lidar_distance_cm = buf[0] + (buf[1] << 8);
                lidar_strength = buf[2] + (buf[3] << 8);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// 5. MPU6050 IMU INTEGRATION & HEADING TRACKING
// ---------------------------------------------------------------------------

void init_mpu6050() {
    Wire.begin(I2C_SDA, I2C_SCL, 400000);
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x6B); // PWR_MGMT_1
    Wire.write(0x00); // Wake up MPU6050
    Wire.endTransmission(true);
    
    // Calibrate stationary gyro bias
    long sum = 0;
    for (int i = 0; i < 200; i++) {
        Wire.beginTransmission(MPU_ADDR);
        Wire.write(0x47); // GYRO_ZOUT_H
        Wire.endTransmission(false);
        Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)2, (uint8_t)true);
        if (Wire.available() >= 2) {
            int16_t gz = (Wire.read() << 8) | Wire.read();
            sum += gz;
        }
        delay(3);
    }
    gyro_z_bias = (float)sum / 200.0;
    last_imu_time_ms = millis();
}

void update_imu() {
    unsigned long now = millis();
    float dt = (now - last_imu_time_ms) / 1000.0;
    last_imu_time_ms = now;
    if (dt <= 0.0 || dt > 0.5) return;

    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x47);
    Wire.endTransmission(false);
    Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)2, (uint8_t)true);
    if (Wire.available() >= 2) {
        int16_t raw_gz = (Wire.read() << 8) | Wire.read();
        float gyro_z_deg_s = ((float)raw_gz - gyro_z_bias) / 131.0;
        
        // ZUPT: Clamping dead-band when parked
        if (abs(gyro_z_deg_s) < 0.25) gyro_z_deg_s = 0.0;
        
        current_heading_deg += gyro_z_deg_s * dt;
        if (current_heading_deg >= 360.0) current_heading_deg -= 360.0;
        if (current_heading_deg < 0.0) current_heading_deg += 360.0;
    }
}

// ---------------------------------------------------------------------------
// 6. WHEEL ODOMETRY & DEAD RECKONING LOCALIZATION
// ---------------------------------------------------------------------------

void update_odometry() {
    long dl_ticks = left_encoder_ticks - prev_l_ticks;
    long dr_ticks = right_encoder_ticks - prev_r_ticks;
    prev_l_ticks = left_encoder_ticks;
    prev_r_ticks = right_encoder_ticks;

    float dl_cm = (dl_ticks / ENCODER_PPR) * WHEEL_CIRCUM_CM;
    float dr_cm = (dr_ticks / ENCODER_PPR) * WHEEL_CIRCUM_CM;
    float ds_cm = (dl_cm + dr_cm) / 2.0;

    float rad = radians(current_heading_deg);
    pose_x_cm += ds_cm * sin(rad);
    pose_y_cm += ds_cm * cos(rad);
}

// ---------------------------------------------------------------------------
// 7. AUTONOMOUS SCAN-AND-BYPASS ROUTINE
// ---------------------------------------------------------------------------

void handle_autonomous_navigation() {
    // Check for obstacle collision hazard inside 30 cm
    if (lidar_distance_cm > 0 && lidar_distance_cm < 30) {
        // Halt immediately
        stop_motors();
        current_mode = MODE_SCAN_BYPASS;
        
        // 1. Sector Scan Right
        skid_steer(180, -180);
        delay(350);
        stop_motors();
        delay(100);
        read_tf_lidar();
        int right_clearance = lidar_distance_cm;

        // 2. Sector Scan Left
        skid_steer(-180, 180);
        delay(700);
        stop_motors();
        delay(100);
        read_tf_lidar();
        int left_clearance = lidar_distance_cm;

        // 3. Bypass Flank along widest clearance
        if (right_clearance > left_clearance) {
            skid_steer(180, -180);
            delay(700); // re-aim right
        }
        skid_steer(160, 160);
        delay(600); // advance past obstacle
        stop_motors();
        
        current_mode = MODE_AUTONOMOUS;
    } else {
        // Forward crawl
        skid_steer(150, 150);
    }
}

// ---------------------------------------------------------------------------
// 8. ESP-NOW JOYSTICK RECV CALLBACK
// ---------------------------------------------------------------------------

void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
    memcpy(&remoteData, incomingData, sizeof(remoteData));
    last_remote_rx_ms = millis();

    // Pushbutton switches mode between MANUAL and AUTONOMOUS
    static bool prev_btn = false;
    if (remoteData.button && !prev_btn) {
        current_mode = (current_mode == MODE_MANUAL) ? MODE_AUTONOMOUS : MODE_MANUAL;
    }
    prev_btn = remoteData.button;

    if (current_mode == MODE_MANUAL) {
        int x = remoteData.x - 2048; // -2048 to +2047
        int y = remoteData.y - 2048;

        // 1000-unit deadzone
        if (abs(x) < 500) x = 0;
        if (abs(y) < 500) y = 0;

        int throttle = map(y, -2048, 2047, -255, 255);
        int steering = map(x, -2048, 2047, -180, 180);

        int left_cmd = throttle + steering;
        int right_cmd = throttle - steering;
        skid_steer(left_cmd, right_cmd);
    }
}

// ---------------------------------------------------------------------------
// 9. WEBSERVER JSON API & PROGMEM HUD
// ---------------------------------------------------------------------------

void handle_root() {
    server.send(200, "text/html", index_html);
}

void handle_telemetry() {
    String json = "{";
    json += "\"mode\":\"" + String(current_mode == MODE_MANUAL ? "MANUAL" : (current_mode == MODE_AUTONOMOUS ? "AUTONOMOUS" : "SCAN_BYPASS")) + "\",";
    json += "\"x_cm\":" + String(pose_x_cm, 1) + ",";
    json += "\"y_cm\":" + String(pose_y_cm, 1) + ",";
    json += "\"heading_deg\":" + String(current_heading_deg, 1) + ",";
    json += "\"lidar_cm\":" + String(lidar_distance_cm) + ",";
    json += "\"lidar_str\":" + String(lidar_strength) + ",";
    json += "\"ticks_l\":" + String(left_encoder_ticks) + ",";
    json += "\"ticks_r\":" + String(right_encoder_ticks) + ",";
    json += "\"uptime_s\":" + String(millis() / 1000);
    json += "}";
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", json);
}

unsigned long last_web_cmd_ms = 0;

void handle_command() {
    if (server.hasArg("cmd")) {
        String cmd = server.arg("cmd");
        last_web_cmd_ms = millis();
        if (cmd == "forward") skid_steer(180, 180);
        else if (cmd == "reverse") skid_steer(-180, -180);
        else if (cmd == "left") skid_steer(-180, 180);
        else if (cmd == "right") skid_steer(180, -180);
        else if (cmd == "stop") stop_motors();
        else if (cmd == "auto") current_mode = MODE_AUTONOMOUS;
        else if (cmd == "manual") { current_mode = MODE_MANUAL; stop_motors(); }
    }
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", "{\"status\":\"ok\"}");
}

// ---------------------------------------------------------------------------
// 10. SETUP & MAIN LOOP
// ---------------------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    LidarSerial.begin(115200, SERIAL_8N1, LIDAR_RX, LIDAR_TX);

    // Motor GPIO Configuration
    pinMode(FL_IN1, OUTPUT); pinMode(FL_IN2, OUTPUT);
    pinMode(FR_IN1, OUTPUT); pinMode(FR_IN2, OUTPUT);
    pinMode(BL_IN1, OUTPUT); pinMode(BL_IN2, OUTPUT);
    pinMode(BR_IN1, OUTPUT); pinMode(BR_IN2, OUTPUT);

    // Motor PWM Setup (LEDC)
    ledcSetup(CH_FL, PWM_FREQ, PWM_RES); ledcAttachPin(FL_PWM, CH_FL);
    ledcSetup(CH_FR, PWM_FREQ, PWM_RES); ledcAttachPin(FR_PWM, CH_FR);
    ledcSetup(CH_BL, PWM_FREQ, PWM_RES); ledcAttachPin(BL_PWM, CH_BL);
    ledcSetup(CH_BR, PWM_FREQ, PWM_RES); ledcAttachPin(BR_PWM, CH_BR);
    stop_motors();

    // Encoder Interrupts
    pinMode(ENC_L_A, INPUT_PULLUP); pinMode(ENC_L_B, INPUT_PULLUP);
    pinMode(ENC_R_A, INPUT_PULLUP); pinMode(ENC_R_B, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(ENC_L_A), isr_enc_l, RISING);
    attachInterrupt(digitalPinToInterrupt(ENC_R_A), isr_enc_r, RISING);

    // Sensors
    init_mpu6050();

    // Networking: Dual Mode AP + Station
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP("AgYaan_Rover_AP", "isro2026");

    // Optional: Connect to external Wi-Fi / Hotspot (uncomment to connect to venue router)
    // WiFi.begin("YOUR_WIFI_SSID", "YOUR_WIFI_PASSWORD");

    // Initialize ESP-NOW
    if (esp_now_init() == ESP_OK) {
        esp_now_register_recv_cb(esp_now_recv_cb_t(OnDataRecv));
    }

    // HTTP Routes
    server.on("/", handle_root);
    server.on("/telemetry", handle_telemetry);
    server.on("/cmd", handle_command);
    server.begin();

    Serial.println("=================================================");
    Serial.println("  🚀 AgYaan Autonomous Lunar Rover Ready");
    Serial.println("  SoftAP SSID : AgYaan_Rover_AP (Pass: isro2026)");
    Serial.println("  SoftAP IP   : " + WiFi.softAPIP().toString());
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("  Station IP  : " + WiFi.localIP().toString());
    }
    Serial.println("=================================================");
}

void loop() {
    server.handleClient();
    read_tf_lidar();
    update_imu();
    update_odometry();

    // Failsafe watchdog: Stop motors if neither remote nor web command has been received in 1500ms
    if (current_mode == MODE_MANUAL && (millis() - last_remote_rx_ms > 1500) && (millis() - last_web_cmd_ms > 1500)) {
        stop_motors();
    }

    // Autonomous engine execution
    if (current_mode == MODE_AUTONOMOUS) {
        handle_autonomous_navigation();
    }
}
