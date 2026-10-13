# ADR-011 — OCI VM deployment and environment setup (slice-22)

## Context

PRISM's backend comprises a Flask REST API and five backing datastores / services:
1. MySQL 8.0 (relational metadata, audit logs, fulltext search)
2. PostgreSQL 15 with `pgvector` extension (vector similarity search)
3. Neo4j 5 (topic graph and related document retrieval)
4. Redis 7 (search result caching)
5. MinIO (S3-compatible raw PDF storage)

For production deployment (Sprint 6, Slice 22), all services and the Flask application are hosted on an Oracle Cloud Infrastructure (OCI) Compute Virtual Machine using Docker Compose. The VM has limited RAM and resources, requiring explicit memory boundaries, automated migration execution on startup, and secure environment configuration.

## Decisions

1. **Multi-Service Docker Compose Architecture**
   - The Flask backend is containerized via `backend/Dockerfile` using `python:3.11-slim` and added to `docker-compose.yml` as the `backend` service.
   - `ports: ["5000:5000"]` binds port 5000 on the host VM so the Flask API is publicly reachable at `http://<OCI_PUBLIC_IP>:5000/health`.
   - Datastore containers (`mysql`, `postgres`, `neo4j`, `redis`, `minio`) communicate with the Flask app over the default Docker bridge network using container service names (`mysql:3306`, `postgres:5432`, `neo4j:7687`, `redis:6379`, `minio:9000`).

2. **Neo4j 2GB Memory Cap**
   - To avoid Out-Of-Memory (OOM) kills on the OCI VM, Neo4j is strictly capped at 2GB in `docker-compose.yml` using two complementary mechanisms:
     - JVM heap and pagecache configuration via environment variables:
       - `NEO4J_server_memory_heap_initial__size: 512m`
       - `NEO4J_server_memory_heap_max__size: 1G`
       - `NEO4J_server_memory_pagecache_size: 1G`
     - Docker cgroup constraint: `mem_limit: 2g`.
   - This caps internal Neo4j memory usage while preventing container memory spikes from starving MySQL, pgvector, or Flask.

3. **Restart Policies in Docker Compose**
   - All services in `docker-compose.yml` specify `restart: unless-stopped`.
   - In accordance with the slice scope, no external process manager (e.g. systemd or supervisor) is introduced; Docker Compose restart policies provide crash resilience.

4. **Automated, Idempotent Migrations on Startup**
   - `backend/entrypoint.sh` runs before starting the Flask server. It checks database readiness, then executes `backend/db/migrate.py`.
   - `backend/db/migrate.py` introduces a `schema_migrations` tracking table in both MySQL and Postgres.
   - Already-applied migrations are tracked and skipped on subsequent runs, and duplicate DDL errors (such as pre-existing tables or columns) are gracefully handled. This guarantees that all DDL scripts (from `001_init.sql` through `004_index_tuning.sql`) execute cleanly on initial boot and without error on container restart.

5. **Pre-downloaded ML Models and Tokenizers in Docker Image**
   - The `sentence-transformers/all-MiniLM-L6-v2` weights and NLTK `punkt`/`punkt_tab` tokenizers are pre-downloaded during Docker image build (`RUN python -c ...`).
   - This eliminates cold-start latency and avoids runtime dependency on HuggingFace / NLTK external endpoints during container startup.

6. **Environment Variable Security**
   - All secrets, database passwords, and JWT keys are configured via a `.env` file on the VM.
   - `.env` is ignored by `.gitignore` and is never committed to source control.
   - `docker-compose.yml` uses `${VAR:-default}` interpolation to consume `.env` values dynamically.

## Out of Scope

- HTTPS/TLS on the backend in v1 (reserved for post-submission improvements; v1 communicates over HTTP on port 5000).
- External process managers (systemd/supervisord); Docker Compose restart policies handle process lifecycle.
- Vercel frontend deployment and CORS configuration (assigned to slice-23).

## Status

Accepted.
