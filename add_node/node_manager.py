import json
import os
from datetime import datetime

class HWNodeManager:
    """
    하드웨어 노드의 등록, 설정 및 데이터 처리를 담당하는 통합 모듈입니다.
    main_async.py에 통합하기 쉬운 클래스 구조로 설계되었습니다.
    """
    def __init__(self, registry_file='add_node/hw_registry.json'):
        self.registry_file = registry_file
        self.nodes = self._load_registry()

    def _load_registry(self):
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {
            "SAMPLE_MAC_123": {
                "node_id": "Seoul_Node_01",
                "target_zone": "A_Zone",
                "thresholds": {"temp_min": 18.0, "temp_max": 28.0, "humi_min": 40.0}
            }
        }

    def _save_registry(self):
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(self.nodes, f, indent=2, ensure_ascii=False)

    def register_node(self, mac_address):
        """
        노드가 처음 접속했을 때 호출됩니다. 
        알려진 MAC이면 설정을 반환하고, 처음 보면 대기 목록에 넣습니다.
        """
        if mac_address in self.nodes:
            config = self.nodes[mac_address]
            print(f"✅ [Registry] 기존 노드 활성화: {mac_address} ({config['node_id']})")
            return config
        else:
            # 새로운 노드 발견 시 기본 설정으로 자동 등록 (또는 관리자 승인 대기)
            new_id = f"NEW_NODE_{len(self.nodes) + 1}"
            self.nodes[mac_address] = {
                "node_id": new_id,
                "target_zone": "Pending",
                "thresholds": {"temp_min": 20.0, "temp_max": 25.0},
                "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_registry()
            print(f"🆕 [Registry] 새 노드 임시 등록: {mac_address} -> {new_id}")
            return self.nodes[mac_address]

    def process_incoming_data(self, node_id, payload):
        """
        노드에서 온 경보(Alert) 또는 데이터를 처리합니다.
        추후 DB 저장이나 시각화 로직이 여기에 추가됩니다.
        """
        print(f"🚨 [Event] {node_id}에서 경보 수신: {payload}")
        # 여기에 구글 시트 기록이나 메인 시스템 데이터 업데이트 로직 연동 가능
        return True

# 테스트를 위한 직접 실행 로직
if __name__ == "__main__":
    manager = HWNodeManager()
    # 테스트 1: 기존 노드
    print(manager.register_node("SAMPLE_MAC_123"))
    # 테스트 2: 새로운 노드
    print(manager.register_node("MAC_ABC_456"))
