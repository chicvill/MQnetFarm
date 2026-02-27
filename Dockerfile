FROM python:3.9-slim

WORKDIR /app

# Install system dependencies (merged and optimized)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Render Port (default is 10000 often, but we use 8000 and it's configurable)
ENV PORT=8000
EXPOSE 8000

# Run
CMD ["python", "main_async.py"]
