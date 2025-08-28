FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Minimal OS deps for pandas/lxml & TLS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata curl gcc g++ build-essential \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first (use Docker cache)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements.txt

# Copy backend source
COPY backend /app

EXPOSE 8000

# Quieter logs but still helpful
CMD ["uvicorn","src.main:app","--host","0.0.0.0","--port","8000","--no-access-log"]
