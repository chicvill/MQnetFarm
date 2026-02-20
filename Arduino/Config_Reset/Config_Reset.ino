/*
 * MQnet Smart Farm - Factory Reset Utility
 * [보드: 모든 ESP32 시리즈 공통]
 *
 * [공지] 이전에 사용하던 esp32를 재사용하는 경우 공장초기화가 필요합니다. 아래
 * 2가지 중 편리한 한 가지를 필히 수행해 주세요.
 * 1. [Erase All Flash Before Sketch Upload]의 옵션을 [Enabled]로 check.
 * 2. 전원이 켜진 ESP32 보드에 있는 BOOT 버튼을 5초 이상 길게 누름.
 *
 * Purpose: Clear all stored preferences (Node ID, WiFi, Thresholds)
 */

#include <Preferences.h>

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("\n--- MQnet Factory Reset Started ---");
  Preferences prefs;
  if (prefs.begin("mqnet", false)) {
    if (prefs.clear())
      Serial.println("All settings cleared successfully.");
    else
      Serial.println("Error: Failed to clear settings.");
    prefs.end();
  }
  Serial.println("--- Reset Complete! ---");
}

void loop() {}
