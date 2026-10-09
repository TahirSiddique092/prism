"""Search routes for PRISM (Slice 09).

Exposes POST /api/search for semantic search over user documents.
"""
import logging
from flask import Blueprint, request, jsonify, g

try:
    from backend.modules.search.service import execute_semantic_search
except ImportError:
    from modules.search.service import execute_semantic_search

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

    try:
        results = execute_semantic_search(user_id=user_id, query=query.strip(), limit=10)
        return jsonify(results), 200
    except Exception as e:
        logger.error(f"Error executing search for user {user_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to execute search: {str(e)}"}), 500
