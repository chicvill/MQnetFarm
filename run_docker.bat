@echo off
echo [MQnetFarm] Docker 컨테이너 빌드 및 실행 중...
docker-compose up --build -d

echo.
echo [!] 컨테이너가 실행되었습니다.
echo [!] 웹 브라우저에서 'http://localhost:8000'으로 접속하세요.
echo [!] 로그를 보려면 'docker-compose logs -f'를 입력하세요.
pause
