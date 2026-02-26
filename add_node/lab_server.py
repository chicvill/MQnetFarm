import paho.mqtt.client as mqtt
import json
import time
from node_manager import HWNodeManager

# 통신 프로토콜 설정
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC_REG = "smartfarm/request/register"
TOPIC_CONFIG = "smartfarm/config/"  # 뒤에 MAC 주소 붙음
TOPIC_ALERT = "smartfarm/+/alert"

# 노드 매니저 초기화
manager = HWNodeManager()

def on_connect(client, userdata, flags, rc):
    print(f"📡 MQTT 테스트 서버 연결됨 (Result: {rc})")
    client.subscribe([(TOPIC_REG, 0), (TOPIC_ALERT, 0)])

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        # 1. 노드 등록 요청 처리
        if msg.topic == TOPIC_REG:
            mac = payload.get("mac", "unknown")
            config = manager.register_node(mac)
            
            # 해당 노드에게만 설정값 발송
            target_topic = TOPIC_CONFIG + mac
            client.publish(target_topic, json.dumps(config))
            print(f"📤 [Config] {mac}에게 설정 발송 완료")

        # 2. 임계값 이탈 경보 처리
        elif "/alert" in msg.topic:
            node_id = msg.topic.split('/')[1]
            manager.process_incoming_data(node_id, payload)

    except Exception as e:
        print(f"❌ 메시지 처리 에러: {e}")

# 클라이언트 가동
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print(f"🚀 [Lab Server] 시작 중... (Broker: {BROKER})")
client.connect(BROKER, PORT, 60)
client.loop_forever()
