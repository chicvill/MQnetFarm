import asyncio
import json
import csv
import os
import random
import sys
from datetime import datetime
from sf_core import ESP32C3Node, SYSTEM_REGISTRY, set_data_dir

# 🟢 Google Sheets Support
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GS_ENABLED = True
except ImportError:
    GS_ENABLED = False

# Add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 📂 데이터 폴더 설정 (환경 변수 또는 기본값)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', 'data').strip()

# 오타 방지용 보정
if DATA_DIR == 'busan-data' and not os.path.exists(os.path.join(BASE_DIR, 'busan-data')) and os.path.exists(os.path.join(BASE_DIR, 'busan_data')):
    DATA_DIR = 'busan_data'

set_data_dir(DATA_DIR)

print(f"🔧 [System] BASE_DIR: {BASE_DIR}")
print(f"📂 [System] DATA_DIR: {DATA_DIR}")

# Vision Analysis (Optional)
try:
    import vision_analysis
    print("✅ [Vision] Vision Module Loaded Successfully.")
except ImportError as e:
    print(f"⚠️ [Vision] Vision Module Load Failed: {e}")
    vision_analysis = None

# Google Sheets 전용 전역 객체
GS_CLIENT = None
GS_SHEET = None

def init_google_sheets():
    global GS_CLIENT, GS_SHEET
    if not GS_ENABLED: return None
    
    sheet_name = os.environ.get('GS_SHEET_NAME', 'SmartFarm_Data')
    
    # Render Secret Files 및 로컬 경로 탐색
    possible_paths = [
        os.environ.get('GS_CRED_PATH', ''), 
        'my_secret_key.json',           # 회피용 새 이름
        'credentials.json',
        '/etc/secrets/my_secret_key.json', # Render용 새 이름
        '/etc/secrets/credentials.json'    # Render 기본 경로
    ]
    
    cred_path = None
    for p in possible_paths:
        if p and os.path.exists(p):
            cred_path = p
            break
    
    if cred_path:
        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(cred_path, scopes=scopes)
            GS_CLIENT = gspread.authorize(creds)
            
            # 로그: 접속 시도
            try:
                # 1. 시트 열기 시도
                spreadsheet = GS_CLIENT.open(sheet_name)
                GS_SHEET = spreadsheet.get_worksheet(0)
                print(f"[Google] '{sheet_name}' 연결 성공. (Path: {cred_path})")
                
                # [NEW] 비동기로 부팅 로그 기록
                asyncio.create_task(async_update_gs([[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "SYSTEM", "BOOT", "Server Started", "OK", "0"]]))
                return True
            except gspread.exceptions.SpreadsheetNotFound:
                # 2. 못 찾았을 경우, 권한이 있는 시트 목록 출력하여 가이드
                print(f"⚠️ [Google] '{sheet_name}' 시트를 찾을 수 없습니다.")
                titles = [s.title for s in GS_CLIENT.openall()]
                if titles:
                    print(f"   ㄴ 현재 접근 가능한 시트: {titles}")
                else:
                    print(f"   ㄴ 접근 가능한 시트가 없습니다. 공유 설정을 다시 확인하세요 (Email: {creds.service_account_email})")
            except Exception as e:
                print(f"⚠️ [Google] 시트 접근 중 오류 발생: {e}")
                
        except Exception as e:
            print(f"⚠️ [Google] 시트 인증 실패: {e}")
    else:
        # print("ℹ️ [Google] credentials.json 파일이 없어 시트 연동을 건너뜁니다.")
        pass
    return False

# Google Sheets 비동기 업데이트 래퍼
async def async_update_gs(rows):
    if not GS_SHEET: return
    try:
        # gspread는 동기 방식이므로 스레드에서 실행하여 이벤트 루프 방해 금지
        await asyncio.to_thread(GS_SHEET.append_rows, rows)
        print(f"[Google] {len(rows)}건 업데이트 완료.")
    except Exception as e:
        print(f"[Google] 업데이트 에러: {e}")

