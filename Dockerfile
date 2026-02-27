# 1. 빌드 스테이지
FROM python:3.9-slim AS builder

WORKDIR /app

# 빌드 필수 도구 설치 (scipy 등 컴파일용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 유저 경로에 설치하여 복사를 용이하게 함
RUN pip install --user --no-cache-dir -r requirements.txt


# 2. 실행 스테이지
FROM python:3.9-slim

WORKDIR /app

# 실행에 필요한 최소 환경 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 빌드된 패키지만 복사 (용량 및 메모리 최적화)
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 소스 코드 복사
COPY . .

# Render 포트 설정
ENV PORT=10000
EXPOSE 10000

# 실행 명령
CMD ["python", "main_async.py"]
