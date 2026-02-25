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

# Copy project source
COPY . .

# Pre-download the ML model into the image so the first request isn't slow.
# The model is cached at /app/model_cache by setting HF_HOME.
ENV HF_HOME=/app/model_cache
RUN python -c "\
from transformers import pipeline; \
pipeline('image-classification', model='skylord/swin-finetuned-food101')"

# Collect static files
RUN python manage.py collectstatic --noinput

# Give the non-root user ownership
RUN chown -R appuser:appuser /app
USER appuser

# HuggingFace Spaces expects port 7860
EXPOSE 7860

# Run gunicorn; 2 workers is plenty for <100 users on a 16 GB RAM Space
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:7860", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-"]
