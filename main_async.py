import asyncio
import json
import csv
import os
import random
import sys
from datetime import datetime
from sf_core import ESP32C3Node, SYSTEM_REGISTRY

# Add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print(f"🔧 [System] Python Executable: {sys.executable}")
print(f"🔧 [System] CWD: {os.getcwd()}")

# Vision Analysis (Optional)
try:
    import vision_analysis
    print("✅ [Vision] Vision Module Loaded Successfully.")
except ImportError as e:
    print(f"⚠️ [Vision] Vision Module Load Failed: {e}")
    vision_analysis = None

def index_to_alpha(n):
    res = ""
    for _ in range(3):
        res = chr(65 + (n % 26)) + res
        n //= 26
    return res

async def tsdb_logger_task(interval=60):
    """
    주기적으로 모든 센서 데이터를 수집하여 CSV 파일에 시계열로 저장합니다.
    """
    file_path = "data/smartfarm_tsdb.csv"
    
    # 파일이 없으면 헤더 생성
    if not os.path.exists(file_path):
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "node_id", "device_id", "device_name", "value", "pin"])

    print(f"📈 [TSDB] 시계열 로깅 태스크 가동 (주기: {interval}초)")
    
    # 실시간 데이터 공유를 위한 파일 경로 (data 폴더)
    live_data_path = "data/live_data.json"

    while True:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entries = []
            live_status = {}

            for node_id, node in SYSTEM_REGISTRY.items():
                node_data = {"sensors": [], "actuators": []}
                for sensor in node.sensors.values():
                    status = sensor.get_status()
                    node_data["sensors"].append(status)
                    # CSV용 로그 데이터 (1분 마다)
                    # 여기서는 2초마다 live_data를 만들고, 60초마다 CSV를 기록하는 로직을 통합
                
                for act in node.actuators.values():
                    node_data["actuators"].append({
                        "id": act.device_id,
                        "name": act.name,
                        "state": act.state
                    })
                live_status[node_id] = node_data

            # 1. 2초마다 실시간 JSON 업데이트 (원자적 저장: 임시 파일 사용 후 이름 변경)
            with open(live_data_path + ".tmp", 'w', encoding='utf-8') as f:
                json.dump({"timestamp": timestamp, "nodes": live_status}, f, ensure_ascii=False, indent=2)
            os.replace(live_data_path + ".tmp", live_data_path)

            # 2. 60초마다 CSV 누적 (간단한 카운터 사용)
            # 여기서는 편의상 매 루프(2초)마다 live_data를 쓰지만 CSV는 interval에 따름
            # 수정: interval을 2초로 잡고, CSV 저장은 별도 카운터로 처리
            if not hasattr(tsdb_logger_task, '_csv_counter'):
                tsdb_logger_task._csv_counter = 0
            
            tsdb_logger_task._csv_counter += 2
            if tsdb_logger_task._csv_counter >= interval:
                tsdb_logger_task._csv_counter = 0
                for node_id, node_data in live_status.items():
                    for s in node_data["sensors"]:
                        log_entries.append([timestamp, node_id, s['id'], s['name'], s['val'], s['pin']])
                
                if log_entries:
                    with open(file_path, 'a', newline='', encoding='utf-8-sig') as f:
                        writer = csv.writer(f)
                        writer.writerows(log_entries)
                    print(f"📊 [TSDB] {timestamp} 이력 데이터 저장 완료.")
            
        except Exception as e:
            print(f"⚠️ [TSDB/Live Error] {e}")
        
        await asyncio.sleep(2) # 실시간성을 위해 2초 주기로 변경

