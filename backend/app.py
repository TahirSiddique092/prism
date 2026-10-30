"""PRISM Backend Flask Application Entry Point."""
import os
import sys
from pathlib import Path
from flask import Flask, jsonify

# Ensure backend package and repository root are on python path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
for path in (str(PROJECT_ROOT), str(CURRENT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from backend.cors import register_cors_middleware
    from backend.modules.auth import auth_bp, register_auth_middleware
    from backend.modules.documents.routes import documents_bp
    from backend.modules.documents.storage import ensure_bucket_exists
    from backend.modules.documents import embed
    from backend.modules.search import search_bp
    from backend.modules.analytics import analytics_bp
except ImportError:
    from cors import register_cors_middleware
    from modules.auth import auth_bp, register_auth_middleware
    from modules.documents.routes import documents_bp
    from modules.documents.storage import ensure_bucket_exists
    from modules.documents import embed
    from modules.search import search_bp
    from modules.analytics import analytics_bp


try:
    from backend.modules.auth.service import DEFAULT_DEV_SECRET
except ImportError:
    from modules.auth.service import DEFAULT_DEV_SECRET


def _validate_security_config(app):
    """Fail fast at startup if the production security config is unsafe.

    In production (PRISM_ENV/FLASK_ENV == "production") a strong JWT_SECRET is
    mandatory — booting with a missing/weak/known-default secret would let anyone
    forge auth tokens. In dev we only warn so local runs and tests stay frictionless.
    """
    env = (os.getenv("PRISM_ENV") or os.getenv("FLASK_ENV") or "").strip().lower()
    is_production = env == "production"
    secret = os.getenv("JWT_SECRET")

    if is_production:
        if not secret or secret == DEFAULT_DEV_SECRET or len(secret) < 32:
            raise RuntimeError(
                "JWT_SECRET must be set to a strong value (>=32 chars, not the "
                "development default) when PRISM_ENV=production."
            )
    elif not secret:
        app.logger.warning(
            "JWT_SECRET is not set; using the insecure development fallback. "
            "Set JWT_SECRET and PRISM_ENV=production before deploying."
        )


def create_app(test_config=None):
    """Application factory for PRISM backend."""
    app = Flask(__name__)

    if test_config:
        app.config.update(test_config)

    # Register CORS middleware (Slice 23: Vercel-only domain policy)
    register_cors_middleware(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(analytics_bp)
    
    if not test_config:
        _validate_security_config(app)
        try:
            ensure_bucket_exists()
        except Exception as e:
            app.logger.warning(f"Could not initialize MinIO bucket on startup: {e}")

    # Register authentication middleware (protects all routes by default except exempt routes)
    register_auth_middleware(app)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    # Documents are processed in background threads of this process, so one
    # still 'processing' now was interrupted by a restart: mark it 'error' so
    # it can be retried (slice-28). Done here, when the server starts, never
    # on import, so tests and scripts that import the app change nothing.
    try:
        try:
            from backend.modules.documents.db import mark_interrupted_processing_failed
        except ImportError:
            from modules.documents.db import mark_interrupted_processing_failed
        interrupted = mark_interrupted_processing_failed()
        if interrupted:
            app.logger.warning(f"Marked {interrupted} interrupted document(s) as error; they can be retried")
    except Exception as e:
        app.logger.warning(f"Could not check for interrupted processing: {e}")

    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
