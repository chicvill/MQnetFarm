@echo off
chcp 65001 >nul
title SmartFarm System Launcher
echo =======================================================
echo   🌌 SmartFarm Live 시스템 및 대시보드를 시작합니다...
echo =======================================================
echo.

:: 1. 필요한 라이브러리 설치 (최초 1회 필요)
echo [0] 필요한 라이브러리 확인 및 설치 중...
python -m pip install opencv-python numpy requests

echo [1] Chrome 브라우저에서 대시보드를 여는 중...
start chrome "http://localhost:8000/html/index.html"

echo [2] 데이터 서버 및 시뮬레이션 기동 중...
echo (종료하려면 이 창에서 Ctrl+C를 누르세요.)
echo.

python main_async.py

:: 만약 에러로 인해 종료된 경우 창이 바로 닫히지 않도록 함
if %ERRORLEVEL% neq 0 (
    echo.
    echo ⚠️ 프로그램이 예상치 못하게 종료되었습니다. (Error Code: %ERRORLEVEL%)
    pause
)
