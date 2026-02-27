import numpy as np
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# 1. 환경 설정
BASE_TEMP = 10.0

def generate_mock_data(days=10):
    """v3.1: 지정된 일수만큼의 고품질 데모 데이터 생성 (타임라인 보장)"""
    end_date = datetime.now().date()
    dates_raw = [end_date - timedelta(days=i) for i in range(days-1, -1, -1)]
    dates = [d.strftime('%Y-%m-%d') for d in dates_raw]
    
    return {
        "success": True,
        "demo": True,
        "dates": dates,
        "temp": [22 + np.sin(i/2)*3 + np.random.normal(0,1) for i in range(days)],
        "humi": [60 + np.cos(i/2)*10 + np.random.normal(0,2) for i in range(days)],
        "light": [400 + np.sin(i/3)*200 for i in range(days)],
        "ec": [1.5 + np.random.normal(0, 0.1) for i in range(days)],
        "ph": [6.0 + np.random.normal(0, 0.2) for i in range(days)],
        "measured_growth": {
            "dates": [dates[0], dates[days//3], dates[2*days//3], dates[-1]],
            "ratios": [5, 35, 70, 95]
        },
        "cumulative_gdd": [max(0, (22-BASE_TEMP)) * i for i in range(1, days+1)]
    }

def run_analysis_data():
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    csv_path = os.path.join(DATA_DIR, 'smartfarm_tsdb.csv')
    log_path = os.path.join(DATA_DIR, 'growth_log.json')
    
    try:
        # 1. 기준 타임라인 생성 (오늘부터 과거 10일)
        end_date = datetime.now().date()
        date_range = [end_date - timedelta(days=i) for i in range(9, -1, -1)]
        timeline_df = pd.DataFrame({'date': date_range})
        
        # 2. 데이터 유무 확인
        if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 100:
             return generate_mock_data(10)

        tsdb_df = pd.read_csv(csv_path)
        if tsdb_df.empty: return generate_mock_data(10)

        tsdb_df['timestamp'] = pd.to_datetime(tsdb_df['timestamp'])
        tsdb_df['date'] = tsdb_df['timestamp'].dt.date
        
        # 3. 피벗 및 타임라인 병합 (Reindex)
        pivot_df = tsdb_df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
        
        # 중요: 타임라인과 합쳐서 데이터가 없는 날도 0이나 null로 행을 만듦
        full_df = pd.merge(timeline_df, pivot_df, on='date', how='left').sort_values('date')
            
        def find_col(df, keywords):
            for col in df.columns:
                if any(kw.lower() in str(col).lower() for kw in keywords): return col
            return None

        temp_col = find_col(full_df, ['온도', 'Temp'])
        humi_col = find_col(full_df, ['습도', 'Humi'])
        light_col = find_col(full_df, ['조도', 'Light', 'PPFD'])
        ec_col = find_col(full_df, ['EC'])
        ph_col = find_col(full_df, ['pH', 'PH'])

        # 온도 데이터조차 아예 한 줄도 없으면 데모 모드
        if not temp_col or full_df[temp_col].count() == 0:
            return generate_mock_data(10)

        # 4. GDD 및 누적 데이터 계산
        full_df['gdd'] = full_df[temp_col].apply(lambda x: max(float(x) - BASE_TEMP, 0) if pd.notnull(x) else 0)
        full_df['cumulative_gdd'] = full_df['gdd'].cumsum()

        # 5. 성장 데이터 매칭
        measured_growth = {"dates": [], "ratios": []}
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                growth_log = json.load(f)
                growth_df = pd.DataFrame(growth_log)
                if not growth_df.empty:
                    growth_df['date'] = pd.to_datetime(growth_df['date']).dt.date
                    # 10일 타임라인 안에 있는 기록만 골라냄
                    merged = pd.merge(growth_df, timeline_df, on='date', how='inner')
                    measured_growth = {
                        "dates": merged['date'].astype(str).tolist(),
                        "ratios": merged['ratio'].tolist()
                    }

        return {
            "success": True,
            "dates": full_df['date'].astype(str).tolist(),
            "temp": full_df[temp_col].tolist(),
            "humi": full_df[humi_col].tolist() if humi_col else [None]*10,
            "light": full_df[light_col].tolist() if light_col else [None]*10,
            "ec": full_df[ec_col].tolist() if ec_col else [None]*10,
            "ph": full_df[ph_col].tolist() if ph_col else [None]*10,
            "measured_growth": measured_growth,
            "cumulative_gdd": full_df['cumulative_gdd'].tolist()
        }

    except Exception as e:
        import traceback
        return {"success": False, "error": f"v3.1 Engine Error: {str(e)}\n{traceback.format_exc()}"}