async def web_server_task():
    """
    브라우저의 CORS 정책(file:// 제한)을 피하기 위해
    현재 디렉토리를 웹 서버로 호스팅합니다.
    또한 /api/history 엔드포인트를 통해 CSV 데이터를 JSON으로 제공합니다.
    """
    import http.server
    import socketserver
    import urllib.parse
    
    PORT = 8000

    class SmartFarmHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            # 루트 경로 접속 시 대시보드로 리다이렉트
            if self.path == '/':
                self.send_response(301)
                self.send_header('Location', '/html/index.html')
                self.end_headers()
                return

            # API 요청 처리
            if self.path.startswith('/api/history'):
                self.handle_history_api()
            elif self.path.startswith('/api/journal'):
                self.handle_journal_list()
            elif self.path.startswith('/api/growth'):
                self.handle_growth_list()
            else:
                # 기본 정적 파일 제공
                super().do_GET()

        def do_POST(self):
            # API 요청 처리 (POST)
            if self.path.startswith('/api/journal'):
                self.handle_journal_post()
            elif self.path.startswith('/api/analyze_growth'):
                self.handle_growth_analysis()
            else:
                self.send_error(404, "Endpoint not found")

        def handle_growth_analysis(self):
            try:
                # 1. Body 읽기 (Target Image URL)
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_json = json.loads(post_data.decode('utf-8'))
                image_url = req_json.get('url', '')
                
                if not image_url:
                    self.send_error(400, "Image URL is missing")
                    return
                
                # 2. Vision Analysis 실행
                if vision_analysis:
                    try:
                        result = vision_analysis.analyze_plant_growth(image_url)
                        
                        # [NEW] 분석 결과 파일 저장
                        if result.get('success'):
                            log_file = "data/growth_log.json"
                            logs = []
                            if os.path.exists(log_file):
                                try:
                                    with open(log_file, 'r', encoding='utf-8') as f:
                                        logs = json.load(f)
                                except: pass
                            
                            # Add log entry
                            logs.append({
                                "date": result['timestamp'],
                                "ratio": result['ratio'],
                                "pixels": result['green_pixels']
                            })
                            
                            with open(log_file, 'w', encoding='utf-8') as f:
                                json.dump(logs, f, indent=2)

                    except Exception as e:
                        result = {"error": f"Vision Engine Error: {str(e)}"}
                else:
                    result = {"error": "Vision Module Not Loaded. (Check terminal logs for import error)"}
                
                # 3. 결과 반환
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
                
            except Exception as e:
                print(f"Analysis API Error: {e}")
                self.send_error(500, str(e))

        def handle_journal_post(self):
            # ... (Existing Code) ...
            try:
                # 1. Body 읽기
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                entry = json.loads(post_data.decode('utf-8'))
                
                # 2. 파일에 저장 (prepend)
                file_path = "data/journal.json"
                journals = []
                
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        try:
                            journals = json.load(f)
                        except json.JSONDecodeError:
                            journals = []
                
                journals.insert(0, entry) # 최신순
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(journals, f, ensure_ascii=False, indent=2)
                
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
                
            except Exception as e:
                print(f"Journal Save Error: {e}")
                self.send_error(500, str(e))


        def handle_history_api(self):
            try:
                # 1. 파라미터 파싱
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                target_date = params.get('date', [None])[0] # YYYY-MM-DD
                
                if not target_date:
                    self.send_error(400, "Missing 'date' parameter")
                    return

                # 2. CSV 읽기 및 필터링
                file_path = "data/smartfarm_tsdb.csv"
                result_data = {"labels": [], "temp": [], "humi": []}
                
                if os.path.exists(file_path):
                    # Try multiple encodings
                    encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
                    lines = []
                    
                    for enc in encodings:
                        try:
                            with open(file_path, 'r', encoding=enc) as f:
                                lines = f.readlines()
                            break # Success
                        except UnicodeDecodeError:
                            continue
                            
                    if lines:
                        reader = csv.DictReader(lines)
                        print(f"📖 [History API] {target_date} 조회 요청 (Encoding: {enc})")
                        
                        count = 0
                        for row in reader:
                            # timestamp format: YYYY-MM-DD HH:MM:SS
                            ts = row.get('timestamp', '')
                            if ts.startswith(target_date):
                                count += 1
                                # 시간만 추출 (HH:MM)
                                time_str = ts.split(' ')[1][:5]
                                
                                # 데이터 분류
                                dev_name = row.get('device_name', '')
                                val_str = row.get('value', '0')
                                pin = row.get('pin', '')
                                
                                try:
                                    val = float(val_str)
                                except ValueError:
                                    continue
                                
                                # 차트용 데이터 수집
                                # AAD001(Temp) or Device Name contains '온도'
                                if "온도" in dev_name or "Temp" in dev_name:
                                    result_data["temp"].append({"t": time_str, "y": val})
                                elif "습도" in dev_name or "Humi" in dev_name:
                                    result_data["humi"].append({"t": time_str, "y": val})
                        
                        print(f"✅ [History API] {count}건의 데이터 검색됨. (Temp: {len(result_data['temp'])}, Humi: {len(result_data['humi'])})")
                    else:
                        print(f"⚠️ [History API] CSV 읽기 실패 (모든 인코딩 시도)")
                else:
                    print(f"⚠️ [History API] {file_path} 파일이 없습니다.")
                
                # 3. 시간순 정렬 및 병합 (간소화된 로직)
                # 실제 그래프를 위해서는 라벨(시간)을 통일해야 하므로, 간단히 수집된 순서대로 반환하거나
                # 프론트엔드에서 처리하도록 원본 데이터를 줌. 여기서는 간단히 반환.
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result_data).encode('utf-8'))
                
            except Exception as e:
                print(f"API Error: {e}")
                self.send_error(500, str(e))
        
        def handle_journal_list(self):
            try:
                file_path = "data/journal.json"
                journals = []
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        try:
                            journals = json.load(f)
                        except: 
                            pass
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(journals).encode('utf-8'))
            except Exception as e:
                self.send_error(500, str(e))
        
        def handle_growth_list(self):
            try:
                file_path = "data/growth_log.json"
                logs = []
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        try:
                            logs = json.load(f)
                        except: pass
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(logs).encode('utf-8'))
            except Exception as e:
                self.send_error(500, str(e))

    # 현재 디렉토리를 서빙하는 핸들러 생성
    handler = list # python 3.7+ workaround not needed for class based
    
    while PORT < 8010:
        try:
            # socketserver.TCPServer는 블로킹이므로 스레드에서 실행
            # directory=os.getcwd()는 SimpleHTTPRequestHandler의 기능이므로 커스텀 클래스에서는 super().__init__에서 처리됨
            # 하지만 다중 상속을 피하기 위해 partial 대신 직접 클래스 사용
            
            # 파이썬 3.7+ ThreadingHTTPServer 권장되지만 호환성 위해 TCPServer 사용
            with socketserver.TCPServer(("", PORT), SmartFarmHandler) as httpd:
                print(f"🌍 [WEB] 서버가 준비되었습니다: http://localhost:{PORT}/html/index.html")
                print(f"   ㄴ API 엔드포인트: http://localhost:{PORT}/api/history")
                await asyncio.to_thread(httpd.serve_forever)
                break
        except OSError:
            PORT += 1

