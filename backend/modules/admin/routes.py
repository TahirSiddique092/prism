"""Admin routes for PRISM (slice-35). Read-only, admins only.

Exposes:
- GET /api/admin/users: every user with their activity counts (sp_admin_user_overview)
- GET /api/admin/stats: system-wide totals (sp_admin_system_stats)
- GET /api/admin/deletions: the latest deletion_audit rows (written by the trigger)
"""
import logging
from flask import Blueprint, jsonify

try:
    from backend.modules.auth import require_admin
    from backend.modules.admin.db import get_deletion_log, get_system_stats, get_user_overview
except ImportError:
    from modules.auth import require_admin
    from modules.admin.db import get_deletion_log, get_system_stats, get_user_overview

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/users", methods=["GET"], strict_slashes=False)
@require_admin
def users():
    """GET /api/admin/users.

    Response: [{ user_id, name, email, role, created_at, documents, chunks, searches, last_search_at }]
    """
    try:
        return jsonify(get_user_overview()), 200
    except Exception as e:
        logger.error(f"Error retrieving the user overview: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve users"}), 500


@admin_bp.route("/stats", methods=["GET"], strict_slashes=False)
@require_admin
def stats():
    """GET /api/admin/stats.

    Response: { users, admins, documents, documents_processing, documents_ready,
    documents_error, chunks, searches, searches_today, deletions }
    """
    try:
        return jsonify(get_system_stats()), 200
    except Exception as e:
        logger.error(f"Error retrieving system stats: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve system stats"}), 500


@admin_bp.route("/deletions", methods=["GET"], strict_slashes=False)
@require_admin
def deletions():
    """GET /api/admin/deletions.

    Response: [{ audit_id, doc_id, title, user_id, deleted_at }], newest first, at most 50.
    """
    try:
        return jsonify(get_deletion_log()), 200
    except Exception as e:
        logger.error(f"Error retrieving the deletion log: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve the deletion log"}), 500
