/*
 * MQnet Smart Farm - ESP32-S3 Gateway
 * [특별 선정 보드: ESP32-S3 N16R8]
 * - 선정 이유: 듀얼 코어의 멀티태스킹, 8MB PSRAM의 대용량 데이터 버퍼링 최적화
 *
 * [공지] 이전에 사용하던 esp32를 재사용하는 경우 공장초기화가 필요합니다.
 * 1. [Erase All Flash Before Sketch Upload]의 옵션을 [Enabled]로 check.
 * 2. 전원이 켜진 ESP32 보드에 있는 BOOT 버튼을 5초 이상 길게 누름.
 *
 * [ESP32-S3 전용 설정 (IDE Tools 메뉴)]
 * - Board: "ESP32S3 Dev Module"
 * - USB CDC On Boot: "Enabled" (필수: 시리얼 모니터 확인용)
 *   주의사항 : serial monitor가 켜진 상태에서는 외부와의 연결이 차단됩니다.
 * 확인 후 꼭 닫아 주세요.
 * - Flash Size: "16MB" (N16R8 모델 기준)
 * - PSRAM: "OPI PSRAM" (N16R8 모델 기준 필수)
 * - Partition Scheme: "16M Flash (3M APP/9.9M FATFS)"
 */

#include <PubSubClient.h>
#include <WiFi.h>
#include <esp_now.h>

// --- USER SETTINGS ---
const char *ssid = "U+Net8AEC";
const char *password = "8514A#867J";
const char *mqtt_server = "192.168.0.103";
const char *mqtt_topic_prefix = "mqnet/smartfarm";

typedef struct struct_message {
  char id[4];
  char name[16];
  float value;
  char unit[8];
  bool is_alert;
} struct_message;

struct_message incomingData;
WiFiClient espClient;
PubSubClient client(espClient);

void onDataRecv(const uint8_t *mac, const uint8_t *incomingDataRaw, int len) {
  memcpy(&incomingData, incomingDataRaw, sizeof(incomingData));
  if (client.connected()) {
    char topic[64], payload[128];
    if (strcmp(incomingData.id, "ZZZ") == 0) {
      sprintf(topic, "%s/new_device", mqtt_topic_prefix);
      sprintf(payload, "{\"mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\"}", mac[0],
              mac[1], mac[2], mac[3], mac[4], mac[5]);
    } else {
      sprintf(topic, "%s/sensor/%s", mqtt_topic_prefix, incomingData.id);
      sprintf(
          payload,
          "{\"value\":%.2f, \"name\":\"%s\", \"unit\":\"%s\", \"alert\":%s}",
          incomingData.value, incomingData.name, incomingData.unit,
          incomingData.is_alert ? "true" : "false");
    }
    client.publish(topic, payload);
  }
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(115200, SERIAL_8N1, 18, 17); // For EW11

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected");

  client.setServer(mqtt_server, 1883);
  if (esp_now_init() != ESP_OK)
    return;
  esp_now_register_recv_cb(onDataRecv);
}

void reconnect() {
  while (!client.connected()) {
    if (client.connect("MQnet_Gateway_S3")) {
      Serial.println("MQTT Connected");
    } else {
      delay(5000);
    }
  }
}

void loop() {
  if (!client.connected())
    reconnect();
  client.loop();
  if (Serial1.available()) {
    String ewData = Serial1.readStringUntil('\n');
    client.publish("mqnet/smartfarm/ew11", ewData.c_str());
  }
}
