import asyncio
import random
import json
from abc import ABC, abstractmethod

# 전역 노드 레지스트리
SYSTEM_REGISTRY = {}

class BaseDevice(ABC):
    def __init__(self, device_id, name, pin, io_type):
        self.device_id = device_id # 고유 ID (예: AAA001)
        self.name = name           # 사람이 읽기 위한 이름
        self.pin = pin
        self.io_type = io_type

    @abstractmethod
    def __repr__(self):
        pass

class Sensor(BaseDevice):
    def __init__(self, device_id, name, pin, io_type, t_min=None, t_max=None, target_min=None, target_max=None, msg_id_min=None, msg_id_max=None, offset=0, filter_size=5, hysteresis=0.5):
        super().__init__(device_id, name, pin, io_type)
        self.threshold_min = t_min
        self.threshold_max = t_max
        self.target_min = target_min
        self.target_max = target_max
        self.msg_id_min = msg_id_min
        self.msg_id_max = msg_id_max
        
        # 보정 및 필터링 설정
        self.offset = offset
        self.filter_size = filter_size
        self.hysteresis = hysteresis
        self.buffer = []
        
        # 현재 상태 추적 (채터링 방지용)
        self.is_alarm_min = False
        self.is_alarm_max = False
        
        self.last_value = 0

    def read_value(self):
        # 1. 원시 값 시뮬레이션 (0~100)
        raw_val = random.uniform(0, 100)
        
        # 2. 보정 적용 (Offset)
        calibrated_val = raw_val + self.offset
        
        # 3. 필터링 (Moving Average)
        self.buffer.append(calibrated_val)
        if len(self.buffer) > self.filter_size:
            self.buffer.pop(0)
            
        self.last_value = sum(self.buffer) / len(self.buffer)
        return self.last_value

    def get_alarm_status(self):
        val = self.read_value()
        
        # 히스테리시스 적용 로직
        if self.threshold_min is not None:
            if not self.is_alarm_min:
                if val < self.threshold_min:
                    self.is_alarm_min = True
            else:
                if val >= self.threshold_min + self.hysteresis:
                    self.is_alarm_min = False
                    
        if self.threshold_max is not None:
            if not self.is_alarm_max:
                if val > self.threshold_max:
                    self.is_alarm_max = True
            else:
                if val <= self.threshold_max - self.hysteresis:
                    self.is_alarm_max = False
        
        if self.is_alarm_min or self.is_alarm_max:
            return {
                "id": self.device_id,
                "pin": self.pin,
                "val": round(val, 2),
                "is_min": self.is_alarm_min,
                "is_max": self.is_alarm_max
            }
        return None

    def get_status(self):
        return {
            "id": self.device_id,
            "name": self.name,
            "val": round(self.read_value(), 2),
            "pin": self.pin,
            "type": self.io_type
        }

    def execute_automation(self, alarm):
        target_id = None
        msg_id = ""

        if alarm['is_min'] and self.target_min:
            target_id = self.target_min
            msg_id = self.msg_id_min
        elif alarm['is_max'] and self.target_max:
            target_id = self.target_max
            msg_id = self.msg_id_max

        if target_id:
            found = False
            for node in SYSTEM_REGISTRY.values():
                if target_id in node.actuators:
                    act = node.actuators[target_id]
                    result = act.set_state(f"ACTIVE (By:{self.device_id} Msg:{msg_id})")
                    print(f"🌐 [Global-Auto] {self.device_id} -> {target_id}({act.pin}): {result}")
                    found = True
                    break
            if not found:
                print(f"⚠️ [Error] 대상 장치 {target_id}를 찾을 수 없습니다.")

    def __repr__(self):
        return f"[Sensor] {self.device_id}({self.name})"

class Actuator(BaseDevice):
    def __init__(self, device_id, name, pin, io_type):
        super().__init__(device_id, name, pin, io_type)
        self.state = "OFF"

    def set_state(self, new_state):
        self.state = new_state
        return f"State -> {self.state}"

    def __repr__(self):
        return f"[Actuator] {self.device_id}({self.name}) State:{self.state}"

