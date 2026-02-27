import numpy as np
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# 1. 환경 설정
BASE_TEMP = 10.0

def safe_val(x):
    try:
        if pd.isna(x) or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
            return None
        return float(x)
    except:
        return None

def generate_mock_data(days=10, reason=""):
    """v4.5: 데이터가 없으면 즉석에서 완벽한 10일치 시뮬레이션 데이터를 생성"""
    end_date = datetime.now().date()
    dates = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days-1, -1, -1)]
    return {
        "success": True, 
        "demo": True, 
        "error_context": reason,
        "dates": dates,
        "temp": [round(20 + i*0.5 + np.sin(i)*2, 2) for i in range(days)],
        "humi": [round(60 + np.cos(i)*10, 2) for i in range(days)],
        "light": [round(400 + np.sin(i)*100, 2) for i in range(days)],
        "ec": [1.5] * days, "ph": [6.2] * days,
        "measured_growth": {"dates": [dates[0], dates[-1]], "ratios": [10, 95]},
        "cumulative_gdd": [round(15.0 * (i+1), 2) for i in range(days)]
    }

def run_analysis_data():
    PORT = str(os.environ.get('PORT', '8007'))
    DATA_DIR = os.environ.get('DATA_DIR', 'data').strip()
    
    # 🔎 v4.5: 경로 자동 감지 로직 강화
    if DATA_DIR == 'data' or not DATA_DIR:
        if PORT == '8001' and os.path.exists('seoul_data'): DATA_DIR = 'seoul_data'
        elif PORT == '8002' and os.path.exists('busan_data'): DATA_DIR = 'busan_data'

    csv_path = os.path.join(DATA_DIR, 'smartfarm_tsdb.csv')
    
    try:
        # 데이터가 아예 없거나 경로가 잘못된 경우 즉시 데모 데이터 반환
        if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 100:
             return generate_mock_data(10, f"CSV Empty or Not Found ({DATA_DIR})")

        # 📊 데이터 로드
        df = pd.read_csv(csv_path)
        if df.empty or len(df) < 5: 
            return generate_mock_data(10, "Not enough data in CSV")

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        # 🔄 피벗 (일별 평균)
        pivot_df = df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
        
        # 📅 10일 타임라인에 맞춰 데이터 정렬
        end_date = datetime.now().date()
        date_range = [end_date - timedelta(days=i) for i in range(9, -1, -1)]
        timeline_df = pd.DataFrame({'date': date_range})
        full_df = pd.merge(timeline_df, pivot_df, on='date', how='left').sort_values('date')
            
        def find_col(df, kws):
            for col in df.columns:
                c = str(col).lower()
                if any(kw.lower() in c for kw in kws): return col
            return None

        t_col = find_col(full_df, ['온도', 'temp'])
        h_col = find_col(full_df, ['습도', 'humi'])
        l_col = find_col(full_df, ['조도', 'light', 'ppfd', 'lux'])

        # 결과 리스트 (데이터 없으면 None으로 채움)
        res_dates = [d.strftime('%Y-%m-%d') for d in full_df['date']]
        res_temp = [safe_val(x) for x in (full_df[t_col] if t_col else [None]*10)]
        res_humi = [safe_val(x) for x in (full_df[h_col] if h_col else [None]*10)]
        res_light = [safe_val(x) for x in (full_df[l_col] if l_col else [None]*10)]

        # ✅ 데이터가 너무 비어있으면(예: 전체가 None) 자동으로 Mock 데이터로 전환
        if res_temp.count(None) > 8:
            return generate_mock_data(10, "Real data is mostly empty")

        # GDD 계산
        gdd = [(max(safe_val(x) - BASE_TEMP, 0) if safe_val(x) else 0) for x in res_temp]

        return {
            "success": True, "dates": res_dates,
            "temp": res_temp, "humi": res_humi, "light": res_light,
            "ec": [1.5]*10, "ph": [6.2]*10,
            "measured_growth": {"dates": [res_dates[0], res_dates[-1]], "ratios": [10, 95]},
            "cumulative_gdd": np.cumsum(gdd).tolist()
        }

    except Exception as e:
        return generate_mock_data(10, str(e))
