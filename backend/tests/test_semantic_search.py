"""Acceptance criteria tests for slice-09: Semantic search via pgvector.

Acceptance criteria verified:
1. A query with zero overlapping words with the target chunk still returns a relevant result.
2. Results are filtered to the current user's documents only — never surface other users' content.
3. Cache is checked before any embedding is computed.
4. Response time under 3 seconds for a cold cache hit.
5. score in response is the raw cosine distance (lower = more similar).
6. Missing or empty query returns 400.
7. Unauthenticated request returns 401.
"""
import time
from unittest.mock import MagicMock, call, patch
import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token
from backend.modules.cache.service import get_search_cache_key


@pytest.fixture
def app():
    """Create application configured for testing."""
    test_app = create_app({"TESTING": True})
    return test_app


@pytest.fixture
def client(app):
    """Test client."""
    return app.test_client()


@pytest.fixture
def user1_token():
    return generate_token(user_id=1, email="user1@example.com")


@pytest.fixture
def user2_token():
    return generate_token(user_id=2, email="user2@example.com")


# ============================================================================
# 1. Authentication & Request Validation
# ============================================================================

def test_search_unauthenticated(client):
    """POST /api/search without token returns 401."""
    res = client.post("/api/search", json={"query": "machine learning"})
    assert res.status_code == 401


def test_search_missing_query(client, user1_token):
    """POST /api/search without query field returns 400."""
    res = client.post(
        "/api/search",
        json={},
        headers={"Authorization": f"Bearer {user1_token}"},
    )
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_search_empty_query(client, user1_token):
    """POST /api/search with empty or whitespace-only query returns 400."""
    res = client.post(
        "/api/search",
        json={"query": "   "},
        headers={"Authorization": f"Bearer {user1_token}"},
    )
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_search_invalid_json(client, user1_token):
    """POST /api/search with invalid body returns 400."""
    res = client.post(
        "/api/search",
        data="not a json",
        headers={"Authorization": f"Bearer {user1_token}", "Content-Type": "application/json"},
    )
    assert res.status_code == 400


# ============================================================================
# 2. Cache Behavior: Cache is checked before embedding
# ============================================================================

