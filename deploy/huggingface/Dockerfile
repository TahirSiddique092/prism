# PRISM backend — Hugging Face Spaces (Docker SDK) production image.
#
# Differs from backend/Dockerfile (local docker-compose dev) in two ways:
#   1. Runs under gunicorn (a real WSGI server) instead of the Flask dev server.
#   2. Listens on $PORT (HF Spaces injects 7860) and fail-fasts on bad config.
#
# Build context must be the REPOSITORY ROOT so `backend/` is available:
#   docker build -f deploy/huggingface/Dockerfile -t prism-backend .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PRISM_ENV=production \
    PORT=7860

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-openbsd \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Pre-download NLTK + sentence-transformers model at build time so the first
# request doesn't pay the (multi-hundred-MB) download cost at runtime.
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True); from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY backend /app/backend
COPY deploy/huggingface/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
