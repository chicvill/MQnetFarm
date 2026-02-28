@echo off
echo [MQnetFarm] Docker 컨테이너 빌드 및 실행 중...
docker-compose up --build -d

echo.
echo [!] 컨테이너가 실행되었습니다.
echo [!] 각 농장 시스템에 다음 주소로 접속하세요:
echo [!] 1. 서울 농장: http://localhost:8001
echo [!] 2. 부산 농장: http://localhost:8002
echo [!] 3. 기본 시스템: http://localhost:8000
echo.
echo [!] 로그를 보려면 'docker-compose logs -f'를 입력하세요.
pause
