"""Acceptance criteria tests for slice-04: Auth — JWT middleware and logout.

Acceptance criteria verified:
1. @require_auth decorator extracts and verifies the token from Authorization: Bearer <token> header
2. Verified user_id is injected into the request context so any route can access it via g.user_id
3. Missing or invalid token returns 401
4. Expired token returns 401 with message "token expired"
5. POST /api/auth/logout returns 200 with { message: "logged out" } — stateless, client discards token
6. All routes except /api/auth/register and /api/auth/login are protected by default
"""
import datetime
import time
from unittest.mock import patch
from flask import Flask, g, jsonify
import jwt
import pytest

from backend.app import create_app
from backend.modules.auth.middleware import (
    extract_bearer_token,
    public_route,
    require_auth,
)
from backend.modules.auth.service import (
    decode_token,
    generate_token,
    get_jwt_secret,
)


@pytest.fixture
def app():
    """Create a test application with PRISM blueprints and auth middleware."""
    test_app = create_app({"TESTING": True})
    return test_app


@pytest.fixture
def client(app):
    """Test client."""
    return app.test_client()


@pytest.fixture
def valid_token():
    """Provide a valid signed JWT for testing."""
    return generate_token(user_id=42, email="tester@example.com")


@pytest.fixture
def auth_headers(valid_token):
    """Provide valid authorization headers."""
    return {"Authorization": f"Bearer {valid_token}"}


class TestAcceptanceCriterion1ExtractAndVerifyToken:
    """AC 1: @require_auth decorator extracts and verifies the token from Authorization: Bearer <token> header."""

    def test_extract_bearer_token_valid(self):
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDcSemACt8x4iTMCda8Yhe3iZaWbvV5XKSTbuAn0M"
        assert extract_bearer_token(f"Bearer {token}") == token
        assert extract_bearer_token(f"bearer {token}") == token
        assert extract_bearer_token(f"BEARER {token}") == token
        assert extract_bearer_token(f"  Bearer   {token}  ") == token

    def test_extract_bearer_token_invalid_formats(self):
        assert extract_bearer_token(None) is None
        assert extract_bearer_token("") is None
        assert extract_bearer_token("Bearer") is None
        assert extract_bearer_token("Bearer    ") is None
        assert extract_bearer_token("Basic dXNlcjpwYXNz") is None
        assert extract_bearer_token("Token some-token") is None
        assert extract_bearer_token("Bearer part1 part2") is None

    def test_require_auth_decorator_on_custom_endpoint(self, app, client, valid_token):
        @app.route("/api/test-decorator-endpoint")
        @require_auth
        def test_endpoint():
            return jsonify({"status": "authenticated", "user_id": g.user_id})

        # Request with valid Authorization: Bearer <token>
        res = client.get(
            "/api/test-decorator-endpoint",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "authenticated"
        assert data["user_id"] == 42


class TestAcceptanceCriterion2UserIdInjection:
    """AC 2: Verified user_id is injected into the request context so any route can access it via g.user_id."""

    def test_user_id_injected_into_flask_g(self, app, client):
        @app.route("/api/test-g-context")
        @require_auth
        def context_endpoint():
            # Any route can access g.user_id
            return jsonify({
                "has_user_id": hasattr(g, "user_id"),
                "user_id": g.user_id,
                "user_id_type": type(g.user_id).__name__,
            })

        token_user_99 = generate_token(user_id=99, email="user99@prism.test")
        res = client.get(
            "/api/test-g-context",
            headers={"Authorization": f"Bearer {token_user_99}"},
        )

        assert res.status_code == 200
        data = res.get_json()
        assert data["has_user_id"] is True
        assert data["user_id"] == 99
        assert data["user_id_type"] == "int"


class TestAcceptanceCriterion3MissingOrInvalidToken:
    """AC 3: Missing or invalid token returns 401."""

    def test_missing_token_returns_401(self, client):
        res = client.post("/api/auth/logout")
        assert res.status_code == 401
        assert "error" in res.get_json() or "message" in res.get_json()

    def test_empty_authorization_header_returns_401(self, client):
        res = client.post("/api/auth/logout", headers={"Authorization": ""})
        assert res.status_code == 401

    def test_non_bearer_scheme_returns_401(self, client):
        res = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Basic dXNlcjpwYXNzd29yZA=="},
        )
        assert res.status_code == 401

    def test_bearer_without_token_returns_401(self, client):
        res = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer "},
        )
        assert res.status_code == 401

    def test_malformed_token_string_returns_401(self, client):
        res = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer not-a-valid-jwt-token"},
        )
        assert res.status_code == 401

    def test_token_with_invalid_signature_returns_401(self, client):
        tampered_token = jwt.encode(
            {"user_id": 1, "email": "evil@prism.test", "exp": int(time.time()) + 3600},
            "totally-wrong-secret-key-different-from-env",
            algorithm="HS256",
        )
        res = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        assert res.status_code == 401

    def test_token_missing_user_id_claim_returns_401(self, client):
        token_no_user_id = jwt.encode(
            {"email": "nouser@prism.test", "exp": int(time.time()) + 3600},
            get_jwt_secret(),
            algorithm="HS256",
        )
        res = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token_no_user_id}"},
        )
        assert res.status_code == 401


