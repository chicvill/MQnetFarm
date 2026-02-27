import numpy as np
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# 1. 환경 설정 (main_async.py와 동기화)
BASE_TEMP = 10.0

def safe_val(x):
    try:
        if pd.isna(x) or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
            return None
        return float(x)
    except:
        return None

def generate_mock_data(days=10):
    """v3.6: 어떤 상황에서도 유효한 데이터를 반환하는 최종 방어선"""
    end_date = datetime.now().date()
    dates = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days-1, -1, -1)]
    return {
        "success": True, 
        "demo": True, 
        "dates": dates,
        "temp": [22.0] * days, 
        "humi": [60.0] * days, 
        "light": [400.0] * days,
        "ec": [1.5] * days, 
        "ph": [6.5] * days,
        "measured_growth": {"dates": [dates[0]], "ratios": [10]},
        "cumulative_gdd": [12.0 * (i+1) for i in range(days)]
    }

def run_analysis_data():
    # main_async.py에서 설정된 전역 변수나 환경 변수를 따름
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    
    # 로컬 경로 보정 (seoul_data/busan_data 탐색)
    if not os.path.exists(DATA_DIR):
        for alt in ['seoul_data', 'busan_data', 'data']:
            if os.path.exists(alt):
                DATA_DIR = alt
                break

    csv_path = os.path.join(DATA_DIR, 'smartfarm_tsdb.csv')
    log_path = os.path.join(DATA_DIR, 'growth_log.json')
    
    try:
        end_date = datetime.now().date()
        date_range = [end_date - timedelta(days=i) for i in range(9, -1, -1)]
        timeline_df = pd.DataFrame({'date': date_range})
        
        # 파일이 없으면 즉시 데모 데이터 반환
        if not os.path.exists(csv_path):
             return generate_mock_data(10)

        tsdb_df = pd.read_csv(csv_path)
        if tsdb_df.empty: return generate_mock_data(10)

        # 타임스탬프 변환 및 필터링
        tsdb_df['timestamp'] = pd.to_datetime(tsdb_df['timestamp'])
        tsdb_df['date'] = tsdb_df['timestamp'].dt.date
        
        # 피벗 테이블 생성
        pivot_df = tsdb_df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
        
        # 타임라인 결합 (데이터 없는 날은 NaN)
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

        # 결과 리스트 생성
        res_dates = [d.strftime('%Y-%m-%d') for d in full_df['date']]
        res_temp = [safe_val(x) for x in full_df[t_col]] if t_col else [None]*10
        res_humi = [safe_val(x) for x in full_df[h_col]] if h_col else [None]*10
        res_light = [safe_val(x) for x in full_df[l_col]] if l_col else [None]*10
        res_ec = [safe_val(x) for x in full_df[e_col]] if e_col else [None]*10
        res_ph = [safe_val(x) for x in full_df[p_col]] if p_col else [None]*10

        # GDD 계산
        gdd = [(max(safe_val(x) - BASE_TEMP, 0) if safe_val(x) else 0) for x in res_temp]
        cum_gdd = np.cumsum(gdd).tolist()

        # 실제 측정 성장 데이터
        measured = {"dates": [], "ratios": []}
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    log = json.load(f)
                    m_df = pd.DataFrame(log)
                    if not m_df.empty:
                        m_df['date'] = pd.to_datetime(m_df['date']).dt.date
                        merged = pd.merge(m_df, timeline_df, on='date', how='inner')
                        measured = {
                            "dates": [d.strftime('%Y-%m-%d') for d in merged['date']],
                            "ratios": merged['ratio'].tolist()
                        }
            except: pass

        return {
            "success": True, 
            "dates": res_dates,
            "temp": res_temp, 
            "humi": res_humi, 
            "light": res_light,
            "ec": res_ec, 
            "ph": res_ph,
            "measured_growth": measured, 
            "cumulative_gdd": cum_gdd
        }

    except Exception as e:
        print(f"Error in analysis engine: {e}")
        return generate_mock_data(10)
