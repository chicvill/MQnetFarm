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

        # 1. 일별 평균 데이터로 피벗 (device_name별로 수집된 데이터를 날짜별로 정렬)
        pivot_df = tsdb_df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
            
        # 2. 센서 이름 유연하게 매칭 (한글/영문/부분일치 대응)
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

        # 3. GDD(적산온도) 계산
        if temp_col:
            pivot_df['gdd'] = pivot_df[temp_col].apply(lambda x: max(float(x) - BASE_TEMP, 0))
            pivot_df['cumulative_gdd'] = pivot_df['gdd'].cumsum()
        else:
            return {"success": False, "error": f"No Temp Data (Available Columns: {list(pivot_df.columns)})"}

        # 4. 실제 측정 성장 데이터와 결합
        growth_df = pd.DataFrame(growth_log)
        growth_df['date'] = pd.to_datetime(growth_df['date']).dt.date
        merged = pd.merge(growth_df, pivot_df, on='date', how='inner')
        
        # 5. 결과 리포트 데이터 구성
        report_data = {
            "success": True,
            "dates": pivot_df['date'].astype(str).tolist(),
            "temp": pivot_df[temp_col].tolist() if temp_col else [],
            "humi": pivot_df[humi_col].tolist() if humi_col else [],
            "light": pivot_df[light_col].tolist() if light_col else [],
            "ec": pivot_df[ec_col].tolist() if ec_col else [],
            "ph": pivot_df[ph_col].tolist() if ph_col else [],
            "measured_growth": {
                "dates": merged['date'].astype(str).tolist(),
                "ratios": merged['ratio'].tolist()
            },
            "cumulative_gdd": pivot_df['cumulative_gdd'].tolist()
        }
        return report_data

    except Exception as e:
        import traceback
        return {"success": False, "error": f"{str(e)}\n{traceback.format_exc()}"}
