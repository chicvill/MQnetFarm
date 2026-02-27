import numpy as np
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# 1. 환경 설정
BASE_TEMP = 10.0

def replace_nan_with_null(obj):
    """NaN 값을 JSON 표준인 None(null)으로 변환"""
    if isinstance(obj, list):
        return [replace_nan_with_null(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: replace_nan_with_null(v) for k, v in obj.items()}
    elif isinstance(obj, float) and np.isnan(obj):
        return None
    return obj

def generate_mock_data(days=10):
    """v3.2: 지정된 일수만큼의 데모 데이터 (JSON 안전 모드)"""
    end_date = datetime.now().date()
    dates_raw = [end_date - timedelta(days=i) for i in range(days-1, -1, -1)]
    dates = [d.strftime('%Y-%m-%d') for d in dates_raw]
    
    return {
        "success": True,
        "demo": True,
        "dates": dates,
        "temp": [round(22 + np.sin(i/2)*3 + np.random.normal(0,1), 2) for i in range(days)],
        "humi": [round(60 + np.cos(i/2)*10 + np.random.normal(0,2), 2) for i in range(days)],
        "light": [round(400 + np.sin(i/3)*200, 2) for i in range(days)],
        "ec": [round(1.5 + np.random.normal(0, 0.1), 2) for i in range(days)],
        "ph": [round(6.0 + np.random.normal(0, 0.2), 2) for i in range(days)],
        "measured_growth": {
            "dates": [dates[0], dates[days//3], dates[2*days//3], dates[-1]],
            "ratios": [5, 35, 70, 95]
        },
        "cumulative_gdd": [round(max(0, (22-BASE_TEMP)) * i, 2) for i in range(1, days+1)]
    }

def run_analysis_data():
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    csv_path = os.path.join(DATA_DIR, 'smartfarm_tsdb.csv')
    log_path = os.path.join(DATA_DIR, 'growth_log.json')
    
    try:
        end_date = datetime.now().date()
        date_range = [end_date - timedelta(days=i) for i in range(9, -1, -1)]
        timeline_df = pd.DataFrame({'date': date_range})
        
        if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 100:
             return generate_mock_data(10)

        tsdb_df = pd.read_csv(csv_path)
        if tsdb_df.empty: return generate_mock_data(10)

        tsdb_df['timestamp'] = pd.to_datetime(tsdb_df['timestamp'])
        tsdb_df['date'] = tsdb_df['timestamp'].dt.date
        
        pivot_df = tsdb_df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
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

        # GDD 계산 (NaN 전처리)
        full_df['gdd'] = full_df[temp_col].apply(lambda x: max(float(x) - BASE_TEMP, 0) if pd.notnull(x) and not np.isnan(float(x)) else 0)
        full_df['cumulative_gdd'] = full_df['gdd'].cumsum()

        measured_growth = {"dates": [], "ratios": []}
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                growth_log = json.load(f)
                growth_df = pd.DataFrame(growth_log)
                if not growth_df.empty:
                    growth_df['date'] = pd.to_datetime(growth_df['date']).dt.date
                    merged = pd.merge(growth_df, timeline_df, on='date', how='inner')
                    measured_growth = {"dates": merged['date'].astype(str).tolist(), "ratios": merged['ratio'].tolist()}

        # 🎯 핵심: .replace(np.nan, None) 를 사용하여 pandas 레벨에서 NaN을 None으로 변환
        clean_df = full_df.where(pd.notnull(full_df), None)

        report_data = {
            "success": True,
            "dates": full_df['date'].astype(str).tolist(),
            "temp": clean_df[temp_col].tolist() if temp_col else [None]*10,
            "humi": clean_df[humi_col].tolist() if humi_col else [None]*10,
            "light": clean_df[light_col].tolist() if light_col else [None]*10,
            "ec": clean_df[ec_col].tolist() if ec_col else [None]*10,
            "ph": clean_df[ph_col].tolist() if ph_col else [None]*10,
            "measured_growth": measured_growth,
            "cumulative_gdd": full_df['cumulative_gdd'].tolist()
        }
        return report_data

    except Exception as e:
        return generate_mock_data(10)
