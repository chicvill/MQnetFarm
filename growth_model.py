import numpy as np
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# 1. 환경 설정
BASE_TEMP = 10.0

def safe_val(x):
    """NaN이나 무한대 값을 JSON 안전한 None(null)으로 변환"""
    try:
        if pd.isna(x) or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
            return None
        return float(x)
    except:
        return None

def generate_mock_data(days=10):
    """v3.4: 100% JSON 안전한 데모 데이터 생성"""
    end_date = datetime.now().date()
    dates = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days-1, -1, -1)]
    return {
        "success": True, "demo": True, "dates": dates,
        "temp": [22.5] * days, "humi": [60.0] * days, "light": [400.0] * days,
        "ec": [1.5] * days, "ph": [6.0] * days,
        "measured_growth": {"dates": [dates[0], dates[-1]], "ratios": [10, 90]},
        "cumulative_gdd": [12.0 * i for i in range(1, days+1)]
    }

def run_analysis_data():
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    csv_path = os.path.join(DATA_DIR, 'smartfarm_tsdb.csv')
    log_path = os.path.join(DATA_DIR, 'growth_log.json')
    
    try:
        # 1. 10일 타임라인 생성
        end_date = datetime.now().date()
        date_range = [end_date - timedelta(days=i) for i in range(9, -1, -1)]
        timeline_df = pd.DataFrame({'date': date_range})
        
        if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 100:
             return generate_mock_data(10)

        tsdb_df = pd.read_csv(csv_path)
        tsdb_df['timestamp'] = pd.to_datetime(tsdb_df['timestamp'])
        tsdb_df['date'] = tsdb_df['timestamp'].dt.date
        
        # 2. 피벗 및 병합
        pivot_df = tsdb_df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
        full_df = pd.merge(timeline_df, pivot_df, on='date', how='left').sort_values('date')
            
        def find_col(df, keywords):
            for col in df.columns:
                if any(kw.lower() in str(col).lower() for kw in keywords): return col
            return None

        t_col = find_col(full_df, ['온도', 'Temp'])
        h_col = find_col(full_df, ['습도', 'Humi'])
        l_col = find_col(full_df, ['조도', 'Light', 'PPFD'])
        e_col = find_col(full_df, ['EC'])
        p_col = find_col(full_df, ['pH', 'PH'])

        # 3. 데이터 추출 및 강력 세탁 (NaN -> None)
        res_dates = full_df['date'].astype(str).tolist()
        res_temp = [safe_val(x) for x in full_df[t_col]] if t_col else [None]*10
        res_humi = [safe_val(x) for x in full_df[h_col]] if h_col else [None]*10
        res_light = [safe_val(x) for x in full_df[l_col]] if l_col else [None]*10
        res_ec = [safe_val(x) for x in full_df[e_col]] if e_col else [None]*10
        res_ph = [safe_val(x) for x in full_df[p_col]] if p_col else [None]*10

        # GDD 계산
        gdd = [(max(safe_val(x) - BASE_TEMP, 0) if safe_val(x) else 0) for x in res_temp]
        cum_gdd = np.cumsum(gdd).tolist()

        # 4. 성장 로그
        measured = {"dates": [], "ratios": []}
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                log = json.load(f)
                m_df = pd.DataFrame(log)
                if not m_df.empty:
                    m_df['date'] = pd.to_datetime(m_df['date']).dt.date
                    merged = pd.merge(m_df, timeline_df, on='date', how='inner')
                    measured = {"dates": merged['date'].astype(str).tolist(), "ratios": merged['ratio'].tolist()}

        return {
            "success": True, "dates": res_dates,
            "temp": res_temp, "humi": res_humi, "light": res_light,
            "ec": res_ec, "ph": res_ph,
            "measured_growth": measured, "cumulative_gdd": cum_gdd
        }

    except Exception as e:
        return generate_mock_data(10)
