# Base Image
FROM python:3.9-slim

# Working Directory
WORKDIR /app

# System Dependencies (Merged to reduce layers and memory usage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python Dependencies (Install first to leverage layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy Source Code (Except items in .dockerignore)
COPY . .

# Environment Defaults
ENV PORT=10000
EXPOSE 10000

# Run Application
CMD ["python", "main_async.py"]
