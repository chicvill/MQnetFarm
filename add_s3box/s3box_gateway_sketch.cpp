/**
 * 🛰️ SmartFarm S3-BOX Gateway Sketch (Arduino/ESP-BOX SDK Reference)
 *
 * 역할을:
 * 1. Wake word "Hi Lexin" 감지 시 음성 명령 모드 진입
 * 2. 수집된 명령을 MQTT로 서버에 전송
 * 3. 서버에서 온 LCD 업데이트 데이터를 화면에 출력
 */

#include "esp_box.h" // S3 BOX 전용 SDK (예시)
#include <PubSubClient.h>

// --- AI 음성 명령 정의 ---
void on_voice_command(int command_id) {
  String msg = "";
  if (command_id == 1)
    msg = "{\"cmd\":\"device_control\", \"target\":\"cooler\", "
          "\"action\":\"ON\"}";
  else if (command_id == 2)
    msg = "{\"cmd\":\"device_control\", \"target\":\"cooler\", "
          "\"action\":\"OFF\"}";

  // MQTT 서버로 음성 인식 결과 전송
  mqttClient.publish("smartfarm/gateway/voice_cmd", msg.c_str());

  // LCD에 명령 표시
  display_text("Voice Cmd: Cooler Control");
}

// --- 서버로부터 오디오/LCD 신호 수신 ---
void callback(char *topic, byte *payload, unsigned int length) {
  JSON doc = deserialize(payload);
  String type = doc["type"];

  if (type == "alert_sound") {
    // 내장 스피커로 비프음/알림음 재생
    play_alert_sound(doc["content"]);
  } else if (type == "tts") {
    // 핵심: 서버에서 온 텍스트를 즉석에서 말로 변환 (ESP-SR 사용)
    String content = doc["text"];
    int vol = doc["volume"];
    esp_tts_speak(content, vol); // 하드웨어 TTS 엔진 호출
  } else if (type == "lcd_update") {
    // LCD 화면 갱신 (LVGL 등 사용)
    update_sensor_widgets(payload);
  }
}

void setup() {
  box_init();  // 마이크, 스피커, LCD 초기화
  wifi_init(); // 와이파이 연결
  mqtt_init(); // 브로커 연결 (HiveMQ 등)

  // 오프라인 음성 명령 사전 등록
  add_voice_command("냉각기 켜", 1);
  add_voice_command("냉각기 꺼", 2);
}

void loop() {
  mqttClient.loop();
  // 음성 엔진은 백그라운드에서 인터럽트로 작동
}
