import pandas as pd
import numpy as np
import json
from datetime import datetime
try:
    from scipy.optimize import curve_fit
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# 1. 환경 설정 및 임계 온도 정의
BASE_TEMP = 10.0  # 작물 성장 하한 온도 (예: 토마토 10도, 상추 5도)
K_MAX_GDD = 1000  # 예측할 최대 누적 온도 범위

def calculate_gdd(temp_df):
    """
    온도 데이터를 기반으로 누적 적산온도(GDD) 계산 (적분 개념 적용)
    """
    # 일별 평균 온도 계산
    temp_df['date'] = pd.to_datetime(temp_df['timestamp']).dt.date
    daily_avg = temp_df[temp_df['device_name'] == '온도 센서'].groupby('date')['value'].mean().reset_index()
    
    # GDD 계산: (평균기온 - 기준기온), 0보다 작으면 0
    daily_avg['gdd'] = daily_avg['value'].apply(lambda x: max(x - BASE_TEMP, 0))
    daily_avg['cumulative_gdd'] = daily_avg['gdd'].cumsum()
    
    return daily_avg

def logistic_model(x, L_max, k, x0):
    """
    로지스틱 성장 모델 (Sigmoid 함수)
    L_max: 최대 성장 한계치 (생물량/면적)
    k: 성장 속도 계수 (미분 관계)
    x0: 성장의 변곡점 (GDD 기준)
    """
    return L_max / (1 + np.exp(-k * (x - x0)))

def fit_growth_model(growth_data, gdd_data):
    """
    관측된 데이터와 GDD 데이터를 결합하여 모델 피팅
    """
    # 데이터 병합
    growth_df = pd.DataFrame(growth_data)
    growth_df['date'] = pd.to_datetime(growth_df['date']).dt.date
    
    merged = pd.merge(growth_df, gdd_data, on='date', how='inner')
    
    if len(merged) < 3:
        return None, "데이터가 부족합니다 (최소 3개 이상의 측정 포인트 필요)"

    # 관측값 (x: 누적 GDD, y: 잎의 면적 비율)
    x_obs = merged['cumulative_gdd'].values
    y_obs = merged['ratio'].values

    # Curve Fitting (비선형 최소자승법)
    try:
        # 초기값 추정 [L_max, k, x0]
        p0 = [max(y_obs) * 1.2, 0.05, np.median(x_obs)]
        popt, _ = curve_fit(logistic_model, x_obs, y_obs, p0=p0, maxfev=5000)
        return popt, merged
    except Exception as e:
        return None, str(e)

import os