# 초기화 함수 정의 (호출은 main에서 수행)

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
    file_path = f"{DATA_DIR}/smartfarm_tsdb.csv"
    
    # 파일이 없으면 헤더 생성
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "node_id", "device_id", "device_name", "value", "pin"])

    print(f"📈 [TSDB] 시계열 로깅 태스크 가동 (주기: {interval}초)")
    
    # 실시간 데이터 공유를 위한 파일 경로
    live_data_path = f"{DATA_DIR}/live_data.json"

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

            # 2. 10분(600초)마다 CSV 및 Google 시트 누적
            if not hasattr(tsdb_logger_task, '_csv_counter'):
                tsdb_logger_task._csv_counter = 0
            
            tsdb_logger_task._csv_counter += 2 # 2초 주기
            if tsdb_logger_task._csv_counter >= interval:
                tsdb_logger_task._csv_counter = 0
                
                # 월별 파일명 생성 (예: data/tsdb_2026_02.csv)
                now = datetime.now()
                monthly_file = f"{DATA_DIR}/tsdb_{now.strftime('%Y_%m')}.csv"
                
                # 파일이 없으면 헤더 생성
                if not os.path.exists(monthly_file):
                    os.makedirs(os.path.dirname(monthly_file), exist_ok=True)
                    with open(monthly_file, 'w', newline='', encoding='utf-8-sig') as f:
                        writer = csv.writer(f)
                        writer.writerow(["timestamp", "node_id", "device_id", "device_name", "value", "pin"])

                for node_id, node_data in live_status.items():
                    for s in node_data["sensors"]:
                        log_entries.append([timestamp, node_id, s['id'], s['name'], s['val'], s['pin']])
                
                if log_entries:
                    # A. 로컬 CSV 저장
                    with open(monthly_file, 'a', newline='', encoding='utf-8-sig') as f:
                        writer = csv.writer(f)
                        writer.writerows(log_entries)
                    
                    # B. Google Sheets 저장 (비동기로 실행하거나 간단히 처리)
                    if GS_SHEET:
                        try:
                            GS_SHEET.append_rows(log_entries)
                            print(f"� [Google] {len(log_entries)}건 시트 업데이트 완료.")
                        except Exception as e:
                            print(f"⚠️ [Google] 시트 쓰기 실패: {e}")
                            
                    print(f"�📊 [TSDB] {timestamp} 이력 데이터 저장 완료 ({monthly_file})")
            
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
    
    PORT = int(os.environ.get('PORT', 8000))

    class SmartFarmHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            # Health Check (Render용)
            if self.path == '/health':
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
                return

            # 루트 경로(/) 또는 /index.html 접속 시 홍보 페이지(promo.html) 즉시 서빙
            # (만약 Dashboard를 가고 싶다면 /html/index.html 또는 /dashboard.html 등을 통해 접근)
            parsed_path = urllib.parse.urlparse(self.path).path
            if parsed_path in ('/', '/index.html', '/index.htm'):
                promo_path = os.path.join(BASE_DIR, 'html', 'promo.html')
                if os.path.exists(promo_path):
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    with open(promo_path, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    self.send_error(404, f"File Not Found: {promo_path}")
                return

            # API 요청 처리
            if self.path.startswith('/api/history'):
                self.handle_history_api()
            elif self.path.startswith('/api/journal'):
                self.handle_journal_list()
            elif self.path.startswith('/api/growth'):
                self.handle_growth_list()
            elif self.path.startswith('/api/run_model'):
                self.handle_run_model()
            else:
                # 기본 정적 파일 제공
                super().do_GET()

        def translate_path(self, path):
            parsed_path = urllib.parse.urlparse(path).path
            file_name = parsed_path.lstrip('/')
            
            # 1. /data/ 요청을 실제 DATA_DIR 폴더로 매핑 (절대 경로 보정)
            if parsed_path.startswith('/data/'):
                rel_path = parsed_path[len('/data/'):].lstrip('/')
                return os.path.join(BASE_DIR, DATA_DIR, rel_path)
            
            # 2. .html 요청인 경우 /html/ 폴더 내 파일이 있는지 우선 확인
            if file_name.endswith('.html'):
                # 이미 'html/' 경로가 포함되어 있다면 중복 방지
                if file_name.startswith('html/'):
                    return os.path.join(BASE_DIR, file_name)
                
                # 포함되어 있지 않다면 'html/' 폴더 안에서 검색
                html_path = os.path.join(BASE_DIR, 'html', file_name)
                if os.path.exists(html_path):
                    return html_path
                    
            # 3. 모든 정적 파일 요청을 BASE_DIR 기준으로 변환
            return os.path.join(BASE_DIR, file_name)

        def do_POST(self):
            # API 요청 처리 (POST)
            if self.path.startswith('/api/journal'):
                self.handle_journal_post()
            elif self.path.startswith('/api/analyze_growth'):
                self.handle_growth_analysis()
            elif self.path.startswith('/api/run_model'):
                self.handle_run_model()
            else:
                self.send_error(404, "Endpoint not found")

        def handle_run_model(self):
            """
            v2.5+: 서버 부하가 큰 이미지 생성 대신, 계산된 데이터(JSON)만 클라이언트에 전달합니다.
            그래프 드로잉은 브라우저(Chart.js)가 담당합니다.
            """
            try:
                import growth_model
                # 현재 서버가 사용 중인 DATA_DIR를 환경 변수로 강제 고정
                os.environ['DATA_DIR'] = DATA_DIR
                result = growth_model.run_analysis_data()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
                
            except Exception as e:
                print(f"❌ [AI Model Error] {e}")
                # 에러 발생 시에도 브라우저가 'H' 문자를 읽지 않도록 JSON으로 응답
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e), "dates": []}).encode('utf-8'))

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
                            log_file = f"{DATA_DIR}/growth_log.json"
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
                file_path = f"{DATA_DIR}/journal.json"
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

                # 2. 데이터 수집 (CSV + Google Sheets)
                ym_prefix = target_date[:7].replace('-', '_')
                file_path = f"{DATA_DIR}/tsdb_{ym_prefix}.csv"
                result_data = {"labels": [], "temp": [], "humi": []}
                
                # A. 로컬 CSV 시도
                if os.path.exists(file_path):
                    encodings = ['utf-8-sig', 'utf-8']
                    lines = []
                    for enc in encodings:
                        try:
                            with open(file_path, 'r', encoding=enc) as f:
                                lines = f.readlines()
                            break
                        except: continue
                    if lines:
                        reader = csv.DictReader(lines)
                        for row in reader:
                            ts = row.get('timestamp', '')
                            if ts.startswith(target_date):
                                t_str = ts.split(' ')[1][:5]
                                dev = row.get('device_name', '')
                                try: val = float(row.get('value', '0'))
                                except: continue
                                if "온도" in dev or "Temp" in dev:
                                    result_data["temp"].append({"t": t_str, "y": val})
                                elif "습도" in dev or "Humi" in dev:
                                    result_data["humi"].append({"t": t_str, "y": val})

                # B. Google Sheets 보충
                if (not result_data["temp"] or not result_data["humi"]) and GS_SHEET:
                    print(f"🌐 [API] Google Sheets에서 {target_date} 복구 시도...")
                    try:
                        all_rec = GS_SHEET.get_all_records()
                        for row in all_rec:
                            ts = str(row.get('timestamp', ''))
                            if ts.startswith(target_date):
                                t_str = ts.split(' ')[1][:5]
                                dev = row.get('device_name', '')
                                try: val = float(row.get('value', '0'))
                                except: continue
                                entry = {"t": t_str, "y": val}
                                if ("온도" in dev or "Temp" in dev):
                                    if not any(x['t'] == t_str for x in result_data["temp"]):
                                        result_data["temp"].append(entry)
                                elif ("습도" in dev or "Humi" in dev):
                                    if not any(x['t'] == t_str for x in result_data["humi"]):
                                        result_data["humi"].append(entry)
                        result_data["temp"].sort(key=lambda x: x["t"])
                        result_data["humi"].sort(key=lambda x: x["t"])
                    except Exception as ge: print(f"⚠️ [API] GS Error: {ge}")

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result_data).encode('utf-8'))
            except Exception as e:
                print(f"API Error: {e}")
                self.send_error(500, str(e))
        
        def handle_journal_list(self):
            try:
                file_path = f"{DATA_DIR}/journal.json"
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
                file_path = f"{DATA_DIR}/growth_log.json"
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
    
    server_started = False
    max_tries = 10
    retry_count = 0
    
    while retry_count < max_tries:
        try:
            # socketserver.TCPServer는 블로킹이므로 스레드에서 실행
            # 파이썬 3.7+ ThreadingHTTPServer 권장되지만 호환성 위해 TCPServer 사용
            with socketserver.TCPServer(("0.0.0.0", PORT), SmartFarmHandler) as httpd:
                print(f"🌍 [{DATA_DIR}] 서버가 가동되었습니다: http://0.0.0.0:{PORT}/")
                print(f"   ㄴ API 엔드포인트: http://localhost:{PORT}/api/history")
                server_started = True
                await asyncio.to_thread(httpd.serve_forever)
                break
        except OSError as e:
            if 'PORT' in os.environ:
                # Render와 같이 환경 변수로 포트가 지정된 경우, 해당 포트가 안 되면 즉시 에러
                print(f"❌ 지정된 포트 {PORT}를 사용할 수 없습니다: {e}")
                raise
            print(f"⚠️ 포트 {PORT}가 이미 사용 중입니다. 다음 포트로 시도합니다...")
            PORT += 1
            retry_count += 1
    
    if not server_started:
        print("❌ 웹 서버를 시작할 수 없습니다.")

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
                # 1. 설정 로드
                with open(f'{DATA_DIR}/zone_config.json', 'r', encoding='utf-8') as f:
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
    # 0. Google Sheets 초기화 (이벤트 루프 시작 후 수행)
    init_google_sheets()

    # 1. 파일에서 설정 로드
    try:
        with open(f'{DATA_DIR}/config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        print(f"{DATA_DIR}/config.json 파일을 찾을 수 없어 기본 시뮬레이션을 실행합니다.")
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

    # 2. 태스크 추가 (5분=300초 간격으로 로그 기록)
    all_tasks.append(tsdb_logger_task(interval=300))
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
