"""Semantic search service using sentence-transformers, pgvector, and Redis caching (Slice 09)."""
import logging
from typing import List, Dict, Any

try:
    from backend.modules.documents.embed import get_embeddings
    from backend.modules.cache import get_cached_search, set_cached_search
    from backend.modules.search.db import (
        get_user_document_ids,
        search_chunk_vectors,
        get_chunks_metadata,
    )
except ImportError:
    from modules.documents.embed import get_embeddings
    from modules.cache import get_cached_search, set_cached_search
    from modules.search.db import (
        get_user_document_ids,
        search_chunk_vectors,
        get_chunks_metadata,
    )

logger = logging.getLogger(__name__)


def execute_semantic_search(user_id: int, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Execute semantic vector search with caching and multi-tenant scoping.
    
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
        return []

    # 1. Check Redis cache before computing embedding
    cached_results = get_cached_search(user_id, clean_query)
    if cached_results is not None:
        logger.info(f"Cache hit for search query: '{clean_query}' (user_id={user_id})")
        return cached_results

    # 2. Get user's document IDs from MySQL
    user_doc_ids = get_user_document_ids(user_id)
    if not user_doc_ids:
        # User has no documents uploaded yet
        set_cached_search(user_id, clean_query, [])
        return []

    # 3. Compute query embedding
    query_embeddings = get_embeddings([clean_query])
    if not query_embeddings:
        return []
    query_vec = query_embeddings[0]

    # 4. Search pgvector for top matches belonging to user's documents
    vector_matches = search_chunk_vectors(query_vec, user_doc_ids, limit=limit)
    if not vector_matches:
        set_cached_search(user_id, clean_query, [])
        return []

    # 5. Fetch chunk snippets and doc titles from MySQL
    chunk_ids = [m["chunk_id"] for m in vector_matches]
    metadata_map = get_chunks_metadata(chunk_ids)

    # 6. Assemble ordered response
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

    # 7. Write to cache
    set_cached_search(user_id, clean_query, results, ttl=3600)

    return results
