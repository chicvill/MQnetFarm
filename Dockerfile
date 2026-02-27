# 1. 빌드 스테이지
FROM python:3.9-slim AS builder

WORKDIR /app

# 컴파일 없이 바이너리 휠만 사용하도록 설정 (메모리 절약 핵심)
COPY requirements.txt .
RUN pip install --user --no-cache-dir --only-binary :all: -r requirements.txt


# 2. 실행 스테이지
FROM python:3.9-slim

WORKDIR /app

# 실행에 필요한 최소 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 빌드된 패키지 복사
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 소스 코드 복사
COPY . .

# Render 기본 포트 (Render는 8000 또는 10000 제공)
ENV PORT=8000
EXPOSE 8000

CMD ["python", "main_async.py"]
