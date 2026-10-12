/*
 * FloodSense IoT Node — ESP32 + JSN-SR04T Ultrasonic Water-Level Sensor
 * ──────────────────────────────────────────────────────────────────────
 * Reference firmware for /app/firmware (not deployed in demo).
 *
 * HONESTY NOTES:
 *  - water_level_cm is the ULTRASONIC distance minus the mounting height.
 *  - rainfall_mm is left null unless a tipping-bucket rain gauge is wired.
 *    We NEVER compute "rain = water + 5" or any fake rainfall proxy.
 *  - All readings are labelled LIVE when sent from real hardware.
 *
 * Hardware:
 *  - ESP32 DevKit (any variant)
 *  - JSN-SR04T waterproof ultrasonic sensor: Trig → GPIO 5, Echo → GPIO 18
 *  - Optional: voltage divider on GPIO 34 for battery voltage
 *
 * Wiring (JSN-SR04T):
 *  VCC → 5V, GND → GND, TRIG → GPIO 5, ECHO → GPIO 18
 *  Sensor is mounted above the water surface; measures distance to water.
 *  water_level_cm = SENSOR_MOUNT_HEIGHT_CM - measured_distance_cm
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── Configuration ─────────────────────────────────────────────────────────────
const char* WIFI_SSID     = "YOUR_SSID";         // Replace before flashing
const char* WIFI_PASSWORD = "YOUR_PASSWORD";      // Replace before flashing
const char* SERVER_URL    = "http://192.168.X.X:8000/api/sensors/readings";
const char* DEVICE_ID     = "FS-HW-001";

const float  SENSOR_MOUNT_HEIGHT_CM = 200.0;  // cm from sensor face to channel floor
const int    TRIG_PIN  = 5;
const int    ECHO_PIN  = 18;
const int    BATT_PIN  = 34;   // ADC pin for battery voltage divider (optional)
const float  BATT_R1   = 100000.0; // Ohms (divider high side) – adjust to your circuit
const float  BATT_R2   = 47000.0;  // Ohms (divider low side)
const float  BATT_FULL = 4.2;  // Li-ion full voltage
const float  BATT_MIN  = 3.0;  // Li-ion cutoff voltage
const float  LAT       = 13.0132;
const float  LON       = 80.2448;
const int    POST_INTERVAL_MS = 15000;  // 15 seconds

// ── Measure distance using JSN-SR04T ─────────────────────────────────────────
float measureDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);  // 30ms timeout
  if (duration == 0) return -1.0;  // timeout / no echo
  return (duration * 0.0343) / 2.0;
}

float readBatteryPct() {
  // Optional: read ADC, compute voltage, map to percentage
  int raw = analogRead(BATT_PIN);
  float vADC = (raw / 4095.0) * 3.3;
  float vBatt = vADC * (BATT_R1 + BATT_R2) / BATT_R2;
  float pct = (vBatt - BATT_MIN) / (BATT_FULL - BATT_MIN) * 100.0;
  return constrain(pct, 0.0, 100.0);
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Serial.printf("FloodSense Node %s starting...\n", DEVICE_ID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWiFi connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\nWiFi failed – will retry each loop.");
  }
}

void loop() {
  float distCm = measureDistanceCm();
  float waterLevelCm = -1.0;

  if (distCm > 0) {
    waterLevelCm = SENSOR_MOUNT_HEIGHT_CM - distCm;
    waterLevelCm = max(0.0f, waterLevelCm);
  }

  float battPct = readBatteryPct();
  int rssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : 0;

  // Build JSON payload
  // NOTE: rainfall_mm is null – we have no rain gauge wired.
  //       DO NOT fake rainfall = water_level + constant. That is not a measurement.
  StaticJsonDocument<256> doc;
  doc["device_id"]      = DEVICE_ID;
  doc["ts"]             = ""; // filled by server from receive time if empty
  doc["water_level_cm"] = (waterLevelCm >= 0) ? waterLevelCm : 0.0;
  doc["rainfall_mm"]    = nullptr;  // null – no rain gauge
  doc["battery_pct"]    = battPct;
  doc["rssi"]           = rssi;
  doc["lat"]            = LAT;
  doc["lon"]            = LON;
  doc["data_source"]    = "LIVE";

  String body;
  serializeJson(doc, body);

  Serial.printf("[%s] dist=%.1f cm, level=%.1f cm, batt=%.0f%%, rssi=%d\n",
                DEVICE_ID, distCm, waterLevelCm, battPct, rssi);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    int code = http.POST(body);
    if (code > 0) {
      Serial.printf("  POST → %d\n", code);
    } else {
      Serial.printf("  POST error: %s\n", http.errorToString(code).c_str());
    }
    http.end();
  } else {
    WiFi.reconnect();
    Serial.println("  WiFi reconnecting...");
  }

  delay(POST_INTERVAL_MS);
}