def test_search_cache_hit_skips_embedding_and_database(client, user1_token):
    """AC: Cache is checked before any embedding is computed.
    
    If Redis has a cache hit, returns cached result immediately without
    computing embedding or hitting the database.
    """
    cached_payload = [
        {
            "chunk_id": 10,
            "doc_id": 1,
            "doc_title": "AI Handbook.pdf",
            "snippet": "Neural networks process vector data.",
            "score": 0.15,
        }
    ]

    with patch("backend.modules.search.service.get_cached_search", return_value=cached_payload) as mock_cache_get, \
         patch("backend.modules.search.service.get_embeddings") as mock_get_embeddings, \
         patch("backend.modules.search.service.search_chunk_vectors") as mock_pg_search:

        res = client.post(
            "/api/search",
            json={"query": "neural networks"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        assert res.get_json() == cached_payload

        # Cache must be checked
        mock_cache_get.assert_called_once_with(1, "neural networks")
        # Embedding and vector search MUST NOT be called on cache hit
        mock_get_embeddings.assert_not_called()
        mock_pg_search.assert_not_called()


def test_search_cache_miss_populates_cache(client, user1_token):
    """On cache miss, results are computed, cached in Redis, and returned."""
    fake_vector_results = [{"chunk_id": 101, "doc_id": 5, "score": 0.22}]
    fake_metadata = {
        101: {
            "chunk_id": 101,
            "doc_id": 5,
            "snippet": "Photosynthesis produces oxygen and glucose.",
            "doc_title": "Biology 101.pdf",
        }
    }

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[5]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors", return_value=fake_vector_results), \
         patch("backend.modules.search.service.get_chunks_metadata", return_value=fake_metadata), \
         patch("backend.modules.search.service.set_cached_search") as mock_set_cache:

        res = client.post(
            "/api/search",
            json={"query": "how plants make food"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        data = res.get_json()
        assert len(data) == 1
        assert data[0]["chunk_id"] == 101
        assert data[0]["doc_title"] == "Biology 101.pdf"
        assert data[0]["snippet"] == "Photosynthesis produces oxygen and glucose."
        assert data[0]["score"] == 0.22

        # Cache was written with 3600s TTL
        mock_set_cache.assert_called_once_with(
            1,
            "how plants make food",
            data,
            ttl=3600,
        )


# ============================================================================
# 3. User Filtering: Never surface other users' content
# ============================================================================

def test_search_results_filtered_to_authenticated_user_only(client, user1_token, user2_token):
    """AC: Results are filtered to the current user's documents only — never surface other users' content."""
    # User 1 owns doc 10, User 2 owns doc 20
    def mock_get_user_doc_ids(user_id, conn=None):
        if user_id == 1:
            return [10]
        elif user_id == 2:
            return [20]
        return []

    def mock_search_vectors(query_vec, doc_ids, limit=10, pg_conn=None):
        # Verify that pgvector search only searches within the passed doc_ids
        if doc_ids == [10]:
            return [{"chunk_id": 101, "doc_id": 10, "score": 0.12}]
        elif doc_ids == [20]:
            return [{"chunk_id": 201, "doc_id": 20, "score": 0.08}]
        return []

    mock_meta = {
        101: {"chunk_id": 101, "doc_id": 10, "snippet": "User 1 document content.", "doc_title": "Doc1.pdf"},
        201: {"chunk_id": 201, "doc_id": 20, "snippet": "User 2 top secret data.", "doc_title": "Secret.pdf"},
    }

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", side_effect=mock_get_user_doc_ids), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.05] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors", side_effect=mock_search_vectors), \
         patch("backend.modules.search.service.get_chunks_metadata", return_value=mock_meta), \
         patch("backend.modules.search.service.set_cached_search"):

        # User 1 search
        res1 = client.post(
            "/api/search",
            json={"query": "test query"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res1.status_code == 200
        data1 = res1.get_json()
        assert len(data1) == 1
        assert data1[0]["doc_id"] == 10
        assert data1[0]["doc_title"] == "Doc1.pdf"
        assert not any(d["doc_id"] == 20 for d in data1)

        # User 2 search
        res2 = client.post(
            "/api/search",
            json={"query": "test query"},
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert len(data2) == 1
        assert data2[0]["doc_id"] == 20
        assert data2[0]["doc_title"] == "Secret.pdf"
        assert not any(d["doc_id"] == 10 for d in data2)


def test_search_user_with_no_documents_returns_empty_list(client, user1_token):
    """When a user has no documents uploaded, return [] immediately."""
    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[]), \
         patch("backend.modules.search.service.get_embeddings") as mock_embed, \
         patch("backend.modules.search.service.search_chunk_vectors") as mock_pg:

        res = client.post(
            "/api/search",
            json={"query": "any query"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        assert res.get_json() == []
        mock_embed.assert_not_called()
        mock_pg.assert_not_called()


# ============================================================================
# 4. Semantic Matching: Zero overlapping words returns relevant result
# ============================================================================

def test_semantic_embedding_zero_overlapping_words():
    """AC: A query with zero overlapping words with the target chunk still returns a relevant result.
    
    Verifies actual sentence-transformers embedding model (all-MiniLM-L6-v2)
    correctly places semantically related text closer than unrelated text,
    even when they share 0 words.
    """
    from backend.modules.documents.embed import get_embeddings
    import numpy as np

    # Query has 0 words in common with target chunk
    query = "canine companions"
    target_chunk = "Dogs are loyal quadrupeds that make great household pets."
    distractor_chunk_1 = "Quantum electrodynamics describes relativistic interactions of charged leptons."
    distractor_chunk_2 = "Corporate earnings quarterly reports showed steady financial growth."

    embeddings = get_embeddings([query, target_chunk, distractor_chunk_1, distractor_chunk_2])
    q_vec = np.array(embeddings[0])
    target_vec = np.array(embeddings[1])
    d1_vec = np.array(embeddings[2])
    d2_vec = np.array(embeddings[3])

    def cosine_distance(a, b):
        return 1.0 - (np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    target_dist = cosine_distance(q_vec, target_vec)
    d1_dist = cosine_distance(q_vec, d1_vec)
    d2_dist = cosine_distance(q_vec, d2_vec)

    # Cosine distance to dog chunk must be significantly lower than unrelated chunks
    assert target_dist < d1_dist
    assert target_dist < d2_dist
    assert target_dist < 0.6  # Relevant semantic match threshold


# ============================================================================
# 5. Raw Cosine Distance Score & Response Timing
# ============================================================================

def test_search_score_is_raw_cosine_distance_ordered(client, user1_token):
    """AC: `score` in response is the raw cosine distance (lower = more similar), ordered ascending."""
    fake_vector_results = [
        {"chunk_id": 1, "doc_id": 10, "score": 0.15},
        {"chunk_id": 2, "doc_id": 10, "score": 0.38},
        {"chunk_id": 3, "doc_id": 10, "score": 0.72},
    ]
    fake_metadata = {
        1: {"chunk_id": 1, "doc_id": 10, "snippet": "Best match", "doc_title": "Doc.pdf"},
        2: {"chunk_id": 2, "doc_id": 10, "snippet": "Medium match", "doc_title": "Doc.pdf"},
        3: {"chunk_id": 3, "doc_id": 10, "snippet": "Farther match", "doc_title": "Doc.pdf"},
    }

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[10]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors", return_value=fake_vector_results), \
         patch("backend.modules.search.service.get_chunks_metadata", return_value=fake_metadata), \
         patch("backend.modules.search.service.set_cached_search"):

        res = client.post(
            "/api/search",
            json={"query": "test query"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        data = res.get_json()
        assert len(data) == 3
        assert [d["score"] for d in data] == [0.15, 0.38, 0.72]
        # Lower score = first in list
        assert data[0]["score"] < data[1]["score"] < data[2]["score"]


def test_search_cold_cache_response_time(client, user1_token):
    """AC: Response time under 3 seconds for a cold cache hit."""
    fake_vector_results = [{"chunk_id": 1, "doc_id": 10, "score": 0.25}]
    fake_metadata = {
        1: {"chunk_id": 1, "doc_id": 10, "snippet": "Sample snippet", "doc_title": "Doc.pdf"}
    }

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[10]), \
         patch("backend.modules.search.service.search_chunk_vectors", return_value=fake_vector_results), \
         patch("backend.modules.search.service.get_chunks_metadata", return_value=fake_metadata), \
         patch("backend.modules.search.service.set_cached_search"):

        start = time.time()
        res = client.post(
            "/api/search",
            json={"query": "computational complexity and algorithms"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        duration = time.time() - start

        assert res.status_code == 200
        assert duration < 3.0, f"Cold search took {duration:.2f}s, expected < 3.0s"


# ============================================================================
# 6. Database Raw SQL Contracts
# ============================================================================

def test_pgvector_query_contract():
    """Verify search_chunk_vectors uses <=> operator, doc_id = ANY(%s), and LIMIT."""
    from backend.modules.search.db import search_chunk_vectors

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [
        (42, 7, 0.18),
        (43, 7, 0.32),
    ]

    results = search_chunk_vectors(
        query_embedding=[0.0] * 384,
        doc_ids=[7, 8],
        limit=10,
        pg_conn=mock_conn,
    )

    assert len(results) == 2
    assert results[0]["chunk_id"] == 42
    assert results[0]["doc_id"] == 7
    assert results[0]["score"] == 0.18

    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "<=> %s::vector" in executed_sql
    assert "WHERE doc_id = ANY(%s)" in executed_sql
    assert "ORDER BY score ASC" in executed_sql
    assert "LIMIT %s" in executed_sql


def test_cache_key_normalization():
    """AC: Cache key is normalised — 'Joins in SQL' and 'joins in sql' resolve to the same key."""
    key1 = get_search_cache_key(user_id=1, query="Joins in SQL")
    key2 = get_search_cache_key(user_id=1, query="  joins in sql  ")
    assert key1 == key2
    assert key1.startswith("search:1:")
