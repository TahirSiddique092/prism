"""Authentication middleware and decorators for PRISM (Slice 04).

Provides:
- extract_bearer_token: Parses and validates the Authorization: Bearer <token> header.
- authenticate_request: Extracts and decodes the JWT, setting g.user_id on success.
- require_auth: Decorator to protect specific routes and inject g.user_id.
- public_route: Decorator to explicitly mark a route as exempt from default auth.
- register_auth_middleware: Enforces authentication across all routes by default,
  exempting /api/auth/register, /api/auth/login, and /health.
"""
from functools import wraps
from flask import Flask, g, jsonify, request
import jwt

try:
    from backend.modules.auth.service import decode_token
except ImportError:
    from modules.auth.service import decode_token


DEFAULT_EXEMPT_ROUTES = frozenset({
    "/api/auth/register",
    "/api/auth/login",
    "/health",
})

DEFAULT_EXEMPT_ENDPOINTS = frozenset({
    "auth.register",
    "auth.login",
    "health",
})


def extract_bearer_token(auth_header: str | None) -> str | None:
    """Extract and validate the token string from an Authorization header.
    
    Expected format: Bearer <token>
    Returns the token string if valid, otherwise None.
    """
    if not auth_header or not isinstance(auth_header, str):
        return None

    parts = auth_header.strip().split(None, 1)
    if len(parts) != 2:
        return None

    scheme, token = parts[0], parts[1].strip()
    if scheme.lower() != "bearer" or not token:
        return None

    # JWT tokens cannot contain whitespace
    if any(c.isspace() for c in token):
        return None

    return token


def authenticate_request():
    """Verify authorization header and inject user context into flask.g.
    
    Returns:
        (True, None) on successful authentication.
        (False, (response, status_code)) on failure (HTTP 401).
    """
    auth_header = request.headers.get("Authorization")
    token = extract_bearer_token(auth_header)
    if not token:
        return False, (
            jsonify({
                "error": "Missing or invalid authorization header",
                "message": "Unauthorized",
            }),
            401,
        )

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        # Acceptance criteria: Expired token returns 401 with message "token expired"
        return False, (
            jsonify({
                "error": "token expired",
                "message": "token expired",
            }),
            401,
        )
    except (jwt.InvalidTokenError, Exception):
        # Acceptance criteria: Missing or invalid token returns 401
        return False, (
            jsonify({
                "error": "Invalid token",
                "message": "Unauthorized",
            }),
            401,
        )

    user_id = payload.get("user_id")
    if user_id is None:
        return False, (
            jsonify({
                "error": "Invalid token payload: missing user_id",
                "message": "Unauthorized",
            }),
            401,
        )

    try:
        g.user_id = int(user_id)
    except (ValueError, TypeError):
        return False, (
            jsonify({
                "error": "Invalid token payload: non-integer user_id",
                "message": "Unauthorized",
            }),
            401,
        )

    g.user = payload
    g.token = token
    return True, None


def require_auth(fn):
    """Decorator to require valid JWT authentication for a route.
    
    Verifies the Bearer token, populates flask.g.user_id, and returns 401
    for missing, invalid, or expired tokens.
    """
    @wraps(fn)
    def decorated_function(*args, **kwargs):
        # If user_id is already set on g for this request, proceed directly
        if getattr(g, "user_id", None) is not None:
            return fn(*args, **kwargs)

        success, error_tuple = authenticate_request()
        if not success:
            response, status_code = error_tuple
            return response, status_code

        return fn(*args, **kwargs)

    return decorated_function


def public_route(fn):
    """Decorator to mark a route as exempt from default authentication."""
    fn._auth_exempt = True
    return fn


def register_auth_middleware(app: Flask) -> None:
    """Register before_request hook ensuring all routes are protected by default.
    
    All routes except /api/auth/register and /api/auth/login (and /health)
    require valid JWT authentication.
    """
    @app.before_request
    def enforce_default_auth():
        # Allow disabling auth completely via config if needed
        if app.config.get("AUTH_DISABLED", False):
            return None

        # Allow browser CORS preflight requests without credentials
        if request.method == "OPTIONS":
            return None

        # Build set of exempt routes from defaults and optional app config
        configured_exempt = app.config.get("AUTH_EXEMPT_ROUTES", ())
        exempt_routes = DEFAULT_EXEMPT_ROUTES.union(configured_exempt)

        path = request.path.rstrip("/") if request.path != "/" else "/"
        if path in exempt_routes:
            return None

        # Check endpoint name (e.g. auth.register, auth.login, health)
        if request.endpoint in DEFAULT_EXEMPT_ENDPOINTS:
            return None

        # Check if the view function was decorated with @public_route
        if request.endpoint:
            view_func = app.view_functions.get(request.endpoint)
            if view_func and getattr(view_func, "_auth_exempt", False):
                return None

        # All other routes are protected by default
        success, error_tuple = authenticate_request()
        if not success:
            response, status_code = error_tuple
            return response, status_code

        return None
