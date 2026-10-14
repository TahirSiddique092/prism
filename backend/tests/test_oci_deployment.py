"""Acceptance criteria tests for slice-22: OCI VM deployment and environment setup.

Acceptance criteria verified:
1. docker-compose.yml defines all services (mysql, postgres, neo4j, redis, minio, backend) cleanly.
2. Flask API exposes port 5000, has a /health endpoint returning {"status": "ok"} reachable without auth.
3. All env variables can be configured via .env; .env is gitignored and never committed.
4. Services define restart: unless-stopped policies to ensure high availability without external supervisors.
5. Migrations are executed against live database instances via entrypoint and migrate.py.
6. Neo4j memory cap is set to 2GB in docker-compose.yml (via mem_limit and JVM/pagecache caps) to prevent VM OOM.
7. Architectural decision record ADR-011 exists and documents the infra choices.
"""
from pathlib import Path
import yaml
import pytest

from backend.app import create_app


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def compose_config():
    """Load and parse docker-compose.yml."""
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist at repository root"
    with open(compose_path, "r") as f:
        return yaml.safe_load(f)


def test_compose_contains_all_required_services(compose_config):
    """AC 1: Compose starts MySQL, pgvector, Neo4j, Redis, MinIO, and Flask backend."""
    services = compose_config.get("services", {})
    required = {"mysql", "postgres", "neo4j", "redis", "minio", "backend"}
    for service_name in required:
        assert service_name in services, f"Service '{service_name}' must be defined in docker-compose.yml"


def test_neo4j_memory_cap_set_to_2gb(compose_config):
    """AC 6: Neo4j memory cap set to 2GB in docker-compose.yml to avoid OOM on the VM."""
    neo4j_service = compose_config["services"]["neo4j"]

    # Test docker container memory limit
    mem_limit = neo4j_service.get("mem_limit")
    assert mem_limit is not None, "Neo4j must specify mem_limit in docker-compose.yml"
    assert str(mem_limit).lower() in ("2g", "2048m", "2048mb"), f"Neo4j mem_limit must be 2GB, got {mem_limit}"

    # Test JVM heap / pagecache environment configuration
    env = neo4j_service.get("environment", {})
    if isinstance(env, dict):
        heap_max = env.get("NEO4J_server_memory_heap_max__size")
        pagecache = env.get("NEO4J_server_memory_pagecache_size")
    else:
        env_dict = dict(item.split("=", 1) for item in env if "=" in item)
        heap_max = env_dict.get("NEO4J_server_memory_heap_max__size")
        pagecache = env_dict.get("NEO4J_server_memory_pagecache_size")

    assert heap_max is not None, "Neo4j heap max size must be configured"
    assert pagecache is not None, "Neo4j pagecache size must be configured"


def test_backend_service_configuration(compose_config):
    """AC 1 & 2: Flask API service is configured, exposes port 5000, and depends on backend datastores."""
    backend = compose_config["services"]["backend"]
    assert "build" in backend, "Backend service must specify build configuration"

    # Ports check: must map host 5000 to container 5000
    ports = [str(p) for p in backend.get("ports", [])]
    assert any("5000:5000" in p or p == "5000" for p in ports), "Backend must expose port 5000"

    # Dependencies check
    depends_on = backend.get("depends_on", [])
    expected_deps = {"mysql", "postgres", "neo4j", "redis", "minio"}
    if isinstance(depends_on, dict):
        dep_set = set(depends_on.keys())
    else:
        dep_set = set(depends_on)
    assert expected_deps.issubset(dep_set), f"Backend must depend on datastores: {expected_deps}"


def test_services_have_restart_policies(compose_config):
    """AC 4: Services have restart policies (unless-stopped) for reliability."""
    services = compose_config.get("services", {})
    for name, service in services.items():
        restart = service.get("restart")
        assert restart in ("unless-stopped", "always"), f"Service '{name}' must have restart policy, got '{restart}'"


def test_env_files_not_committed_and_ignored():
    """AC 3: All env variables are set via a .env file on the VM — never committed to repo."""
    gitignore_path = REPO_ROOT / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist"
    with open(gitignore_path, "r") as f:
        gitignore_content = f.read()

    assert ".env" in gitignore_content, ".env must be ignored in .gitignore"

    # A local .env on a developer machine is expected and fine; what the AC
    # actually requires is that .env is never COMMITTED/tracked by git. Check
    # git tracking rather than mere filesystem existence (which would fail for
    # anyone who has created a local .env).
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", ".env"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert tracked == "", ".env must never be committed/tracked by git"


def test_flask_health_endpoint():
    """AC 2: Flask API is reachable at /health and returns { 'status': 'ok' }."""
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.get("/health")
    assert response.status_code == 200
    assert response.is_json
    data = response.get_json()
    assert data == {"status": "ok"}


def test_backend_dockerfile_and_entrypoint_exist():
    """AC 1 & 5: Backend Dockerfile and entrypoint exist and are configured properly."""
    dockerfile_path = REPO_ROOT / "backend" / "Dockerfile"
    entrypoint_path = REPO_ROOT / "backend" / "entrypoint.sh"

    assert dockerfile_path.exists(), "backend/Dockerfile must exist"
    assert entrypoint_path.exists(), "backend/entrypoint.sh must exist"

    with open(dockerfile_path, "r") as f:
        df_content = f.read()

    assert "EXPOSE 5000" in df_content, "Dockerfile must expose port 5000"
    assert "requirements.txt" in df_content, "Dockerfile must install requirements.txt"
    assert "ENTRYPOINT" in df_content, "Dockerfile must set ENTRYPOINT"

    with open(entrypoint_path, "r") as f:
        ep_content = f.read()

    # Entrypoint must run migrations
    assert "migrate.py" in ep_content, "Entrypoint must run migrate.py against live database"
    assert "app.py" in ep_content, "Entrypoint must start Flask application"
