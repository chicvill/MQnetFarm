/*
 * MQnet Smart Farm - ESP32-WROOM Node (Test Version)
 * [보드: ESP32 Dev Module / DOIT ESP32 DEVKIT V1]
 *
 * [Arduino IDE 보드 설정]
 * - Board: "ESP32 Dev Module"
 * - Upload Speed: "921600"
 * - Flash Frequency: "80MHz"
 *
 * [공지] 이전에 사용하던 esp32를 재사용하는 경우 공장초기화가 필요합니다.
 * 1. [Erase All Flash Before Sketch Upload]의 옵션을 [Enabled]로 check.
 * 2. 전원이 켜진 ESP32 보드에 있는 BOOT 버튼을 5초 이상 길게 누름.
 */

#include <Preferences.h>
#include <WiFi.h>
#include <esp_now.h>

// --- USER SETTINGS ---
const char *ssid = "U+Net8AEC";
const char *password = "8514A#867J";
const char *mqtt_server = "192.168.0.103";
const char *GATEWAY_MAC = "FF:FF:FF:FF:FF:FF";

char nodeId[4] = "ZZZ";
float threshold_min = 10.0;
float threshold_max = 50.0;
unsigned long lastHeartbeat = 0;
Preferences prefs;

typedef struct struct_message {
  char id[4];
  char name[16];
  float value;
  char unit[8];
  bool is_alert;
} struct_message;

struct_message myData;
esp_now_peer_info_t peerInfo;

void setup() {
  Serial.begin(115200);
  prefs.begin("mqnet", false);
  if (prefs.isKey("node_id")) {
    prefs.getString("node_id", nodeId, 4);
  }

  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK)
    return;

  uint8_t broadcastAddr[6];
  sscanf(GATEWAY_MAC, "%x:%x:%x:%x:%x:%x", &broadcastAddr[0], &broadcastAddr[1],
         &broadcastAddr[2], &broadcastAddr[3], &broadcastAddr[4],
         &broadcastAddr[5]);
  memcpy(peerInfo.peer_addr, broadcastAddr, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  esp_now_add_peer(&peerInfo);

  pinMode(0, INPUT_PULLUP); // WROOM Boot Button
}

void loop() {
  if (digitalRead(0) == LOW) {
    delay(5000);
    if (digitalRead(0) == LOW) {
      prefs.putString("node_id", "ZZZ");
      ESP.restart();
    }
  }
  float sensorValue = analogRead(34);
  bool isAbnormal =
      (sensorValue < threshold_min || sensorValue > threshold_max);
  if (isAbnormal || (millis() - lastHeartbeat > 60000) ||
      strcmp(nodeId, "ZZZ") == 0) {
    strcpy(myData.id, nodeId);
    strcpy(myData.name, "WROOM-Node");
    myData.value = sensorValue;
    strcpy(myData.unit, "raw");
    myData.is_alert = isAbnormal;
    esp_now_send(peerInfo.peer_addr, (uint8_t *)&myData, sizeof(myData));
    lastHeartbeat = millis();
  }
  delay(2000);
}
