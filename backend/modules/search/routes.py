"""Search routes for PRISM (Slice 09 & 10).

Exposes POST /api/search for semantic search with FULLTEXT fallback and logging.
"""
import logging
from flask import Blueprint, request, jsonify, g, current_app

try:
    from backend.modules.search.service import execute_semantic_search, log_search_async
except ImportError:
    from modules.search.service import execute_semantic_search, log_search_async

logger = logging.getLogger(__name__)

search_bp = Blueprint("search", __name__, url_prefix="/api/search")


@search_bp.route("", methods=["POST"], strict_slashes=False)
def search():
    """POST /api/search
    
    Request body: { "query": "plain English query" }
    Response: [{ chunk_id, doc_id, doc_title, snippet, score }]
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Request body must be a valid JSON object"}), 400

    query = data.get("query")
    if query is None or not isinstance(query, str) or not query.strip():
        return jsonify({"error": "Query string is required and cannot be empty"}), 400

    user_id = g.user_id
    clean_query = query.strip()

    try:
        results = execute_semantic_search(user_id=user_id, query=clean_query, limit=10)

        # Slice 10: Non-blocking search logging to search_log and search_results
        try:
            sync_logging = current_app.config.get("SEARCH_LOGGING_SYNC", False)
            log_search_async(user_id=user_id, query=clean_query, results=results, sync=sync_logging)
        except Exception as log_err:
            logger.error(f"Failed to dispatch search logging for user {user_id}: {log_err}", exc_info=True)

        return jsonify(results), 200
    except Exception as e:
        logger.error(f"Error executing search for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to execute search: {str(e)}"}), 500

