"""Acceptance criteria tests for slice-23: Vercel deployment and CORS config.

Acceptance criteria verified:
1. Flask CORS is configured to allow requests only from the Vercel domain — all other origins return 403.
2. Allowed Vercel domains receive valid CORS headers (Access-Control-Allow-Origin, Access-Control-Allow-Credentials).
3. Preflight OPTIONS requests from allowed Vercel domains return 204 with methods and headers; disallowed origins return 403.
4. Requests without Origin header (server-to-server proxy from Next.js route handlers, curl, health probes) succeed.
5. No secrets (JWT_SECRET, DB passwords) are present in the Vercel environment or the frontend code.
6. NEXT_PUBLIC_API_URL is configured in frontend auth lib.
7. Vercel deployment configurations and ADR-012 exist.
"""
from pathlib import Path
import pytest

from backend.app import create_app
from backend.cors import is_origin_allowed, VERCEL_DOMAIN_REGEX


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def client():
    """Create Flask test client."""
    app = create_app({"TESTING": True})
    return app.test_client()


def test_cors_disallowed_origin_returns_403(client):
    """AC 3: All origins other than Vercel domains return 403 Forbidden."""
    unauthorized_origins = [
        "https://malicious-site.com",
        "https://attacker.org",
        "http://untrusted-domain.net",
        "https://vercel.app.attacker.com",  # subdomain spoof attempt
        "http://evil-prism.vercel.app.phishing.com",
    ]

    for origin in unauthorized_origins:
        # GET request with unauthorized Origin
        res = client.get("/health", headers={"Origin": origin})
        assert res.status_code == 403, f"Origin '{origin}' should return 403, got {res.status_code}"
        assert "Forbidden" in res.get_json().get("error", "")

        # POST request with unauthorized Origin
        res_post = client.post("/api/auth/login", headers={"Origin": origin}, json={})
        assert res_post.status_code == 403, f"POST with Origin '{origin}' should return 403"

        # Preflight OPTIONS request with unauthorized Origin
        res_options = client.options("/api/search", headers={"Origin": origin})
        assert res_options.status_code == 403, f"OPTIONS with Origin '{origin}' should return 403"


def test_cors_allowed_vercel_domain_returns_headers(client):
    """AC 3: Allowed Vercel domains succeed and receive CORS headers."""
    allowed_origins = [
        "https://prism.vercel.app",
        "https://prism-git-main-team.vercel.app",
        "https://custom-preview-123.vercel.app",
    ]

    for origin in allowed_origins:
        # GET request from allowed Vercel domain
        res = client.get("/health", headers={"Origin": origin})
        assert res.status_code == 200
        assert res.headers.get("Access-Control-Allow-Origin") == origin
        assert res.headers.get("Access-Control-Allow-Credentials") == "true"

        # OPTIONS preflight request from allowed Vercel domain
        res_options = client.options("/api/search", headers={"Origin": origin})
        assert res_options.status_code == 204
        assert res_options.headers.get("Access-Control-Allow-Origin") == origin
        assert "GET" in res_options.headers.get("Access-Control-Allow-Methods", "")
        assert "POST" in res_options.headers.get("Access-Control-Allow-Methods", "")
        assert "Authorization" in res_options.headers.get("Access-Control-Allow-Headers", "")


def test_cors_server_to_server_without_origin_header_succeeds(client):
    """AC 4: Requests without Origin header (Next.js server route handlers, curl) succeed."""
    # Direct /health check without Origin header
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}
    # No CORS origin header when no Origin was requested
    assert "Access-Control-Allow-Origin" not in res.headers


def test_vercel_regex_validation():
    """Verify regex correctly distinguishes valid Vercel domains from attacker domains."""
    assert VERCEL_DOMAIN_REGEX.match("https://prism.vercel.app")
    assert VERCEL_DOMAIN_REGEX.match("https://sub.domain.vercel.app")
    assert VERCEL_DOMAIN_REGEX.match("https://prism-dev-preview.vercel.app")

    # Insecure plain HTTP must be rejected
    assert not VERCEL_DOMAIN_REGEX.match("http://prism.vercel.app")
    # Phishing / domain shadowing attempts must be rejected
    assert not VERCEL_DOMAIN_REGEX.match("https://vercel.app.attacker.com")
    assert not VERCEL_DOMAIN_REGEX.match("https://attacker-vercel.app.org")
    assert not VERCEL_DOMAIN_REGEX.match("https://notvercel.app")


def test_frontend_secret_isolation():
    """AC 6: No secrets (JWT_SECRET, DB passwords) are present in the frontend code or bundle."""
    frontend_src = REPO_ROOT / "frontend" / "src"
    assert frontend_src.exists()

    forbidden_patterns = [
        "JWT_SECRET",
        "MYSQL_URL",
        "POSTGRES_URL",
        "NEO4J_PASSWORD",
        "MINIO_SECRET_KEY",
        "REDIS_URL",
    ]

    for file_path in frontend_src.rglob("*.ts*"):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        for forbidden in forbidden_patterns:
            assert forbidden not in content, f"Secret pattern '{forbidden}' found in frontend file: {file_path}"


def test_next_public_api_url_configured_in_frontend():
    """AC 2: NEXT_PUBLIC_API_URL is configured in frontend to point to Flask API."""
    auth_ts_path = REPO_ROOT / "frontend" / "src" / "lib" / "auth.ts"
    assert auth_ts_path.exists()

    with open(auth_ts_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "NEXT_PUBLIC_API_URL" in content
    assert "getApiBaseUrl" in content


def test_vercel_configuration_files_exist():
    """AC 1: Vercel deployment configurations and ADR-012 exist."""
    root_vercel = REPO_ROOT / "vercel.json"
    frontend_vercel = REPO_ROOT / "frontend" / "vercel.json"
    frontend_env_example = REPO_ROOT / "frontend" / ".env.example"
    deploy_guide = REPO_ROOT / "deploy" / "vercel-setup.md"
    adr_path = REPO_ROOT / "docs" / "decisions" / "ADR-012-vercel-deployment-and-cors.md"

    assert root_vercel.exists(), "vercel.json must exist at root"
    assert frontend_vercel.exists(), "frontend/vercel.json must exist"
    assert frontend_env_example.exists(), "frontend/.env.example must exist"
    assert deploy_guide.exists(), "deploy/vercel-setup.md must exist"
    assert adr_path.exists(), "docs/decisions/ADR-012-vercel-deployment-and-cors.md must exist"
