/*
 * MQnet Smart Farm - Factory Reset Utility
 * [공지] 이전에 사용하던 esp32를 재사용하는 경우 공장초기화가 필요합니다. 아래
 * 2가지 중 편리한 한 가지를 필히 수행해 주세요.
 * 1. [Erase All Flash Before Sketch Upload]의 옵션을 [Enabled]로 check.
 * 2. 전원이 켜진 ESP32 보드에 있는 BOOT 버튼을 5초 이상 길게 누름.
 *
 * Purpose: Clear all stored preferences (Node ID, WiFi, Thresholds)
 * Compatibility: All ESP32 Series (Standard, C3, S3, S2)
 */

#include <Preferences.h>

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("\n--- MQnet Factory Reset Started ---");

  Preferences prefs;

  // "mqnet" 네임스페이스 열기 (false는 읽기/쓰기 모드)
  if (prefs.begin("mqnet", false)) {
    Serial.println("1. Namespace 'mqnet' opened.");

    // 모든 키-값 쌍 삭제
    if (prefs.clear()) {
      Serial.println("2. All settings cleared successfully.");
    } else {
      Serial.println("Error: Failed to clear settings.");
    }

    prefs.end();
    Serial.println("3. Namespace closed.");
  } else {
    Serial.println("Error: Could not open namespace.");
  }

  Serial.println("\n--- Reset Complete! ---");
  Serial.println("You can now upload the main Node/Gateway code.");
}

void loop() {
  // 아무 작업도 하지 않음 (한 번만 실행)
}
