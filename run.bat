@echo off
chcp 65001 >nul
title SmartFarm System Launcher
echo =======================================================
echo   🌌 SmartFarm Live 시스템 및 홍보 페이지를 시작합니다...
echo =======================================================
echo.

REM 1. 파이썬 실행 명령어 확인
set PY_CMD=
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY_CMD=py
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set PY_CMD=python
    )
)

if "%PY_CMD%"=="" (
    echo Python을 찾을 수 없습니다. 
    echo Python이 설치되어 있고 PATH에 등록되어 있는지 확인하세요.
    pause
    exit /b 1
)

set PORT=8007

echo [0] 파이썬 버전 확인: %PY_CMD%
echo [1] 필수 라이브러리 확인 및 설치 중...
"%PY_CMD%" -m pip install -r requirements.txt >nul 2>nul

echo [2] Chrome 브라우저에서 홈페이지를 여는 중...
echo     접속 주소: http://localhost:%PORT%
start chrome "http://localhost:%PORT%"

echo [3] 스마트팜 데이터 서버 기동 중...
echo.

"%PY_CMD%" main_async.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo ⚠️ 프로그램이 종료되었습니다. (Error Code: %ERRORLEVEL%)
    pause
)
