# Dockerfile for Telegram LLM Bot
# Multi-stage build for optimized production image

# Stage 1: Builder
FROM ollama/ollama:latest AS ollama

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    python3-dev \
    gnupg \
    libpq5 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./
COPY requirements.txt ./
COPY .env ./
COPY app ./app

# Upgrade pip and install setuptools (replaces distutils in Python 3.12)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install production dependencies from pyproject.toml
RUN pip install --no-cache-dir -e .

# Start Ollama temporarily in the background, pull model, then stop it
RUN ollama serve & \
    sleep 5 && \
    ollama pull phi3 && \
    pkill ollama

# Expose port for FastAPI
EXPOSE 8088

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/health').read()" || exit 1

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Start Ollama + FastAPI together
CMD bash -c "\
    ollama serve & \
    sleep 5 && \
    uvicorn app.main:app --host 0.0.0.0 --port 8088 --reload \
"