import numpy as np
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# 1. 환경 설정
BASE_TEMP = 10.0

def safe_val(x):
    """NaN/Inf를 JSON 안전한 None으로 변환"""
    try:
        if pd.isna(x) or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
            return None
        return float(x)
    except:
        return None

def generate_mock_data(days=10, reason=""):
    """v4.0: 실패 시에도 무조건 웅장한 10일 그래프를 보여주는 최후의 보루"""
    print(f"📡 [AI Mode] Generating mock data (Reason: {reason})")
    end_date = datetime.now().date()
    dates = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days-1, -1, -1)]
    return {
        "success": True, 
        "demo": True, 
        "error_context": reason,
        "dates": dates,
        "temp": [round(22 + np.sin(i/2)*3, 2) for i in range(days)],
        "humi": [round(60 + np.cos(i/2)*10, 2) for i in range(days)],
        "light": [round(400 + np.sin(i/3)*200, 2) for i in range(days)],
        "ec": [1.5] * days, "ph": [6.5] * days,
        "measured_growth": {"dates": [dates[0], dates[-1]], "ratios": [5, 95]},
        "cumulative_gdd": [round(12.0 * (i+1), 2) for i in range(days)]
    }

def run_analysis_data():
    # 🔎 v4.4: 포트(8001/8002) 기반 자동 데이터 경로 매칭
    PORT = str(os.environ.get('PORT', '8007'))
    DATA_DIR = os.environ.get('DATA_DIR', 'data').strip()
    
    # 8001이면 seoul_data, 8002이면 busan_data 우선 탐색
    if DATA_DIR == 'data' or not DATA_DIR:
        if PORT == '8001' and os.path.exists('seoul_data'): DATA_DIR = 'seoul_data'
        elif PORT == '8002' and os.path.exists('busan_data'): DATA_DIR = 'busan_data'

    # 최종 디렉토리 유효성 확인
    if not os.path.exists(DATA_DIR):
        for alt in ['seoul_data', 'busan_data', 'data']:
            if os.path.exists(alt):
                DATA_DIR = alt
                break

    csv_path = os.path.join(DATA_DIR, 'smartfarm_tsdb.csv')
    log_path = os.path.join(DATA_DIR, 'growth_log.json')
    
    try:
        # 📅 10일 타임라인 생성
        end_date = datetime.now().date()
        date_range = [end_date - timedelta(days=i) for i in range(9, -1, -1)]
        timeline_df = pd.DataFrame({'date': date_range})
        
        if not os.path.exists(csv_path):
             return generate_mock_data(10, f"CSV Not Found at {csv_path}")

        # 📊 데이터 로드 및 전처리
        df = pd.read_csv(csv_path)
        if df.empty: return generate_mock_data(10, "CSV is empty")

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        # 🔄 피벗 테이블 (일별 평균)
        # 중요: device_name 별로 평균을 내어 날짜별로 정렬
        pivot_df = df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
        
        # 🎯 센서명 매칭 키워드 최적화 (한글/영문/대소문자 무시)
        def find_best_col(df, kws):
            for col in df.columns:
                c = str(col).lower()
                if any(kw.lower() in c for kw in kws): return col
            return None

        t_col = find_best_col(pivot_df, ['온도', 'temp'])
        h_col = find_best_col(pivot_df, ['습도', 'humi'])
        l_col = find_best_col(pivot_df, ['조도', 'light', 'ppfd', '광량'])
        e_col = find_best_col(pivot_df, ['ec'])
        p_col = find_best_col(pivot_df, ['ph'])

        # 🔗 타임라인 강제 병합 (Reindex)
        full_df = pd.merge(timeline_df, pivot_df, on='date', how='left').sort_values('date')
        
        res_dates = [d.strftime('%Y-%m-%d') for d in full_df['date']]
        res_temp = [safe_val(x) for x in (full_df[t_col] if t_col is not None else [None]*10)]
        res_humi = [safe_val(x) for x in (full_df[h_col] if h_col is not None else [None]*10)]
        res_light = [safe_val(x) for x in (full_df[l_col] if l_col is not None else [None]*10)]
        res_ec = [safe_val(x) for x in (full_df[e_col] if e_col is not None else [None]*10)]
        res_ph = [safe_val(x) for x in (full_df[p_col] if p_col is not None else [None]*10)]

        # GDD (적산온도) 계산 로직 보호
        gdd_vals = []
        for t in res_temp:
            val = max(t - BASE_TEMP, 0) if t is not None else 0
            gdd_vals.append(val)
        cum_gdd = np.cumsum(gdd_vals).tolist()

        # 생육 측정 데이터 병합
        measured = {"dates": [], "ratios": []}
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                    m_df = pd.DataFrame(log_data)
                    if not m_df.empty:
                        m_df['date'] = pd.to_datetime(m_df['date']).dt.date
                        # 10일 타임라인 내의 데이터만 합침
                        merged_g = pd.merge(m_df, timeline_df, on='date', how='inner')
                        measured = {
                            "dates": [d.strftime('%Y-%m-%d') for d in merged_g['date']],
                            "ratios": merged_g['ratio'].tolist()
                        }
            except Exception as ge:
                print(f"⚠️ [AI Log] Growth log error: {ge}")

        # ✅ 최종 결과 반환
        return {
            "success": True,
            "dates": res_dates,
            "temp": res_temp,
            "humi": res_humi,
            "light": res_light,
            "ec": res_ec,
            "ph": res_ph,
            "measured_growth": measured,
            "cumulative_gdd": [round(v, 2) for v in cum_gdd]
        }

    except Exception as e:
        import traceback
        err_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"❌ [AI Model Engine] Fatal Error: {err_msg}")
        return generate_mock_data(10, err_msg)
