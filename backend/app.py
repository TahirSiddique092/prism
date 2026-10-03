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
    from backend.modules.auth import auth_bp
except ImportError:
    from modules.auth import auth_bp


def create_app(test_config=None):
    """Application factory for PRISM backend."""
    app = Flask(__name__)

    if test_config:
        app.config.update(test_config)

    # Register blueprints
    app.register_blueprint(auth_bp)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
