"""Analytics routes for PRISM (Slice 14 & 15).

Exposes:
- GET /api/analytics/history: user's search history ranked by frequency using window functions
- GET /api/analytics/unsearched: user's documents that never appeared in search results (CTE)
- GET /api/analytics/top-documents: user's top documents by search appearance (SQL view)
"""
import logging
from flask import Blueprint, jsonify, g

try:
    from backend.modules.analytics.db import (
        get_search_history,
        get_unsearched_documents,
        get_top_documents,
    )
except ImportError:
    from modules.analytics.db import (
        get_search_history,
        get_unsearched_documents,
        get_top_documents,
    )

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


@analytics_bp.route("/unsearched", methods=["GET"], strict_slashes=False)
def unsearched():
    """GET /api/analytics/unsearched (Slice 15).

    Returns documents the user uploaded that have never appeared in any search result.
    Response: [{ doc_id, title, uploaded_at }]
    """
    user_id = g.user_id
    try:
        docs = get_unsearched_documents(user_id=user_id)
        return jsonify(docs), 200
    except Exception as e:
        logger.error(f"Error retrieving unsearched documents for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to retrieve unsearched documents: {str(e)}"}), 500


@analytics_bp.route("/top-documents", methods=["GET"], strict_slashes=False)
def top_documents():
    """GET /api/analytics/top-documents (Slice 15).

    Returns documents ranked by how often their chunks appear in search results.
    Response: [{ doc_id, title, appearance_count, avg_score }]
    """
    user_id = g.user_id
    try:
        docs = get_top_documents(user_id=user_id)
        return jsonify(docs), 200
    except Exception as e:
        logger.error(f"Error retrieving top documents for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to retrieve top documents: {str(e)}"}), 500
