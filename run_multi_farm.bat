@echo off
title Multi-Farm Test Launcher
chcp 65001 >nul

echo =======================================================
echo   📍 서울/부산 다중 농장 배포 시험을 시작합니다.
echo =======================================================

:: 1. 폴더 확인
if not exist seoul_data (
    echo [!] seoul_data 폴더가 없어 생성합니다.
    mkdir seoul_data
    xcopy data seoul_data /E /I /H /Y
)
if not exist busan_data (
    echo [!] busan_data 폴더가 없어 생성합니다.
    mkdir busan_data
    xcopy data busan_data /E /I /H /Y
)

:: 2. 서울 농장 실행 (Port 8001 / DATA_DIR seoul_data)
echo [1/2] 서울 농장 시스템 기동 (Port: 8001)
start "SEOUL FARM (8001)" cmd /c "set DATA_DIR=seoul_data&& set PORT=8001&& python main_async.py"

timeout /t 2 /nobreak >nul

:: 3. 부산 농장 실행 (Port 8002 / DATA_DIR busan_data)
echo [2/2] 부산 농장 시스템 기동 (Port: 8002)
start "BUSAN FARM (8002)" cmd /c "set DATA_DIR=busan_data&& set PORT=8002&& python main_async.py"

echo.
echo -------------------------------------------------------
echo ✅ 모든 농장 시스템이 개별 포트에서 가동되었습니다.
echo 🖥️ 서울 대시보드: http://localhost:8001/html/index.html
echo 🖥️ 부산 대시보드: http://localhost:8002/html/index.html
echo.
echo (참고: 각 창에서 로그를 확인하고, 작업이 끝나면 창을 닫으세요.)
echo -------------------------------------------------------
pause
