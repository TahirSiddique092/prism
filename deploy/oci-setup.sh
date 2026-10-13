#!/bin/bash
# PRISM - OCI VM Deployment and Environment Setup Script (Slice 22)
# Usage: ./deploy/oci-setup.sh
set -e

echo "=========================================================="
echo "      PRISM — OCI VM Deployment & Environment Setup       "
echo "=========================================================="

# Check for Docker and Docker Compose
if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker "$USER" || true
    rm -f get-docker.sh
    echo "Docker installed."
fi

# Detect docker compose plugin or standalone docker-compose
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "Docker Compose not found. Installing docker compose plugin..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin || true
    DOCKER_COMPOSE="docker compose"
fi

# Setup .env file on the VM if not already present
if [ ! -f .env ]; then
    echo "Creating .env configuration file from template..."
    JWT_SECRET_RANDOM=$(openssl rand -hex 32 2>/dev/null || date +%s%N | sha256sum | head -c 64)
    cat <<EOF > .env
# PRISM Production Environment Configuration (OCI VM)
# Generated on $(date)

# Container Database Credentials and URLs
MYSQL_ROOT_PASSWORD=root
MYSQL_DATABASE=prism
MYSQL_USER=user
MYSQL_PASSWORD=password
MYSQL_URL=mysql+pymysql://user:password@mysql:3306/prism

POSTGRES_DB=prism
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_URL=postgresql://user:password@postgres:5432/prism

NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

REDIS_URL=redis://redis:6379/0

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Application Secrets
JWT_SECRET=${JWT_SECRET_RANDOM}
PORT=5000
EOF
    echo ".env created with generated JWT_SECRET. Customize database passwords if needed."
else
    echo ".env file already exists; preserving existing configuration."
fi

# Configure host OS firewall for port 5000 if iptables or ufw is active
echo "Configuring OS firewall for port 5000..."
if command -v ufw >/dev/null 2>&1 && sudo ufw status | grep -q "Status: active"; then
    echo "Allowing port 5000 in UFW..."
    sudo ufw allow 5000/tcp || true
elif command -v iptables >/dev/null 2>&1; then
    # OCI Ubuntu/Oracle Linux images often enforce iptables rules blocking non-standard ports
    echo "Ensuring iptables allows incoming TCP on port 5000..."
    sudo iptables -C INPUT -p tcp --dport 5000 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 6 -p tcp --dport 5000 -j ACCEPT 2>/dev/null || true
fi

# Build and start all services using Docker Compose
echo "Starting all PRISM services via Docker Compose..."
$DOCKER_COMPOSE up -d --build

echo "Waiting for services to become healthy..."
sleep 10

# Verify containers
echo "=== Container Status ==="
$DOCKER_COMPOSE ps

# Test Flask health endpoint
echo "=== Testing Flask Health Endpoint ==="
for i in {1..12}; do
    if curl -s -f http://localhost:5000/health >/dev/null 2>&1; then
        RESPONSE=$(curl -s http://localhost:5000/health)
        echo "Health check succeeded: $RESPONSE"
        break
    fi
    echo "Waiting for Flask API to become ready ($i/12)..."
    sleep 5
done

PUBLIC_IP=$(curl -s -m 5 https://ifconfig.me 2>/dev/null || curl -s -m 5 https://api.ipify.org 2>/dev/null || echo "<OCI_PUBLIC_IP>")
echo "=========================================================="
echo "PRISM Backend successfully deployed!"
echo "API Public URL: http://${PUBLIC_IP}:5000/health"
echo "IMPORTANT: In the OCI Console, make sure an Ingress Rule"
echo "is configured in your VCN Security List allowing:"
echo "  - Source CIDR: 0.0.0.0/0"
echo "  - IP Protocol: TCP"
echo "  - Destination Port: 5000"
echo "=========================================================="