class ESP32C3Node:
    def __init__(self, node_id):
        self.node_id = node_id  
        self.is_provisioned = False
        self.sensors = {}
        self.actuators = {}
        SYSTEM_REGISTRY[node_id] = self

        self.hardware_pins = {
            "analog": [f"GPIO{i}(ADC)" for i in range(5)],
            "digital": [f"GPIO{i}" for i in range(5, 21)]
        }

    def provision(self, config):
        """ID 및 기기 목록 기반 초기 프로비저닝 (핀 맵 고정)"""
        # 기존 핀 맵 보존을 위해 초기화 시에만 실행 권장
        self.sensors = {}
        self.actuators = {}
        
        # 기기 등록 및 핀 할당
        for s in config.get('sensors', []):
            s_id = s['id']
            pin_list = self.hardware_pins.get(s['type'])
            if pin_list:
                pin = pin_list.pop(0)
                self.sensors[s_id] = Sensor(
                    s_id, s.get('name', 'Sensor'), pin, s['type'], 
                    s.get('min'), s.get('max'), 
                    s.get('target_min'), s.get('target_max'),
                    s.get('msg_id_min'), s.get('msg_id_max'),
                    offset=s.get('offset', 0),
                    filter_size=s.get('filter_size', 5),
                    hysteresis=s.get('hysteresis', 0.5)
                )

        for a in config.get('actuators', []):
            a_id = a['id']
            pin_list = self.hardware_pins.get(a['type'])
            if pin_list:
                pin = pin_list.pop(0)
                self.actuators[a_id] = Actuator(a_id, a.get('name', 'Actuator'), pin, a['type'])
        
        # 초기 레시피 적용
        if 'recipe' in config:
            self.update_thresholds(config['recipe'])
            
        self.is_provisioned = True

    def update_thresholds(self, recipe_str):
        """레시피(작물.단계)를 기반으로 센서 임계값을 동적으로 업데이트"""
        if not recipe_str: return
        
        try:
            with open('data/catalog_crop.json', 'r', encoding='utf-8') as f:
                all_recipes = json.load(f)
                parts = recipe_str.split('.')
                if len(parts) != 2: return
                crop, stage = parts
                recipe_data = all_recipes.get(crop, {}).get(stage, {})
                
                if not recipe_data:
                    # print(f"   [{self.node_id}] Warning: '{recipe_str}' 에 해당하는 레시피 데이터가 없습니다.")
                    return

                for s_id, sensor in self.sensors.items():
                    for key, limits in recipe_data.items():
                        if key.lower() in sensor.name.lower():
                            sensor.threshold_min = limits.get('min')
                            sensor.threshold_max = limits.get('max')
                            # print(f"   [{self.node_id}] {s_id}({sensor.name}) 임계값 갱신: {sensor.threshold_min} ~ {sensor.threshold_max}")
                            break
                return True
        except Exception as e:
            print(f"   [{self.node_id}] 임계값 업데이트 실패: {e}")
        return False

    def get_pin_map(self):
        mapping = {}
        for s in self.sensors.values():
            mapping[s.device_id] = {"name": s.name, "pin": s.pin, "type": "Sensor"}
        for a in self.actuators.values():
            mapping[a.device_id] = {"name": a.name, "pin": a.pin, "type": "Actuator"}
        return mapping

    async def run_forever(self, interval=5):
        if not self.is_provisioned: return
        print(f"[{self.node_id}] 모니터링 시작")
        try:
            while True:
                for s_id, s_obj in self.sensors.items():
                    alarm = s_obj.get_alarm_status()
                    if alarm:
                        print(f"📡 [ESP-NOW] {self.node_id} 알람: {alarm}")
                        s_obj.execute_automation(alarm)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[{self.node_id}] 오류: {e}")
