/*
 * MQnet Smart Farm - ESP32-C3 Node
 * [특별 선정 보드: ESP32-C3 SuperMini]
 * - 선정 이유: 초저가, 초소형, 센서 데이터 필터링(Edge Computing) 최적화
 *
 * [Arduino IDE 보드 설정]
 * - Board: "ESP32C3 Dev Module"
 * - USB CDC On Boot: "Enabled" (시리얼 모니터 확인용)
 * - Flash Mode: "DIO"
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

void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Delivery Success"
                                                : "Delivery Fail");
}

void setup() {
  Serial.begin(115200);
  prefs.begin("mqnet", false);
  if (prefs.isKey("node_id")) {
    prefs.getString("node_id", nodeId, 4);
  }

  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK)
    return;
  esp_now_register_send_status(onDataSent);

  uint8_t broadcastAddr[6];
  sscanf(GATEWAY_MAC, "%x:%x:%x:%x:%x:%x", &broadcastAddr[0], &broadcastAddr[1],
         &broadcastAddr[2], &broadcastAddr[3], &broadcastAddr[4],
         &broadcastAddr[5]);
  memcpy(peerInfo.peer_addr, broadcastAddr, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  esp_now_add_peer(&peerInfo);

  pinMode(9, INPUT_PULLUP); // C3 SuperMini Boot Button
}

void loop() {
  if (digitalRead(9) == LOW) {
    delay(5000);
    if (digitalRead(9) == LOW) {
      prefs.putString("node_id", "ZZZ");
      ESP.restart();
    }
  }
  float sensorValue = random(15, 35);
  bool isAbnormal =
      (sensorValue < threshold_min || sensorValue > threshold_max);
  if (isAbnormal || (millis() - lastHeartbeat > 60000) ||
      strcmp(nodeId, "ZZZ") == 0) {
    strcpy(myData.id, nodeId);
    strcpy(myData.name, "C3-Node");
    myData.value = sensorValue;
    strcpy(myData.unit, "C");
    myData.is_alert = isAbnormal;
    esp_now_send(peerInfo.peer_addr, (uint8_t *)&myData, sizeof(myData));
    lastHeartbeat = millis();
  }
  delay(2000);
}
