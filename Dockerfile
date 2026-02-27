FROM python:3.9-slim

WORKDIR /app

# v2.5+: 시스템 라이브러리(libgl1 등)가 더 이상 필요하지 않습니다.
# 빌드 성공률을 높이기 위해 외부 패키지 설치를 최소화합니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# Render 포트 설정
ENV PORT=8000
EXPOSE 8000

# 앱 실행
CMD ["python", "main_async.py"]
