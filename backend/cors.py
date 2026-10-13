"""CORS configuration and origin filtering for PRISM (Slice 23).

Enforces acceptance criteria:
- Flask CORS is configured to allow requests only from the Vercel domain — all other origins return 403.
- Safe handling of server-to-server proxy requests (no Origin header).
"""
import os
import re
from flask import Flask, Response, jsonify, request


# Regex matching official Vercel deployment domains:
# Covers production (e.g. https://prism.vercel.app), preview deployments, and
# branch URLs. Requires at least one subdomain label (so the bare apex
# https://vercel.app is NOT trusted as an API origin).
VERCEL_DOMAIN_REGEX = re.compile(r"^https://([a-zA-Z0-9-]+\.)+vercel\.app(?::\d+)?$")

# Regex for local development origins (localhost / 127.0.0.1)
DEV_ORIGIN_REGEX = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")


def get_configured_origins() -> set[str]:
    """Retrieve explicitly configured allowed origins from environment variables."""
    origins: set[str] = set()

    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.add(frontend_url.strip().rstrip("/"))

    vercel_url = os.getenv("VERCEL_URL")
    if vercel_url:
        cleaned = vercel_url.strip().rstrip("/")
        if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            cleaned = f"https://{cleaned}"
        origins.add(cleaned)

    custom_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if custom_origins:
        for orig in custom_origins.split(","):
            cleaned = orig.strip().rstrip("/")
            if cleaned:
                origins.add(cleaned)

    return origins


def is_origin_allowed(origin: str | None, app: Flask | None = None) -> bool:
    """Check if an Origin header is permitted.

    Permitted origins:
    1. Matches any explicitly configured FRONTEND_URL, VERCEL_URL, or CORS_ALLOWED_ORIGINS
    2. Any valid Vercel deployment domain (*.vercel.app over HTTPS)
    3. Localhost during testing or local development
    """
    if not origin:
        return True

    clean_origin = origin.strip().rstrip("/")

    # Check explicitly configured origins
    configured = get_configured_origins()
    if clean_origin in configured:
        return True

    # Strict mode (opt-in for production): trust ONLY explicitly configured
    # origins — do not accept the whole *.vercel.app space, since any tenant can
    # deploy there. Enable with CORS_STRICT=true (env) or app.config CORS_STRICT.
    strict = os.getenv("CORS_STRICT", "false").strip().lower() in ("true", "1", "yes")
    if app is not None and app.config.get("CORS_STRICT"):
        strict = True
    if strict:
        return False

    # Check Vercel domain pattern (*.vercel.app)
    if VERCEL_DOMAIN_REGEX.match(clean_origin):
        return True

    # Check local development origins
    is_testing = app.config.get("TESTING", False) if app else False
    is_debug = app.config.get("DEBUG", False) if app else False
    allow_dev = os.getenv("ALLOW_DEV_CORS", "false").lower() in ("true", "1", "yes")

    if (is_testing or is_debug or allow_dev or os.getenv("FLASK_ENV") == "development") and DEV_ORIGIN_REGEX.match(clean_origin):
        return True

    return False


def register_cors_middleware(app: Flask) -> None:
    """Register before_request and after_request hooks enforcing Vercel-only CORS.

    All cross-origin requests from disallowed origins return an immediate HTTP 403 Forbidden.
    """
    @app.before_request
    def enforce_cors_policy():
        # Allow disabling CORS completely via config if explicitly requested
        if app.config.get("CORS_DISABLED", False):
            return None

        origin = request.headers.get("Origin")
        if not origin:
            # Server-to-server calls (e.g. Next.js server route handler fetch, curl)
            # do not provide an Origin header; allow them to proceed.
            return None

        if not is_origin_allowed(origin, app):
            return (
                jsonify({
                    "error": "Forbidden",
                    "message": "Origin not allowed by CORS policy",
                }),
                403,
            )

        # Preflight OPTIONS request from an allowed origin
        if request.method == "OPTIONS":
            response = Response("", status=204)
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, HEAD"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, X-Requested-With"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response

        return None

    @app.after_request
    def add_cors_headers(response: Response) -> Response:
        origin = request.headers.get("Origin")
        if origin and is_origin_allowed(origin, app):
            # Response varies by Origin, so caches must key on it — otherwise a
            # cached per-origin ACAO could be replayed to a different origin.
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, HEAD"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, X-Requested-With"
        return response
