#!/bin/bash
# PRISM backend entrypoint for Hugging Face Spaces (production).
#
# Unlike the local docker-compose entrypoint, this one FAIL-FASTS: if database
# migrations cannot be applied, the container exits non-zero instead of serving
# an API against an empty/mismatched schema.
set -euo pipefail

echo "=== PRISM Backend (Hugging Face Spaces) ==="

PORT="${PORT:-7860}"

# All datastores are managed external services (Neon, Aiven, AuraDB, Upstash,
# R2); their URLs come straight from Space secrets. Apply migrations against the
# live MySQL + Postgres instances before accepting traffic.
echo "Applying database migrations..."
python /app/backend/db/migrate.py

# Gunicorn:
#   --preload loads the app (and the sentence-transformers model) ONCE in the
#   master, then forks workers (copy-on-write) so the model isn't duplicated per
#   worker. gthread workers handle the mostly-IO request load; the timeout is
#   generous because embedding a cold query can take a couple of seconds.
WORKERS="${GUNICORN_WORKERS:-2}"
THREADS="${GUNICORN_THREADS:-4}"

echo "Starting gunicorn on 0.0.0.0:${PORT} (workers=${WORKERS}, threads=${THREADS})..."
exec gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WORKERS}" \
    --threads "${THREADS}" \
    --worker-class gthread \
    --preload \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    backend.app:app