class TestAcceptanceCriterion4ExpiredToken:
    """AC 4: Expired token returns 401 with message 'token expired'."""

    def test_expired_token_returns_401_with_message_token_expired(self, client):
        # Generate token expired 1 minute ago
        expired_token = generate_token(
            user_id=12,
            email="expired@prism.test",
            expires_in=datetime.timedelta(seconds=-60),
        )

        res = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert res.status_code == 401
        data = res.get_json()
        assert data.get("message") == "token expired" or data.get("error") == "token expired"
        assert "token expired" in res.get_data(as_text=True)

    def test_expired_token_on_any_protected_route_returns_token_expired_message(self, app, client):
        @app.route("/api/test-expired-route")
        def protected_route():
            return jsonify({"status": "ok"})

        expired_token = generate_token(
            user_id=77,
            email="exp77@prism.test",
            expires_in=datetime.timedelta(seconds=-10),
        )

        res = client.get(
            "/api/test-expired-route",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert res.status_code == 401
        data = res.get_json()
        assert data.get("message") == "token expired" or data.get("error") == "token expired"


class TestAcceptanceCriterion5Logout:
    """AC 5: POST /api/auth/logout returns 200 with { message: 'logged out' } — stateless, client discards token."""

    def test_logout_with_valid_token_returns_200_and_message(self, client, auth_headers):
        res = client.post("/api/auth/logout", headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data == {"message": "logged out"}

    def test_logout_is_stateless(self, client, auth_headers):
        # Multiple calls succeed because backend does not maintain server session state
        res1 = client.post("/api/auth/logout", headers=auth_headers)
        assert res1.status_code == 200
        assert res1.get_json() == {"message": "logged out"}

        res2 = client.post("/api/auth/logout", headers=auth_headers)
        assert res2.status_code == 200
        assert res2.get_json() == {"message": "logged out"}

    def test_logout_requires_post_method(self, client, auth_headers):
        res = client.get("/api/auth/logout", headers=auth_headers)
        assert res.status_code == 405


class TestAcceptanceCriterion6DefaultProtection:
    """AC 6: All routes except /api/auth/register and /api/auth/login are protected by default."""

    def test_register_is_exempt_from_token_requirement(self, client):
        # Should not return 401 Unauthorized, returns 400 Bad Request on empty payload
        res = client.post("/api/auth/register", json={})
        assert res.status_code == 400

    def test_login_is_exempt_from_token_requirement(self, client):
        # Should not return 401 Unauthorized for missing token, returns 400 Bad Request on empty payload
        res = client.post("/api/auth/login", json={})
        assert res.status_code == 400

    def test_health_check_endpoint_is_exempt(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.get_json() == {"status": "ok"}

    def test_unregistered_or_new_routes_are_protected_by_default(self, app, client, auth_headers):
        @app.route("/api/documents/list")
        def document_list():
            return jsonify({"documents": [], "user_id": g.user_id})

        # Without token: protected by default -> 401
        unauth_res = client.get("/api/documents/list")
        assert unauth_res.status_code == 401

        # With valid token: succeeds and accesses g.user_id
        auth_res = client.get("/api/documents/list", headers=auth_headers)
        assert auth_res.status_code == 200
        assert auth_res.get_json()["user_id"] == 42

    def test_options_requests_pass_through_for_cors_preflight(self, app, client):
        @app.route("/api/test-preflight", methods=["GET", "OPTIONS"])
        def preflight_route():
            return ("", 204)

        res = client.open("/api/test-preflight", method="OPTIONS")
        assert res.status_code == 204

    def test_public_route_decorator_exempts_route_if_explicitly_used(self, app, client):
        @app.route("/api/public-info")
        @public_route
        def public_info():
            return jsonify({"info": "public data"})

        res = client.get("/api/public-info")
        assert res.status_code == 200
        assert res.get_json() == {"info": "public data"}
