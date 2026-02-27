import numpy as np
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# 1. 환경 설정
BASE_TEMP = 10.0

def generate_mock_data(days=10):
    """v3.0: 지정된 일수만큼의 고품질 데모 데이터 생성"""
    dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days-1, -1, -1)]
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
            "ratios": [5, 30, 65, 95]
        },
        "cumulative_gdd": [max(0, (22-BASE_TEMP)) * i for i in range(1, days+1)]
    }

def run_analysis_data():
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    csv_path = os.path.join(DATA_DIR, 'smartfarm_tsdb.csv')
    log_path = os.path.join(DATA_DIR, 'growth_log.json')
    
    try:
        # 데이터가 없으면 10일치 데모 반환
        if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 100:
             return generate_mock_data(10)

        tsdb_df = pd.read_csv(csv_path)
        if tsdb_df.empty: return generate_mock_data(10)

        tsdb_df['timestamp'] = pd.to_datetime(tsdb_df['timestamp'])
        tsdb_df['date'] = tsdb_df['timestamp'].dt.date
        
        # 날짜별 평균 (Pivot)
        pivot_df = tsdb_df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
        pivot_df = pivot_df.sort_values('date') # 날짜 정렬 보장
            
        def find_col(df, keywords):
            for col in df.columns:
                if any(kw.lower() in col.lower() for kw in keywords): return col
            return None

        temp_col = find_col(pivot_df, ['온도', 'Temp'])
        humi_col = find_col(pivot_df, ['습도', 'Humi'])
        light_col = find_col(pivot_df, ['조도', 'Light', 'PPFD'])
        ec_col = find_col(pivot_df, ['EC'])
        ph_col = find_col(pivot_df, ['pH', 'PH'])

        if not temp_col: return generate_mock_data(10)

        # GDD 계산
        pivot_df['gdd'] = pivot_df[temp_col].apply(lambda x: max(float(x) - BASE_TEMP, 0))
        pivot_df['cumulative_gdd'] = pivot_df['gdd'].cumsum()

        # 최근 10일치로 필터링 (데이터가 더 많을 수도 있으므로)
        pivot_df = pivot_df.tail(10)

        measured_growth = {"dates": [], "ratios": []}
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                growth_log = json.load(f)
                growth_df = pd.DataFrame(growth_log)
                if not growth_df.empty:
                    growth_df['date'] = pd.to_datetime(growth_df['date']).dt.date
                    merged = pd.merge(growth_df, pivot_df, on='date', how='inner')
                    measured_growth = {"dates": merged['date'].astype(str).tolist(), "ratios": merged['ratio'].tolist()}

        return {
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

    except Exception as e:
        return generate_mock_data(10) # 오류 시에도 10일 데모
