# Base Image
FROM python:3.9-slim

# Working Directory
WORKDIR /app

# System Dependencies (Essential only for gspread/headless)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Source Code
COPY . .

# Expose Port
EXPOSE 8000

# Run Application
CMD ["python", "main_async.py"]
