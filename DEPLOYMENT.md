# PRISM — Production Deployment Plan (Path B: Hugging Face Spaces + managed free tiers)

This is the complete, step-by-step runbook to take PRISM from source to a live
production deployment using **only free tiers**. It assumes you are starting
fresh with **one new Google account** dedicated to this project.

- **Backend** (Flask API + embedding model) → **Hugging Face Spaces** (Docker)
- **Frontend** (Next.js) → **Vercel**
- **Data** → **Neon** (pgvector **and** S3-compatible Object Storage for files), Aiven (MySQL), Neo4j AuraDB, Upstash (Redis)

> **No credit card anywhere, and one fewer account.** Files are stored in
> **Neon Object Storage** — an S3-compatible store built into the same Neon
> project that already holds the vectors (5 GB free, no card). Our backend speaks
> generic S3, so this is a config-only choice; Cloudflare R2 remains a drop-in
> alternative (but R2 asks for a card to activate).

> Companion docs: `deploy/huggingface-setup.md` (condensed), `ADR-013`
> (why this architecture), `deploy/README.md` (legacy OCI / local dev).

---

## 0. How this fits together

```
Browser ──HTTPS──> Vercel (Next.js)
                     │  server route handlers forward the JWT
                     ▼
                 Hugging Face Space (Flask API + all-MiniLM-L6-v2)  ──HTTPS──┐
                     │          │            │           │                    │
                     ▼          ▼            ▼           ▼                    ▼
                 Neon        Aiven        AuraDB      Upstash          Neon Object Storage
               (pgvector)   (MySQL)      (Neo4j)     (Redis)          (PDF storage, same project)
```

Everything is HTTPS end-to-end, which is what makes the inline PDF viewer and
secure credential flow work.

### 0.1 The one-Google-account note