async def dynamic_coordinator_task():
    """
    하루 4번(00, 06, 12, 18시) 날짜를 점검하여 구역별 재배 단계 및 임계값을 업데이트합니다.
    초기 실행 시 1회 즉시 동기화를 수행합니다.
    """
    CHECK_HOURS = {0, 6, 12, 18}
    print(f"📅 [Coordinator] 정기 업데이트 모드 가동 (예정 시간: {sorted(list(CHECK_HOURS))}시)")
    
    last_run_hour = -1
    last_processed_stages = {} # {node_id: last_recipe}
    first_run = True

    while True:
        try:
            now = datetime.now()
            # 정해진 시간이거나 초기 실행인 경우
            if first_run or (now.hour in CHECK_HOURS and now.hour != last_run_hour):
                # 1. 설정 로드 (data 폴더)
                with open('data/zone_config.json', 'r', encoding='utf-8') as f:
                    zones = json.load(f)
                
                for zone in zones:
                    zone_id_prefix = zone['id']
                    crop = zone.get('crop', 'none')
                    schedule = zone.get('schedule', {})
                    
                    # 2. 현재 날짜에 따른 재배 단계 결정
                    current_stage = "sowing"
                    sorted_stages = sorted(
                        [(k, datetime.strptime(v, "%Y-%m-%d")) for k, v in schedule.items()],
                        key=lambda x: x[1], reverse=True
                    )
                    for stage, date in sorted_stages:
                        if now >= date:
                            current_stage = stage
                            break
                    
                    target_recipe = f"{crop}.{current_stage}"
                    
                    # 3. 해당 구역의 노드들을 찾아 임계값 업데이트
                    for node_id, node in SYSTEM_REGISTRY.items():
                        if node_id.startswith(zone_id_prefix):
                            if last_processed_stages.get(node_id) != target_recipe:
                                success = node.update_thresholds(target_recipe)
                                if success:
                                    prefix = "🚀 [Initial]" if first_run else f"⏰ [{now.hour:02d}:00]"
                                    print(f"{prefix} {node_id} 단계 확인: {target_recipe} 임계값 적용")
                                    last_processed_stages[node_id] = target_recipe

                last_run_hour = now.hour
                first_run = False

        except Exception as e:
            print(f"⚠️ [Coordinator Error] {e}")
        
        # 1분 단위로 체크
        await asyncio.sleep(60)

async def main():
    # 1. 파일에서 설정 로드 (data 폴더)
    try:
        with open('data/config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        print("data/config.json 파일을 찾을 수 없어 기본 시뮬레이션을 실행합니다.")
        return

    all_tasks = []
    print(f"[{len(config_data)}개의 노드 설정 로드 완료...]")

    for node_cfg in config_data:
        node_id = node_cfg['id']
        node = ESP32C3Node(node_id)
        node.provision(node_cfg)
        
        # 할당된 핀 정보 출력
        print(f"   [{node_id}] Pin Map: ", end="")
        pin_info = [f"{dev_id}({info['pin']})" for dev_id, info in node.get_pin_map().items()]
        print(", ".join(pin_info))
        
        # 비동기 실행 추가
        interval = random.uniform(4, 6)
        all_tasks.append(node.run_forever(interval=interval))

    # 2. 태스크 추가
    all_tasks.append(tsdb_logger_task(interval=60))
    all_tasks.append(web_server_task())
    all_tasks.append(dynamic_coordinator_task())

    print(f"\n[실행 시작] 모든 노드와 통합 서버가 작동합니다.")
    print("------------------------------------------------------------------")

    try:
        # 모든 태스크가 종료될 때까지 무한 실행
        await asyncio.gather(*all_tasks)
    except KeyboardInterrupt:
        print("\n[정지] 사용자가 프로그램을 종료했습니다.")
    except Exception as e:
        print(f"\n[오류 발생] {e}")

if __name__ == "__main__":
    asyncio.run(main())
