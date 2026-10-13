# PRISM Backend Deployment — Hugging Face Spaces + Managed Free Tiers (Path B)

This supersedes the OCI VM deployment (`deploy/README.md`) as the production
target for the PRISM backend. The OCI/`docker-compose` setup remains for **local
development** only.

## Why this architecture

The backend loads `sentence-transformers/all-MiniLM-L6-v2` (PyTorch, ~1–2 GB
RAM) in-process, which does not fit the 256–512 MB offered by most free PaaS
(Render/Koyeb free, etc.). Hugging Face Spaces' free CPU tier gives **2 vCPU /
16 GB RAM** and HTTPS out of the box, which fits the model comfortably. The five
datastores move to managed free tiers so no single host has to run everything
and data survives Space restarts/sleeps.

| Component | Was (OCI) | Now (free managed) | Free-tier notes |
|-----------|-----------|--------------------|-----------------|
| Flask API + model | OCI VM container | **Hugging Face Space (Docker)** | 2 vCPU/16 GB; sleeps after 48h idle; HTTPS |
| pgvector (vectors) | pgvector container | **Neon** | pgvector supported; ~1 GB storage |
| MySQL (users/docs/FULLTEXT) | MySQL container | **Aiven for MySQL** | always-free; 1 GB; InnoDB FULLTEXT supported |
| Neo4j (topic graph) | Neo4j container | **Neo4j AuraDB Free** | 200k nodes; pauses after 3 days idle |
| Redis (cache) | Redis container | **Upstash Redis** | 256 MB / 500k cmds per month |
| Object store (PDFs) | MinIO container | **Cloudflare R2** (or Supabase Storage) | S3-compatible, HTTPS pre-signed URLs |

> HTTPS everywhere also closes two audit findings for free: credentials/JWTs are
> no longer sent in cleartext (backend is HTTPS), and the inline PDF viewer works
> because pre-signed object URLs are HTTPS (no mixed-content block).

## 1. Provision the managed databases

Create a free account on each and capture the connection string:

1. **Neon** (pgvector) → create project → copy the `postgresql://…?sslmode=require`
   connection string → `POSTGRES_URL`. Run `CREATE EXTENSION IF NOT EXISTS vector;`
   (the migration also does this).
2. **Aiven for MySQL** → create a free MySQL service → copy host/port/user/pass/db
   → assemble `MYSQL_URL=mysql+pymysql://user:pass@host:port/dbname`.
3. **Neo4j AuraDB Free** → create instance → download credentials →
   `NEO4J_URI=neo4j+s://<id>.databases.neo4j.io`, `NEO4J_USER`, `NEO4J_PASSWORD`.
4. **Upstash Redis** → create database → copy the TLS (`rediss://`) URL → `REDIS_URL`.
5. **Cloudflare R2** → create a bucket named `prism-documents` → create an API
   token (Object Read & Write) → note the account endpoint
   `https://<account>.r2.cloudflarestorage.com`, access key, secret key →
   `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET=prism-documents`,
   `S3_REGION=auto`.

## 2. Create the Hugging Face Space

1. huggingface.co → **New Space** → SDK **Docker** → blank/other template.
2. In the Space repo, place a root **`Dockerfile`** with the contents of
   `deploy/huggingface/Dockerfile`, the `entrypoint.sh` from
   `deploy/huggingface/`, a root `README.md` from `deploy/huggingface/README.md`
   (keep its YAML front-matter), and the `backend/` directory. The simplest way
   is to push this whole repo to the Space's git remote and copy those two files
   to the root, or add the Space as a second remote and sync.
3. In **Settings → Variables and secrets**, add every secret listed in
   `deploy/huggingface/README.md` (JWT_SECRET, PRISM_ENV=production,
   CORS_STRICT=true, FRONTEND_URL, the five DB URLs, and the R2 credentials).
4. The Space builds and starts; once healthy its URL is
   `https://<user>-<space>.hf.space`. Verify:
   ```bash
   curl -f https://<user>-<space>.hf.space/health   # {"status":"ok"}
   ```

Startup fail-fasts if `JWT_SECRET` is missing/weak (PRISM_ENV=production) or if
migrations can't apply — so a bad config surfaces in the build logs, not as a
silently broken API.

## 3. Point the frontend at the Space

On Vercel (**Settings → Environment Variables**):
```
API_URL=https://<user>-<space>.hf.space          # server-only (preferred)
NEXT_PUBLIC_API_URL=https://<user>-<space>.hf.space   # kept for compatibility
```
Redeploy the frontend. Set `FRONTEND_URL` (and keep `CORS_STRICT=true`) on the
Space so the backend's CORS allows only your Vercel origin.

## 4. End-to-end verification

1. Register/login on the Vercel site → JWT cookie set, dashboard loads.
2. Upload a PDF → appears as `processing` then `ready`; the inline PDF viewer
   loads (HTTPS pre-signed R2 URL).
3. Search a plain-English query → ranked snippets; repeat → `cached` badge.
4. Analytics pages populate (history, top documents, unsearched).

## Caveats

- **Cold starts / sleep:** the free Space sleeps after 48h idle; the first
  request then takes ~30–60s to load the model. Data is safe (external DBs).
- **AuraDB pause:** the free graph instance pauses after 3 days idle and is
  deleted after 30 days idle — hit it periodically or keep the credentials to
  recreate. Topic-graph failures already degrade gracefully (related docs/topics
  return empty, never error).
- **Free-tier quotas** (Upstash 500k cmds/mo, Neon 1 GB, Aiven 1 GB) are ample
  for a course-project / demo workload but not production scale.