| Service | Sign in with Google? | Notes |
|---------|----------------------|-------|
| Hugging Face | ✅ Yes | "Continue with Google" on signup |
| Neon | ✅ Yes | Google / GitHub / email |
| Aiven | ✅ Yes | "Sign up with Google" |
| Neo4j Aura | ✅ Yes | Google / email |
| Upstash | ✅ Yes | Google / GitHub |
| Vercel | ⚠️ Via email | Vercel logs in with GitHub/GitLab/Bitbucket/**Email**. We use the **Vercel CLI + email** path below so you do NOT need to tie it to a GitHub account. |

> Object storage no longer needs its own provider — it lives inside your **Neon**
> project (same Google sign-in, no card). Cloudflare is dropped entirely.

> Use the **same Google email** everywhere so all dashboards live under one
> identity. Turn on 2FA where offered.

### 0.2 Credentials vault (fill this in as you go — keep it OUT of git)

Create a private note (not in this repo) and collect these. You will paste them
into Hugging Face Space secrets (backend) and Vercel env vars (frontend) later.

```
# --- Backend (Hugging Face Space → Settings → Variables and secrets) ---
PRISM_ENV=production
CORS_STRICT=true
JWT_SECRET=________________________________________   # step 2
FRONTEND_URL=https://________________.vercel.app        # step 4 (fill after Vercel)

POSTGRES_URL=postgresql://____:____@____/____?sslmode=require   # Neon  (step 1a)
MYSQL_URL=mysql+pymysql://____:____@____:____/____             # Aiven (step 1b)
NEO4J_URI=neo4j+s://____.databases.neo4j.io                    # AuraDB (step 1c)
NEO4J_USER=neo4j
NEO4J_PASSWORD=________________________________________
REDIS_URL=rediss://____:____@____:____                        # Upstash (step 1d)

S3_ENDPOINT=https://br-____.storage.c-2.____.aws.neon.tech    # Neon Object Storage (step 1e)
S3_ACCESS_KEY=________________________________________        # Neon credential token_id
S3_SECRET_KEY=________________________________________        # Neon credential s3_secret_access_key
S3_BUCKET=prism-documents
S3_REGION=____                                                # your Neon branch region, e.g. us-east-2

# --- Frontend (Vercel → Environment Variables) ---
API_URL=https://____-____.hf.space                            # step 3 (HF Space URL)
NEXT_PUBLIC_API_URL=https://____-____.hf.space
```

---

## 1. Prerequisites (local machine, ~10 min)

You run most of this from a local clone of the repo.

```bash
# Verify tooling
git --version          # any recent
python3 --version      # 3.11+ recommended
node --version         # 18+ (Vercel/Next 16)
openssl version        # for the JWT secret
```

- A clone of this repository (you already have it).
- The new Google account email in front of you.
- ~45–60 minutes total. Provisioning the five data services is the bulk of it.

> Order matters: provision **data services first** (Phase 1), because the
> backend fail-fasts on boot if it can't reach the databases or run migrations.

---

## 2. Phase 1 — Provision the five data services

Do these in any order, but collect every value into your vault (§0.2).

### 1a. Neon — PostgreSQL + pgvector (embeddings) + Object Storage (files)

This one project provides **both** the vector store (step 1a) and the file
object storage (step 1e) — no separate storage account, no card.

1. Go to **neon.com** → **Sign up** → **Continue with Google**.
2. **Create project** (name: `prism`). Pick a region that also supports Object
   Storage: `us-east-2`, `us-east-1`, `eu-central-1`, or `ap-southeast-1`
   (choose the one nearest your HF Space). Postgres 15+. Note the project's
   **default branch name** (looks like `br-winter-pond-xxxx`) and **region** —
   you'll need both in step 1e.
3. On the project dashboard, open **Connection string** (a.k.a. "Connection
   Details"). Copy the **`postgresql://…?sslmode=require`** string.
4. Save it as **`POSTGRES_URL`**. It already contains the db name (often
   `neondb`) and `sslmode=require` — keep that query string.
5. Enable pgvector: open the **SQL Editor** and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   (The migration also runs this, but doing it now confirms your access.)
6. Create a **Neon API key** (needed to mint storage credentials in step 1e):
   **Profile → Account settings → API keys → Create API key** → save it as
   `NEON_API_KEY` in your vault (local only).

### 1b. Aiven — MySQL (users, documents, chunks, FULLTEXT, analytics)

1. Go to **aiven.io** → **Sign up** → **Google**.
2. **Create service** → **MySQL** → **Free plan** → a region near your Space →
   create. Wait until status is **Running** (~2–3 min).
3. Open the service → **Overview** → **Connection information**. Note:
   `Host`, `Port`, `User` (usually `avnadmin`), `Password`, `Database name`
   (usually `defaultdb`).
4. Assemble **`MYSQL_URL`**:
   ```
   mysql+pymysql://avnadmin:<PASSWORD>@<HOST>:<PORT>/defaultdb
   ```
   - The `mysql+pymysql://` prefix is fine — the backend parses host/port/user/
     password/db from the URL and ignores the scheme.
   - TLS is negotiated automatically (the MySQL connector uses SSL by default,
     which Aiven accepts). If a value contains special characters (`@`, `/`,
     `:`), URL-encode it.

### 1c. Neo4j AuraDB — topic graph (related documents / topics)

1. Go to **neo4j.com/cloud/aura** → **Start Free** → sign in with **Google**.
2. **Create instance** → **AuraDB Free**.
3. A **credentials panel appears ONCE** — **Download** it (or copy now). You get:
   - Connection URI: `neo4j+s://<id>.databases.neo4j.io` → **`NEO4J_URI`**
   - Username: `neo4j` → **`NEO4J_USER`**
   - Generated password → **`NEO4J_PASSWORD`**
4. Wait until the instance is **Running**.
   > The graph is optional-by-design: if Neo4j is paused/unreachable, uploads
   > still succeed and topic/related-docs just return empty. But set it up so
   > those features work.

### 1d. Upstash — Redis (search cache)

1. Go to **upstash.com** → **Sign up** → **Google**.
2. **Create Database** → **Redis** → a nearby region → **Create**.
3. On the database page, find the **Redis Connect** / connection details and copy
   the **`rediss://…`** (TLS) URL → **`REDIS_URL`**.
   - Must be `rediss://` (double-s = TLS), not `redis://`.

### 1e. Neon Object Storage — uploaded PDFs (same Neon project as 1a)

Neon has a built-in **S3-compatible** object store (5 GB free, **no card**, no
extra account). You create a bucket, then mint long-lived S3 credentials.

> Needs the **Neon CLI** and your `NEON_API_KEY` (from step 1a.6).

1. Install and authenticate the Neon CLI:
   ```bash
   npm i -g neonctl
   neonctl auth          # opens a browser; sign in with the same Google account
   ```
2. Create the bucket in your `prism` project:
   ```bash
   neonctl buckets create prism-documents
   # If your CLI version uses a different noun, see `neonctl buckets --help`.
   ```
   (The backend's startup bucket-check is best-effort; pre-creating here is what
   matters. A harmless "Could not initialize bucket" warning in the Space logs is
   fine as long as this bucket exists.)
3. Mint **long-lived** S3 credentials for the default branch (replace
   `{project_id}` and `{branch_id}` — find them with
   `neonctl projects list` and `neonctl branches list`):
   ```bash
   curl -X POST \
     "https://console.neon.tech/api/v2/projects/{project_id}/branches/{branch_id}/credentials" \
     -H "Authorization: Bearer $NEON_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"scopes": ["storage:read", "storage:write"]}'
   ```
   From the JSON response copy:
   - `token_id`             → **`S3_ACCESS_KEY`**
   - `s3_secret_access_key` → **`S3_SECRET_KEY`** (shown **once** — save it now)

   > These credentials don't expire (`expires_at` is `null` / unenforced), so
   > they're safe as static server keys. If one leaks, rotate with
   > `neonctl credentials rotate <token_id>` (keeps the same access key id).
4. Assemble the remaining values from your Neon branch (step 1a.2):
   - **`S3_ENDPOINT`** = `https://<branch>.storage.c-2.<region>.aws.neon.tech`
     (e.g. `https://br-winter-pond-aptw82ef.storage.c-2.us-east-2.aws.neon.tech`)
   - **`S3_REGION`** = your branch region (e.g. `us-east-2`)
   - **`S3_BUCKET`** = `prism-documents`

---

## 3. Phase 2 — Generate the app secret

Generate a strong JWT signing secret (≥ 32 chars). The backend **refuses to
boot in production** without a strong one.

```bash
openssl rand -hex 32
```

Save the output as **`JWT_SECRET`** in your vault. Also set **`PRISM_ENV=production`**
and **`CORS_STRICT=true`**.

---

## 4. Phase 3 — Deploy the backend to Hugging Face Spaces

The Space is its own git repo. We push the PRISM code to it, with the HF Docker
files promoted to the repo root (HF builds from a root `Dockerfile`).

### 4.1 Create the Space

1. Go to **huggingface.co** → **Sign Up** → **Continue with Google**.
2. Top-right **+ → New Space**:
   - **Owner**: your username
   - **Space name**: `prism-backend`
   - **SDK**: **Docker** → **Blank**
   - **Hardware**: **CPU basic (free)**
   - **Visibility**: Public (or Private — both free)
3. Create. Note the Space URL — it becomes
   `https://<username>-prism-backend.hf.space`.

### 4.2 Create an access token (to push)

**Settings → Access Tokens → Create new token** → type **Write** → copy it.
You'll use it as the password when git prompts for the HF remote.

### 4.3 Push the code with the Docker files at root

From your local PRISM clone:

```bash
# 1. Get a clean copy to push to HF (keeps your main clone untouched)
cd /path/to            # parent dir
git clone https://github.com/TahirSiddique092/prism.git prism-hf
cd prism-hf

# 2. Promote the HF Docker files to the repo root (HF builds from root Dockerfile)
cp deploy/huggingface/Dockerfile   ./Dockerfile
cp deploy/huggingface/README.md    ./README.md     # keep its YAML front-matter

# 3. Point this clone at the HF Space git remote and push
git remote remove origin
git remote add origin https://huggingface.co/spaces/<username>/prism-backend
git add Dockerfile README.md
git commit -m "HF Space: root Dockerfile + Space README"
git push --force origin main
#   Username: <your HF username>
#   Password: <the WRITE access token from 4.2>
```

> Why the copy: `deploy/huggingface/Dockerfile` uses repo-root-relative paths
> (`COPY backend …`, `COPY deploy/huggingface/entrypoint.sh …`), so it works as
> the root `Dockerfile` with the whole repo present. `README.md`'s front-matter
> (`sdk: docker`, `app_port: 7860`) tells HF how to build and route it.

### 4.4 Set the Space secrets

In the Space: **Settings → Variables and secrets → New secret**. Add **every**
line from the Backend block of your vault (§0.2):

```
PRISM_ENV, CORS_STRICT, JWT_SECRET,
POSTGRES_URL, MYSQL_URL, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, REDIS_URL,
S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET, S3_REGION
```

Leave `FRONTEND_URL` for now (you'll add it after Vercel in §6). Add all others
as **Secrets** (not public Variables), since they're credentials.

### 4.5 Watch the build & verify

- The Space rebuilds on push / on secret change. Open the **Logs** tab.
- First build is slow (installs torch + downloads the `all-MiniLM-L6-v2` model
  into the image). Expect several minutes.
- On boot the entrypoint **runs migrations then starts gunicorn**. If `JWT_SECRET`
  is weak/missing or a DB is unreachable, it **fail-fasts** — you'll see the
  error in the logs (this is intended; fix the secret/URL and it rebuilds).
- When healthy, verify:
  ```bash
  curl -f https://<username>-prism-backend.hf.space/health
  # {"status": "ok"}
  ```
- Confirm migrations applied (optional): the logs show `Running MySQL migration:`
  / `Running Postgres migration:` lines on first boot.

Record the Space URL as **`API_URL`** and **`NEXT_PUBLIC_API_URL`**.

---

## 5. Phase 4 — Deploy the frontend to Vercel

We use the **Vercel CLI with email login** so you don't need to connect GitHub.

```bash
cd /path/to/prism/frontend

# 1. Install + log in (choose "Continue with Email", enter your Google email)
npm i -g vercel
vercel login

# 2. Link a new project (accept defaults; framework auto-detected as Next.js)
vercel link        # scope: your account; create new project "prism"

# 3. Add the backend URL (server-only + public), for Production
vercel env add API_URL production
#   paste: https://<username>-prism-backend.hf.space
vercel env add NEXT_PUBLIC_API_URL production
#   paste: https://<username>-prism-backend.hf.space

# 4. Deploy to production
vercel --prod
```

- Because you run the CLI **from `frontend/`**, that directory is the project
  root and Next.js builds normally (no root-`vercel.json` gymnastics needed).
- When it finishes, the CLI prints your production URL,
  `https://<project>.vercel.app`. Save it as **`FRONTEND_URL`**.

> GitHub-integration alternative (optional): on vercel.com import the GitHub repo,
> set **Root Directory = `frontend`**, add the same two env vars. The committed
> root `vercel.json` also works for a repo-root import (it now has an
> `installCommand`). The CLI path above is simplest for a fresh account.

---

## 6. Phase 5 — Wire CORS back to the frontend

Now that you have the Vercel URL, lock the backend's CORS to it:

1. HF Space **Settings → Variables and secrets** → add:
   ```
   FRONTEND_URL = https://<project>.vercel.app
   ```
   (`CORS_STRICT=true` is already set, so the backend will trust **only** this
   origin — not the whole `*.vercel.app` space.)
2. The Space restarts. Verify CORS:
   ```bash
   # Allowed origin → 200 with ACAO header
   curl -i -H "Origin: https://<project>.vercel.app" \
     https://<username>-prism-backend.hf.space/health | grep -i access-control-allow-origin
   # Disallowed origin → 403
   curl -i -H "Origin: https://evil.example.com" \
     https://<username>-prism-backend.hf.space/health | head -1
   ```

> If you later add a custom domain or use Vercel **preview** URLs, add them to
> `CORS_ALLOWED_ORIGINS` (comma-separated) on the Space, or temporarily set
> `CORS_STRICT=false` to allow any `*.vercel.app` preview.

---

## 7. Phase 6 — End-to-end verification

On your live Vercel URL:

1. **Register** a user → you're redirected to `/dashboard`, logged in via an
   httpOnly cookie. Log out and back in.
2. **Upload** a PDF with a few topic tags → row appears as `processing`, then
   `ready` within a few seconds.
3. Open the document → the **inline PDF viewer loads** (HTTPS pre-signed Neon Object Storage URL),
   topic tags and related documents show.
4. **Search** a plain-English query → ranked snippets. Run the **same** query
   again → a **`cached`** badge appears (Redis hit).
5. **Analytics** → History, Top Documents (shows appearances + avg similarity),
   and Unsearched populate.

If all five pass, you're live. 🎉

---

## 8. Security checklist (confirm before sharing the URL)

- [ ] `PRISM_ENV=production` **and** a strong `JWT_SECRET` set on the Space
      (the app won't boot otherwise).
- [ ] `CORS_STRICT=true` **and** `FRONTEND_URL` set to your exact Vercel origin.
- [ ] All DB/storage credentials are **Secrets** on the Space, not public
      Variables, and are **not** committed anywhere in git.
- [ ] Frontend env has only `API_URL` / `NEXT_PUBLIC_API_URL` — **no** secrets.
- [ ] Backend URL is **https** (HF provides this) — so credentials/JWTs and the
      PDF viewer are never plaintext/mixed-content.
- [ ] 2FA enabled on the Google account and on each provider that offers it.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|--------|--------------|-----|
| Space build fails downloading the model | transient / rate limit | Re-run the build (Space → **Restart** / push again). |
| Space logs show `JWT_SECRET must be set…` and it won't start | missing/weak secret in prod | Set a 32+ char `JWT_SECRET` secret; it rebuilds. |
| Logs show migration/DB connection errors, container exits | wrong DB URL or DB not running | Re-check `MYSQL_URL`/`POSTGRES_URL`; ensure Aiven/Neon are **Running**; this fail-fast is intentional. |
| `curl /health` works but search 500s | pgvector/MySQL reachable but empty | Confirm migrations ran (logs) and that you uploaded a doc that reached `ready`. |
| MySQL connection refused / SSL error | Aiven requires TLS | The connector uses TLS by default; re-verify host/port/user/password/db parsed from the Aiven URI (URL-encode special chars). |
| PDF viewer blank | object URL not https / bucket mismatch | Ensure `S3_ENDPOINT` is the `https://br-…storage…aws.neon.tech` endpoint, `S3_REGION` matches the branch region, and `S3_BUCKET=prism-documents` exists. |
| Startup log: "Could not initialize MinIO bucket" | Neon Object Storage doesn't support S3 CreateBucket/HeadBucket | Harmless — the bucket was pre-created via `neonctl buckets create`; uploads/reads/pre-signing still work. |
| Frontend calls fail / CORS 403 | `FRONTEND_URL` missing or wrong on Space | Set `FRONTEND_URL` to the exact Vercel origin; with `CORS_STRICT=true` only that origin is allowed. |
| First request after idle is very slow | free Space slept (48h idle) | Expected cold start (~30–60s to reload the model). Data is safe (external DBs). |
| Related docs/topics always empty | AuraDB paused (3-day idle) or creds wrong | Resume the AuraDB instance; re-check `NEO4J_URI/USER/PASSWORD`. |
| `rediss` connection errors | used `redis://` not `rediss://` | Use the TLS URL from Upstash. |

---

## 10. Free-tier limits & ongoing maintenance

| Service | Free limit | Watch out for |
|---------|-----------|---------------|
| HF Space | 2 vCPU / 16 GB, sleeps after 48h idle | Cold starts; ephemeral disk (fine — all data is external) |
| Neon | ~1 GB storage, compute auto-suspends | Storage cap for many large PDFs' chunks |
| Aiven MySQL | 1 GB, single node | Storage cap |
| Neo4j AuraDB Free | 200k nodes / 400k rels; **pauses after 3 days idle**, **deleted after 30 days idle** | Visit periodically; keep creds to recreate |
| Upstash Redis | 256 MB, 500k commands/month | Command budget under heavy search |
| Neon Object Storage | 5 GB storage (shared Neon project) | Counts toward your Neon project; large PDFs add up alongside vectors |

**Routine upkeep:** hit the app at least every couple of days to keep AuraDB
awake; rotate `JWT_SECRET` if you suspect exposure (invalidates all sessions);
keep your credentials vault backed up.

---

## 11. Appendix — full environment variable reference

| Variable | Set where | Example / source |
|----------|-----------|------------------|
| `PRISM_ENV` | HF Space | `production` |
| `CORS_STRICT` | HF Space | `true` |
| `JWT_SECRET` | HF Space | `openssl rand -hex 32` |
| `FRONTEND_URL` | HF Space | `https://prism.vercel.app` (step 5) |
| `POSTGRES_URL` | HF Space | Neon connection string (`…?sslmode=require`) |
| `MYSQL_URL` | HF Space | `mysql+pymysql://avnadmin:…@…:…/defaultdb` (Aiven) |
| `NEO4J_URI` | HF Space | `neo4j+s://<id>.databases.neo4j.io` |
| `NEO4J_USER` / `NEO4J_PASSWORD` | HF Space | AuraDB credentials |
| `REDIS_URL` | HF Space | `rediss://…` (Upstash) |
| `S3_ENDPOINT` | HF Space | `https://br-<id>.storage.c-2.<region>.aws.neon.tech` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | HF Space | Neon credential `token_id` / `s3_secret_access_key` |
| `S3_BUCKET` | HF Space | `prism-documents` |
| `S3_REGION` | HF Space | Neon branch region, e.g. `us-east-2` |
| `API_URL` | Vercel | HF Space URL (server-only, preferred) |
| `NEXT_PUBLIC_API_URL` | Vercel | HF Space URL (compatibility) |

> Legacy `MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY` still work as fallbacks for the
> `S3_*` names (used by local docker-compose dev). In production use `S3_*`.
