import numpy as np
import json
import os
import pandas as pd

# 1. 환경 설정
BASE_TEMP = 10.0

def run_analysis_data():
    """
    scipy/matplotlib 없이 순수 수학으로 성장 데이터를 계산하여 JSON으로 반환
    """
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    try:
        tsdb_df = pd.read_csv(os.path.join(DATA_DIR, 'smartfarm_tsdb.csv'))
        tsdb_df['timestamp'] = pd.to_datetime(tsdb_df['timestamp'])
        tsdb_df['date'] = tsdb_df['timestamp'].dt.date
        
        with open(os.path.join(DATA_DIR, 'growth_log.json'), 'r', encoding='utf-8') as f:
            growth_log = json.load(f)
            
        # 일별 평균 데이터 (Pivot)
        pivot_df = tsdb_df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
        
        # GDD 계산
        if '온도 센서' in pivot_df.columns:
            pivot_df['gdd'] = pivot_df['온도 센서'].apply(lambda x: max(x - BASE_TEMP, 0))
            pivot_df['cumulative_gdd'] = pivot_df['gdd'].cumsum()
        else:
            return {"success": False, "error": "No Temp Data"}

        # 성장 데이터 결합
        growth_df = pd.DataFrame(growth_log)
        growth_df['date'] = pd.to_datetime(growth_df['date']).dt.date
        merged = pd.merge(growth_df, pivot_df, on='date', how='inner')
        
        if len(merged) < 2:
            return {"success": False, "error": "Need more measurements"}

        # [기초 수학 모델] 로지스틱 곡선 근사 (단순화된 형태)
        # 복잡한 curve_fit 대신, 현재까지의 데이터를 Chart.js로 넘겨서 
        # 화면에서 처리하도록 모든 데이터를 가공해서 보냄
        
        report_data = {
            "success": True,
            "dates": pivot_df['date'].astype(str).tolist(),
            "temp": pivot_df.get('온도 센서', []).tolist(),
            "humi": pivot_df.get('습도 센서', []).tolist(),
            "light": pivot_df.get('조도(PPFD) 센서', []).tolist(),
            "ec": pivot_df.get('EC 센서', []).tolist(),
            "ph": pivot_df.get('pH 센서', []).tolist(),
            "measured_growth": {
                "dates": merged['date'].astype(str).tolist(),
                "ratios": merged['ratio'].tolist()
            },
            "cumulative_gdd": pivot_df['cumulative_gdd'].tolist()
        }
        return report_data

    except Exception as e:
        return {"success": False, "error": str(e)}
