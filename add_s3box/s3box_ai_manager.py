import json

class S3BoxAIManager:
    """
    ESP32-S3 BOX의 AI 기능(음성 인식, LCD 출력, 오디오 피드백)을 
    서버 측에서 제어하고 해석하는 모듈입니다.
    """
    def __init__(self, mqtt_client):
        self.client = mqtt_client
        self.topic_audio = "smartfarm/gateway/audio_play"
        self.topic_lcd = "smartfarm/gateway/lcd_update"

    def process_voice_command(self, payload):
        """
        S3 BOX로부터 수신된 음성 명령 JSON을 해석하여 실행 가능한 명령으로 변환합니다.
        """
        cmd_type = payload.get("cmd")
        target = payload.get("target")
        action = payload.get("action")
        
        print(f"🎙️ [Voice AI] 음성 명령 인식됨: {target}를 {action} 합니다.")
        
        # 여기서 실제 MQTT 제어 토픽으로 변환하여 발송하는 로직이 추가됩니다.
        # 예: smartfarm/node1/cmd -> {"power": "ON"}
        return {"success": True, "target": target, "action": action}

    def send_voice_alert(self, message_type, farm_name):
        """
        S3 BOX 스피커로 알림음을 내보내거나 미리 정의된 메시지를 재생하도록 명령합니다.
        """
        alert_msg = {
            "type": "alert_sound",
            "content": "warning_beep",
            "priority": "high"
        }
        self.client.publish(self.topic_audio, json.dumps(alert_msg))
        print(f"🔊 [Voice AI] {farm_name} 알림음 송출 명령 발송")

    def speak_text(self, text, language="ko-KR"):
        """
        [NEW] 텍스트를 전달하여 S3 BOX의 TTS 엔진이 말하게 합니다.
        파일 저장 없이 텍스트만 전송하므로 매우 가벼운 통신이 가능합니다.
        """
        tts_msg = {
            "type": "tts",
            "text": text,
            "lang": language,
            "speed": 1.0,
            "volume": 70
        }
        self.client.publish(self.topic_audio, json.dumps(tts_msg))
        print(f"📢 [TTS Engine] 발성 명령: \"{text}\"")

    def update_lcd_status(self, seoul_data, busan_data):
        """
        S3 BOX LCD 화면에 최신 농소 데이터를 업데이트합니다.
        """
        display_data = {
            "seoul": {"t": seoul_data['temp'], "h": seoul_data['humi']},
            "busan": {"t": busan_data['temp'], "h": busan_data['humi']},
            "time": "18:30"
        }
        self.client.publish(self.topic_lcd, json.dumps(display_data))
        print(f"🖥️ [LCD] 게이트웨이 화면 데이터 갱신 완료")

# 사용 예시 (lab_server.py 등에서 활용)
if __name__ == "__main__":
    # Mock Client
    class MockClient:
        def publish(self, t, p): print(f"Publishing to {t}: {p}")
        
    ai_manager = S3BoxAIManager(MockClient())
    ai_manager.send_voice_alert("temp_high", "서울")
