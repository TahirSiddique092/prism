"""Semantic search service with pgvector, FULLTEXT fallback, Redis caching, and logging (Slice 09 & 10)."""
import logging
import threading
from typing import List, Dict, Any, Tuple

VECTOR_SIMILARITY_THRESHOLD = 0.75

try:
    from backend.modules.documents.embed import get_embeddings
    from backend.modules.cache import get_cached_search, set_cached_search
    from backend.modules.search.db import (
        get_user_document_ids,
        search_chunk_vectors,
        get_chunks_metadata,
        search_chunks_fulltext,
        insert_search_log,
        insert_search_results,
    )
except ImportError:
    from modules.documents.embed import get_embeddings
    from modules.cache import get_cached_search, set_cached_search
    from modules.search.db import (
        get_user_document_ids,
        search_chunk_vectors,
        get_chunks_metadata,
        search_chunks_fulltext,
        insert_search_log,
        insert_search_results,
    )

logger = logging.getLogger(__name__)


def execute_semantic_search(user_id: int, query: str, limit: int = 10) -> Tuple[List[Dict[str, Any]], bool]:
    """Execute semantic vector search with caching and multi-tenant scoping.

    Returns a ``(results, cached)`` tuple, where ``cached`` is True only when the
    results were served from the Redis cache without touching pgvector.

    Workflow:
    1. Check Redis cache first — if hit, return cached result immediately.
    2. Retrieve user's document IDs to ensure isolation to authenticated user.
    3. If user has no documents, return empty list.
    4. Embed query using all-MiniLM-L6-v2.
    5. Search pgvector ordered by cosine distance (embedding <=> query_vec).
    6. Retrieve chunk snippet and document title metadata from MySQL.
    7. Assemble results [{ chunk_id, doc_id, doc_title, snippet, score }].
    8. Store results in Redis cache.
    9. Return results.
    """
    clean_query = query.strip()
    if not clean_query:
        return [], False

    # 1. Check Redis cache before computing embedding
    cached_results = get_cached_search(user_id, clean_query)
    if cached_results is not None:
        logger.info(f"Cache hit for search query: '{clean_query}' (user_id={user_id})")
        return cached_results, True

    # 2. Get user's document IDs from MySQL
    user_doc_ids = get_user_document_ids(user_id)
    if not user_doc_ids:
        # User has no documents uploaded yet
        set_cached_search(user_id, clean_query, [])
        return [], False

    # 3. Compute query embedding
    query_embeddings = get_embeddings([clean_query])
    if not query_embeddings:
        return [], False
    query_vec = query_embeddings[0]

    # 4. Search pgvector for top matches belonging to user's documents
    vector_matches = search_chunk_vectors(query_vec, user_doc_ids, limit=limit)

    # 5. Check fallback condition (Slice 10):
    # Triggered when best cosine distance from pgvector exceeds 0.75, or if no vector matches found.
    is_fallback = False
    if not vector_matches:
        is_fallback = True
    elif vector_matches[0]["score"] > VECTOR_SIMILARITY_THRESHOLD:
        is_fallback = True

    if is_fallback:
        logger.info(
            f"Triggering MySQL FULLTEXT fallback for user {user_id}, query: '{clean_query}'. "
            f"Best vector score: {vector_matches[0]['score'] if vector_matches else 'none'} "
            f"(threshold={VECTOR_SIMILARITY_THRESHOLD})"
        )
        fallback_results = search_chunks_fulltext(user_id=user_id, query=clean_query, limit=limit)
        set_cached_search(user_id, clean_query, fallback_results, ttl=3600)
        return fallback_results, False

    # 6. Fetch chunk snippets and doc titles from MySQL for vector matches
    chunk_ids = [m["chunk_id"] for m in vector_matches]
    metadata_map = get_chunks_metadata(chunk_ids)

    # 7. Assemble ordered response
    results = []
    for match in vector_matches:
        chunk_id = match["chunk_id"]
        meta = metadata_map.get(chunk_id)
        if meta:
            results.append({
                "chunk_id": chunk_id,
                "doc_id": match["doc_id"],
                "doc_title": meta["doc_title"],
                "snippet": meta["snippet"],
                "score": match["score"],
            })

    # 8. Write to cache
    set_cached_search(user_id, clean_query, results, ttl=3600)

    return results, False


def log_search(user_id: int, query: str, results: list[dict], conn=None) -> int | None:
    """Log search query and its results to MySQL search_log and search_results (Slice 10).
    
    AC:
    - Every POST /api/search call produces exactly one search_log row.
    - search_results rows are correctly linked to search_log row with rank 1–10.
    - A search that returns zero results still logs to search_log (with no search_results rows).
    - Logging failure does not cause search response to fail.
    """
    try:
        log_id = insert_search_log(user_id, query, conn=conn)
        if results and log_id:
            insert_search_results(log_id, results, conn=conn)
        return log_id
    except Exception as e:
        logger.error(f"Failed to log search for user {user_id}: {e}", exc_info=True)
        return None


def log_search_async(
    user_id: int,
    query: str,
    results: list[dict],
    sync: bool = False,
) -> threading.Thread | None:
    """Dispatch search logging asynchronously without blocking the HTTP response (Slice 10).
    
    If sync=True, executes synchronously (useful for test assertions).
    """
    if sync:
        log_search(user_id, query, results)
        return None

    t = threading.Thread(
        target=log_search,
        args=(user_id, query, results),
        daemon=True,
    )
    t.start()
    return t

