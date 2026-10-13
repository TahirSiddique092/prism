#!/bin/bash
set -e

echo "=== PRISM Backend Starting ==="

# Automatic container hostname mapping:
# If running inside Docker and configuration still points to localhost,
# redirect to the compose service hostnames so container networking works seamlessly.
if [ -f /.dockerenv ]; then
    if [ "$MYSQL_URL" = "mysql+pymysql://user:password@localhost:3306/prism" ]; then
        echo "Detected localhost in MYSQL_URL inside container; mapping to mysql hostname"
        export MYSQL_URL="mysql+pymysql://user:password@mysql:3306/prism"
    fi
    if [ "$POSTGRES_URL" = "postgresql://user:password@localhost:5432/prism" ]; then
        echo "Detected localhost in POSTGRES_URL inside container; mapping to postgres hostname"
        export POSTGRES_URL="postgresql://user:password@postgres:5432/prism"
    fi
    if [ "$NEO4J_URI" = "bolt://localhost:7687" ]; then
        echo "Detected localhost in NEO4J_URI inside container; mapping to neo4j hostname"
        export NEO4J_URI="bolt://neo4j:7687"
    fi
    if [ "$REDIS_URL" = "redis://localhost:6379/0" ]; then
        echo "Detected localhost in REDIS_URL inside container; mapping to redis hostname"
        export REDIS_URL="redis://redis:6379/0"
    fi
    if [ "$MINIO_ENDPOINT" = "localhost:9000" ]; then
        echo "Detected localhost in MINIO_ENDPOINT inside container; mapping to minio hostname"
        export MINIO_ENDPOINT="minio:9000"
    fi
fi

# Function to wait for a service port to become reachable
wait_for_service() {
    local host=$1
    local port=$2
    local name=$3
    local max_retries=${4:-30}
    local count=0

    echo "Waiting for $name at $host:$port..."
    while ! nc -z "$host" "$port" 2>/dev/null; do
        count=$((count + 1))
        if [ "$count" -ge "$max_retries" ]; then
            echo "Timeout waiting for $name at $host:$port (continuing anyway)"
            return 0
        fi
        sleep 1
    done
    echo "$name is reachable!"
}

# Extract host & port for MySQL from MYSQL_URL or environment
MYSQL_HOST="${MYSQL_HOST:-mysql}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
if [[ "$MYSQL_URL" =~ @([^:/]+):?([0-9]+)?/ ]]; then
    MYSQL_HOST="${BASH_REMATCH[1]}"
    if [ -n "${BASH_REMATCH[2]}" ]; then
        MYSQL_PORT="${BASH_REMATCH[2]}"
    fi
fi

# Extract host & port for Postgres from POSTGRES_URL or environment
PG_HOST="${PG_HOST:-postgres}"
PG_PORT="${PG_PORT:-5432}"
if [[ "$POSTGRES_URL" =~ @([^:/]+):?([0-9]+)?/ ]]; then
    PG_HOST="${BASH_REMATCH[1]}"
    if [ -n "${BASH_REMATCH[2]}" ]; then
        PG_PORT="${BASH_REMATCH[2]}"
    fi
fi

# Wait for databases to be ready before running migrations
wait_for_service "$MYSQL_HOST" "$MYSQL_PORT" "MySQL" 30
wait_for_service "$PG_HOST" "$PG_PORT" "PostgreSQL" 30

# Apply all database migrations against live MySQL and pgvector instances
echo "Applying database migrations..."
python /app/backend/db/migrate.py || python -m backend.db.migrate || echo "Warning: Migration runner completed with warnings"

# If arguments were provided to docker run/exec, execute them instead of default server
if [ "$#" -gt 0 ]; then
    echo "Executing command: $@"
    exec "$@"
fi

echo "Starting Flask API server on port ${PORT:-5000}..."
exec python /app/backend/app.py
