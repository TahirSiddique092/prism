# PRISM OCI VM Deployment Guide (Slice 22)

> **⚠️ Historical.** PRISM is not deployed to the cloud — it runs **locally via
> `docker compose up`** (see the root [`README.md`](../README.md) and
> [`ADR-014`](../docs/decisions/ADR-014-local-only-docker-compose.md)). This
> OCI guide is kept only for historical reference; the `docker-compose.yml`
> steps below still describe the local stack.

This guide documents deploying the PRISM backend (Flask REST API, MySQL 8, pgvector/PostgreSQL 15, Neo4j 5, Redis 7, and MinIO) to an Oracle Cloud Infrastructure (OCI) Compute Virtual Machine using Docker Compose.

---

## 1. Prerequisites on OCI

1. **OCI Compute Instance:**
   - Image: Ubuntu 22.04 LTS / 24.04 LTS or Oracle Linux 8 / 9.
   - Shape: VM.Standard.A1.Flex (Ampere, e.g., 2–4 OCPUs, 12–24 GB RAM) or VM.Standard.E4.Flex (AMD).
   - Public IP address assigned.

2. **OCI VCN Ingress Rules (Security List):**
   In the OCI Console:
   - Navigate to **Networking** > **Virtual Cloud Networks** > Select your VCN > **Security Lists** > **Default Security List**.
   - Click **Add Ingress Rules**:
     - **Source Type:** CIDR
     - **Source CIDR:** `0.0.0.0/0`
     - **IP Protocol:** TCP
     - **Destination Port Range:** `5000`
     - **Description:** Allow PRISM Flask REST API
   - Note: Keep database ports (3306, 5432, 7474, 7687, 6379, 9000, 9001) internal or protected; only port `5000` is exposed publicly for the API.

---

## 2. Deploying on the VM

SSH into your OCI VM:
```bash
ssh -i /path/to/private_key ubuntu@<OCI_PUBLIC_IP>
```

Clone the repository and enter directory:
```bash
git clone <REPO_URL> prism
cd prism
```

Run the automated setup script:
```bash
./deploy/oci-setup.sh
```

Or run manually:

1. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your production secrets (JWT_SECRET, secure passwords)
   # Ensure hostnames point to compose services:
   # MYSQL_URL=mysql+pymysql://user:password@mysql:3306/prism
   # POSTGRES_URL=postgresql://user:password@postgres:5432/prism
   # NEO4J_URI=bolt://neo4j:7687
   # REDIS_URL=redis://redis:6379/0
   # MINIO_ENDPOINT=minio:9000
   ```

2. **Configure Host OS Firewall (iptables / ufw):**
   OCI images often enforce default host firewall rules. Allow port 5000:
   ```bash
   sudo iptables -I INPUT 6 -p tcp --dport 5000 -j ACCEPT
   # Or with UFW:
   sudo ufw allow 5000/tcp
   ```

3. **Start All Services with Docker Compose:**
   ```bash
   docker compose up -d --build
   ```

4. **Verify Running Containers:**
   ```bash
   docker compose ps
   ```
   All containers (`mysql`, `postgres`, `neo4j`, `redis`, `minio`, `backend`) should show as running with no abnormal restarts.

5. **Verify API Health:**
   ```bash
   curl -f http://localhost:5000/health
   # From your local machine:
   curl -f http://<OCI_PUBLIC_IP>:5000/health
   ```
   Returns: `{"status": "ok"}`

---

## 3. Database Migrations

Migrations from `backend/db/migrations/` (`001_init.sql` through `004_index_tuning.sql`) are automatically applied against live MySQL and pgvector on backend container startup via `backend/entrypoint.sh`.

To manually trigger or inspect migrations:
```bash
docker compose exec backend python backend/db/migrate.py
```

---

## 4. Neo4j Memory Cap

In `docker-compose.yml`, Neo4j is configured with:
- `NEO4J_server_memory_heap_initial__size: 512m`
- `NEO4J_server_memory_heap_max__size: 1G`
- `NEO4J_server_memory_pagecache_size: 1G`
- `mem_limit: 2g`

This prevents Neo4j from exceeding 2GB RAM on the VM and avoids Out-Of-Memory (OOM) crashes.
