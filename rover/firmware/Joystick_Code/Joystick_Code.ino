/* =========================================================================
 *  AgYaan — Handheld Remote Controller Firmware
 *  ESP32 Transmitter with Analog Joystick over Peer-to-Peer ESP-NOW
 *
 *  Pinout:
 *  - Joystick VRx -> GPIO 34 (Analog In)
 *  - Joystick VRy -> GPIO 35 (Analog In)
 *  - Joystick Pushbutton (SW) -> GPIO 4 (INPUT_PULLUP)
 *
 *  Target Rover MAC Address: 28:05:A5:2F:9E:3C
 *  Latency: < 5 ms peer-to-peer radio packet
 * ========================================================================= */

#include <esp_now.h>
#include <WiFi.h>

#define PIN_VRX 34
#define PIN_VRY 35
#define PIN_SW  4

// Target Rover MAC Address (AgYaan Node)
uint8_t roverAddress[] = {0x28, 0x05, 0xA5, 0x2F, 0x9E, 0x3C};

typedef struct struct_message {
    int x;       // 0 to 4095
    int y;       // 0 to 4095
    bool button; // Pressed = true
} struct_message;

struct_message controlPacket;
esp_now_peer_info_t peerInfo;

void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
    // Optional status LED toggle
}

void setup() {
    Serial.begin(115200);
    pinMode(PIN_SW, INPUT_PULLUP);

    WiFi.mode(WIFI_STA);

    if (esp_now_init() != ESP_OK) {
        Serial.println("[-] Error initializing ESP-NOW");
        return;
    }

    esp_now_register_send_cb(OnDataSent);

    // Register Rover peer
    memcpy(peerInfo.peer_addr, roverAddress, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("[-] Failed to add rover peer");
        return;
    }

    Serial.println("=================================================");
    Serial.println("  🎮 AgYaan Handheld Remote Online");
    Serial.println("  Broadcasting to: 28:05:A5:2F:9E:3C");
    Serial.println("=================================================");
}

void loop() {
    // Read Analog Joystick with 90-degree axis calibration
    int rawX = analogRead(PIN_VRX);
    int rawY = analogRead(PIN_VRY);
    bool swPressed = (digitalRead(PIN_SW) == LOW);

    controlPacket.x = rawX;
    controlPacket.y = rawY;
    controlPacket.button = swPressed;

    // Send packet via ESP-NOW
    esp_now_send(roverAddress, (uint8_t *)&controlPacket, sizeof(controlPacket));

    delay(20); // 50 Hz control loop
}
