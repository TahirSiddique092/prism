---
title: PRISM Backend
emoji: 🔎
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# PRISM Backend (Hugging Face Space)

This is the **template README** for the Hugging Face Space that hosts the PRISM
Flask API. Copy this file (keeping the YAML front-matter above) to the **root of
the Space repository** — Hugging Face reads `sdk: docker` and `app_port: 7860`
from the front-matter to build and route the container.

## How the Space is built

Hugging Face Spaces (Docker SDK) builds from a file named `Dockerfile` at the
Space repo root. Use the contents of [`deploy/huggingface/Dockerfile`](./Dockerfile)
as that root `Dockerfile` (it expects the repo-root build context so `backend/`
is present), together with [`deploy/huggingface/entrypoint.sh`](./entrypoint.sh).

The container:
- runs the API under **gunicorn** (not the Flask dev server),
- listens on `$PORT` (HF injects `7860`),
- applies DB migrations on boot and **fail-fasts** if they don't apply,
- loads the `all-MiniLM-L6-v2` model once (baked into the image at build time).

## Required Space secrets

Set these in **Settings → Variables and secrets** (see
[`../huggingface-setup.md`](../huggingface-setup.md) for where each value comes
from). Never commit real values.

```
PRISM_ENV=production
JWT_SECRET=<32+ random chars>
CORS_STRICT=true
FRONTEND_URL=https://<your-project>.vercel.app

MYSQL_URL=mysql+pymysql://<user>:<pass>@<aiven-host>:<port>/<db>
POSTGRES_URL=postgresql://<user>:<pass>@<neon-host>/<db>?sslmode=require
NEO4J_URI=neo4j+s://<auradb-host>
NEO4J_USER=neo4j
NEO4J_PASSWORD=<auradb-password>
REDIS_URL=rediss://<upstash-host>:<port>?password=<token>

S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com
S3_ACCESS_KEY=<r2-access-key>
S3_SECRET_KEY=<r2-secret-key>
S3_BUCKET=prism-documents
S3_REGION=auto
```

> Sleep note: the free CPU Space sleeps after 48h idle and the first request
> after a cold start takes ~30–60s while the model loads. All data lives in the
> managed databases, so sleeping/restarting the Space never loses data.