def run_analysis():
    # 데이터 폴더 설정
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    
    # 데이터 로드
    try:
        tsdb_path = os.path.join(DATA_DIR, 'smartfarm_tsdb.csv')
        growth_log_path = os.path.join(DATA_DIR, 'growth_log.json')
        
        if not os.path.exists(tsdb_path):
            print(f"오류: {tsdb_path} 파일을 찾을 수 없습니다.")
            return

        tsdb_df = pd.read_csv(tsdb_path)
        # 타임스탬프 변환
        tsdb_df['timestamp'] = pd.to_datetime(tsdb_df['timestamp'])
        tsdb_df['date'] = tsdb_df['timestamp'].dt.date
        
        if os.path.exists(growth_log_path):
            with open(growth_log_path, 'r', encoding='utf-8') as f:
                growth_log = json.load(f)
        else:
            print(f"오류: {growth_log_path} 파일을 찾을 수 없습니다.")
            return
            
    except Exception as e:
        print(f"파일을 읽는 중 오류 발생: {e}")
        return

    # 1. 시계열 데이터 전처리 (일별 평균)
    pivot_df = tsdb_df.pivot_table(index='date', columns='device_name', values='value', aggfunc='mean').reset_index()
    
    # 2. 적산온도(GDD) 계산
    print("Step 1: 적산온도(GDD) 계산 중...")
    if '온도 센서' in pivot_df.columns:
        pivot_df['gdd'] = pivot_df['온도 센서'].apply(lambda x: max(x - BASE_TEMP, 0))
        pivot_df['cumulative_gdd'] = pivot_df['gdd'].cumsum()
    else:
        print("온도 데이터가 없습니다.")
        return

    # 3. 모델 최적화 (Fitting)
    print("Step 2: 성장 모델 최적화 중...")
    popt, result_df = fit_growth_model(growth_log, pivot_df)
    
    if popt is None:
        print(f"모델 피팅 실패: {result_df}")
        return

    L_max, k, x0 = popt
    
    # --- 시각화 (Multi-panel) ---
    fig, axes = plt.subplots(4, 1, figsize=(12, 18), sharex=True)
    plt.subplots_adjust(hspace=0.3)
    
    # 일자별 X축 라벨용 데이터
    dates = pivot_df['date'].values
    cumulative_gdd = pivot_df['cumulative_gdd'].values

    # Plot 1: 성장 곡선 및 예측
    ax1 = axes[0]
    ax1.scatter(result_df['date'], result_df['ratio'], color='red', label='Measured Growth')
    # 예측 곡선을 위한 날짜 확장 (보간용)
    future_gdd = np.linspace(0, max(cumulative_gdd) * 1.5, 100)
    pred_growth = logistic_model(future_gdd, *popt)
    
    # GDD를 다시 날짜 인덱스로 매핑하기 어려우므로 X축은 'GDD'가 아닌 'Date'로 통일하여 그림
    # 대신 현재 데이터 기간 내에서의 예측 곡선을 그림
    current_pred = logistic_model(cumulative_gdd, *popt)
    ax1.plot(dates, current_pred, label='Growth Model (Logistic)', color='green', linewidth=2)
    ax1.set_title('1. Crop Growth Prediction (Model vs Measured)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Leaf Area Ratio (%)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: 온도 및 습도
    ax2 = axes[1]
    if '온도 센서' in pivot_df.columns:
        ax2.plot(dates, pivot_df['온도 센서'], color='orange', marker='o', label='Temp (°C)')
    ax2_twin = ax2.twinx()
    if '습도 센서' in pivot_df.columns:
        ax2_twin.plot(dates, pivot_df['습도 센서'], color='blue', marker='x', label='Humidity (%)')
    ax2.set_title('2. Environmental: Temp & Humidity', fontsize=12)
    ax2.set_ylabel('Temp (°C)', color='orange')
    ax2_twin.set_ylabel('Humidity (%)', color='blue')
    ax2.grid(True, alpha=0.3)

    # Plot 3: 조도 (PPFD)
    ax3 = axes[2]
    if '조도(PPFD) 센서' in pivot_df.columns:
        ax3.bar(dates, pivot_df['조도(PPFD) 센서'], color='gold', alpha=0.6, label='Light (PPFD)')
    ax3.set_title('3. Light Intensity (PPFD)', fontsize=12)
    ax3.set_ylabel('PPFD')
    ax3.grid(True, alpha=0.3)

    # Plot 4: 양액 상태 (EC & pH)
    ax4 = axes[3]
    if 'EC 센서' in pivot_df.columns:
        ax4.plot(dates, pivot_df['EC 센서'], color='purple', marker='s', label='EC')
    ax4_twin = ax4.twinx()
    if 'pH 센서' in pivot_df.columns:
        ax4_twin.plot(dates, pivot_df['pH 센서'], color='teal', marker='^', label='pH')
    ax4.set_title('4. Nutrient Solution: EC & pH', fontsize=12)
    ax4.set_ylabel('EC', color='purple')
    ax4_twin.set_ylabel('pH', color='teal')
    ax4.grid(True, alpha=0.3)

    plt.xticks(rotation=45)
    plt.xlabel('Date')
    
    # 결과 저장 (DATA_DIR 내부로 저장하여 웹 서비스 가능하게 함)
    plt.tight_layout()
    output_path = os.path.join(DATA_DIR, 'growth_prediction_chart.png')
    plt.savefig(output_path)
    
    print(f"\n[모델 분석 결과]")
    print(f"- 최대 예상 성장치(L_max): {L_max:.2f}%")
    print(f"- 성장 계수(k): {k:.4f}")
    print(f"- 성장 변곡점(GDD_0): {x0:.2f} degree-days")
    print(f"\n통합 분석 차트가 '{output_path}'에 업데이트되었습니다.")

if __name__ == "__main__":
    run_analysis()
