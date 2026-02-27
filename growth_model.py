import numpy as np
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# 1. 환경 설정
BASE_TEMP = 10.0

def run_analysis_data():
    """
    v2.6: 데이터 부재 시에도 안정적으로 작동하며, 데이터 상태를 상세히 보고함
    """
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    csv_path = os.path.join(DATA_DIR, 'smartfarm_tsdb.csv')
    log_path = os.path.join(DATA_DIR, 'growth_log.json')
    
    try:
        # 1. 파일 존재 여부 및 데이터 확인
        if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 50:
             return {"success": False, "error": "센서 데이터 수집 중입니다. (CSV 파일이 비어 있음)"}

        tsdb_df = pd.read_csv(csv_path)
        if tsdb_df.empty:
            return {"success": False, "error": "기록된 센서 데이터가 없습니다."}

        tsdb_df['timestamp'] = pd.to_datetime(tsdb_df['timestamp'])
        tsdb_df['date'] = tsdb_df['timestamp'].dt.date
        
        # 2. 피벗 테이블 생성
        pivot_df = tsdb_df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
            
        def find_col(df, keywords):
            for col in df.columns:
                if any(kw.lower() in col.lower() for kw in keywords):
                    return col
            return None

        temp_col = find_col(pivot_df, ['온도', 'Temp'])
        humi_col = find_col(pivot_df, ['습도', 'Humi'])
        light_col = find_col(pivot_df, ['조도', 'Light', 'PPFD'])
        ec_col = find_col(pivot_df, ['EC'])
        ph_col = find_col(pivot_df, ['pH', 'PH'])

        # 3. 데이터가 아예 없는 경우 (샘플 모드)
        if not temp_col:
             available = [c for c in pivot_df.columns if c != 'date']
             return {"success": False, "error": f"온도 데이터가 없습니다. (감지된 장치: {available})"}

        # GDD 계산
        pivot_df['gdd'] = pivot_df[temp_col].apply(lambda x: max(float(x) - BASE_TEMP, 0))
        pivot_df['cumulative_gdd'] = pivot_df['gdd'].cumsum()

        # 4. 성장 로그 로드
        measured_growth = {"dates": [], "ratios": []}
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                growth_log = json.load(f)
                growth_df = pd.DataFrame(growth_log)
                if not growth_df.empty:
                    growth_df['date'] = pd.to_datetime(growth_df['date']).dt.date
                    merged = pd.merge(growth_df, pivot_df, on='date', how='inner')
                    measured_growth = {
                        "dates": merged['date'].astype(str).tolist(),
                        "ratios": merged['ratio'].tolist()
                    }

        # 5. 최종 리포트 데이터
        report_data = {
            "success": True,
            "dates": pivot_df['date'].astype(str).tolist(),
            "temp": pivot_df[temp_col].fillna(0).tolist(),
            "humi": pivot_df[humi_col].fillna(0).tolist() if humi_col else [],
            "light": pivot_df[light_col].fillna(0).tolist() if light_col else [],
            "ec": pivot_df[ec_col].fillna(0).tolist() if ec_col else [],
            "ph": pivot_df[ph_col].fillna(0).tolist() if ph_col else [],
            "measured_growth": measured_growth,
            "cumulative_gdd": pivot_df['cumulative_gdd'].tolist()
        }
        return report_data

    except Exception as e:
        return {"success": False, "error": f"분석 엔진 오류: {str(e)}"}
