# slice-22 — OCI VM deployment and environment setup

**Sprint:** 6 — Polish and deployment
**Module:** infra

## What to build

Deploy the Flask backend and all services (MySQL, pgvector, Neo4j, Redis, MinIO) to an OCI VM using Docker Compose. Expose the Flask API on a public port.

## Acceptance criteria

- `docker-compose up -d` on the OCI VM starts all services cleanly
- Flask API is reachable at `http://<OCI_PUBLIC_IP>:5000/health` and returns `{ "status": "ok" }`
- All env variables are set via a `.env` file on the VM — never committed to the repo
- MySQL, pgvector, Neo4j, Redis, and MinIO are all running and healthy (`docker ps` shows no restarts)
- Migrations from slice-02 have been run against the live MySQL instance
- Neo4j memory cap set to 2GB in `docker-compose.yml` to avoid OOM on the VM

## Human review required

This slice touches infra config and environment variables — do not merge without human sign-off.

## Out of scope

- No HTTPS/TLS on the backend in v1 — that's a post-submission improvement
- No process manager (systemd, supervisor) — Docker Compose restart policies are sufficient

## Assigned To

Dev A
