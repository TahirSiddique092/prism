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
    from backend.modules.auth import auth_bp, register_auth_middleware
    from backend.modules.documents.routes import documents_bp
    from backend.modules.documents.storage import ensure_bucket_exists
    from backend.modules.documents import embed
except ImportError:
    from modules.auth import auth_bp, register_auth_middleware
    from modules.documents.routes import documents_bp
    from modules.documents.storage import ensure_bucket_exists
    from modules.documents import embed


def create_app(test_config=None):
    """Application factory for PRISM backend."""
    app = Flask(__name__)

    if test_config:
        app.config.update(test_config)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    
    if not test_config:
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
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
