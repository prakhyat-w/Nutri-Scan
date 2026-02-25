# syntax=docker/dockerfile:1
FROM python:3.11-slim

# HuggingFace Spaces runs containers as a non-root user (UID 1000).
# We create the same user so file permissions work correctly.
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install OS-level dependencies needed by Pillow and psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer-caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Pre-download the BLIP model BEFORE copying source code.
# Keeping this layer before `COPY . .` means it is cached by Docker and will
# NOT re-download on every source-code push — only when requirements change.
ENV HF_HOME=/app/model_cache
RUN python -c "\
from transformers import pipeline; \
pipeline('image-to-text', model='Salesforce/blip-image-captioning-base')"

# Copy project source
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Give the non-root user ownership
RUN chown -R appuser:appuser /app
USER appuser

# HuggingFace Spaces expects port 7860
EXPOSE 7860

# 1 worker: BLIP needs ~1 GB RAM; 2 workers risk OOM and doubled startup time.
# 300 s timeout: loading BLIP on CPU takes 60-120 s — default 30 s kills the worker.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:7860", \
     "--workers", "1", \
     "--timeout", "300", \
     "--access-logfile", "-"]
