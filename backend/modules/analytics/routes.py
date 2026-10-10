"""Analytics routes for PRISM (Slice 14 & 15).

Exposes:
- GET /api/analytics/history: user's search history ranked by frequency using window functions
"""
import logging
from flask import Blueprint, jsonify, g

try:
    from backend.modules.analytics.db import get_search_history
except ImportError:
    from modules.analytics.db import get_search_history

logger = logging.getLogger(__name__)

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@analytics_bp.route("/history", methods=["GET"], strict_slashes=False)
def search_history():
    """GET /api/analytics/history (Slice 14).

    Returns authenticated user's search history ranked by frequency using SQL window functions.
    Response: [{ query_text, search_count, query_rank, last_searched, total_searches }]
    """
    user_id = g.user_id
    try:
        history = get_search_history(user_id=user_id)
        return jsonify(history), 200
    except Exception as e:
        logger.error(f"Error retrieving search history for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to retrieve search history: {str(e)}"}), 500
