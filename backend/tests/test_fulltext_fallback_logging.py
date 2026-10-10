"""Acceptance criteria tests for slice-10: FULLTEXT fallback and search logging.

Acceptance criteria verified:
1. When all vector scores exceed 0.75, FULLTEXT results are returned instead.
2. FULLTEXT results are still filtered to the current user's documents.
3. Every POST /api/search call produces exactly one search_log row.
4. search_results rows are correctly linked to the search_log row with rank 1–10.
5. A search that returns zero results still logs to search_log (with no search_results rows).
6. Logging failure does not cause the search response to fail.
"""
import threading
from unittest.mock import MagicMock, call, patch
import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token
from backend.modules.search.db import (
    search_chunks_fulltext,
    insert_search_log,
    insert_search_results,
)
from backend.modules.search.service import (
    VECTOR_SIMILARITY_THRESHOLD,
    log_search,
    log_search_async,
)


@pytest.fixture
def app():
    """Create application configured for testing."""
    test_app = create_app({"TESTING": True, "SEARCH_LOGGING_SYNC": True})
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
# 1. Fallback Logic: Vector score threshold > 0.75 triggers MySQL FULLTEXT
# ============================================================================

def test_fallback_triggered_when_vector_scores_exceed_threshold(client, user1_token):
    """AC 1: When all vector scores exceed 0.75, FULLTEXT results are returned instead.
    
    Response shape matches semantic search, with score: null to indicate fallback was used.
    """
    # Best vector score is 0.82 (> 0.75 threshold)
    poor_vector_matches = [
        {"chunk_id": 10, "doc_id": 1, "score": 0.82},
        {"chunk_id": 11, "doc_id": 1, "score": 0.89},
    ]

    fulltext_fallback_results = [
        {
            "chunk_id": 50,
            "doc_id": 1,
            "doc_title": "Database Systems.pdf",
            "snippet": "B-Tree indexes provide logarithmic search times.",
            "score": None,
        }
    ]

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[1]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors", return_value=poor_vector_matches), \
         patch("backend.modules.search.service.search_chunks_fulltext", return_value=fulltext_fallback_results) as mock_ft, \
         patch("backend.modules.search.service.set_cached_search") as mock_set_cache, \
         patch("backend.modules.search.routes.log_search_async"):

        res = client.post(
            "/api/search",
            json={"query": "B-Tree index"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        data = res.get_json()["results"]
        assert len(data) == 1
        assert data[0]["chunk_id"] == 50
        assert data[0]["doc_title"] == "Database Systems.pdf"
        assert data[0]["snippet"] == "B-Tree indexes provide logarithmic search times."
        # score must be null (None in Python)
        assert data[0]["score"] is None

        # FULLTEXT fallback was executed
        mock_ft.assert_called_once_with(user_id=1, query="B-Tree index", limit=10)
        # Fallback results were cached
        mock_set_cache.assert_called_once_with(1, "B-Tree index", fulltext_fallback_results, ttl=3600)


def test_fallback_not_triggered_when_vector_score_is_below_threshold(client, user1_token):
    """When best vector score is <= 0.75, semantic search results are returned, NOT fallback."""
    good_vector_matches = [
        {"chunk_id": 20, "doc_id": 2, "score": 0.35},
        {"chunk_id": 21, "doc_id": 2, "score": 0.50},
    ]
    meta_map = {
        20: {"chunk_id": 20, "doc_id": 2, "doc_title": "Doc.pdf", "snippet": "Vector chunk 20"},
        21: {"chunk_id": 21, "doc_id": 2, "doc_title": "Doc.pdf", "snippet": "Vector chunk 21"},
    }

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[2]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors", return_value=good_vector_matches), \
         patch("backend.modules.search.service.get_chunks_metadata", return_value=meta_map), \
         patch("backend.modules.search.service.search_chunks_fulltext") as mock_ft, \
         patch("backend.modules.search.routes.log_search_async"):

        res = client.post(
            "/api/search",
            json={"query": "machine learning"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        data = res.get_json()["results"]
        assert len(data) == 2
        assert data[0]["chunk_id"] == 20
        assert data[0]["score"] == 0.35
        # Fulltext fallback MUST NOT be called
        mock_ft.assert_not_called()


def test_fallback_triggered_when_vector_search_returns_empty(client, user1_token):
    """When vector search produces no matches for a user with documents, fall back to FULLTEXT."""
    fulltext_results = [
        {
            "chunk_id": 30,
            "doc_id": 1,
            "doc_title": "Paper.pdf",
            "snippet": "Keyword match snippet",
            "score": None,
        }
    ]

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[1]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors", return_value=[]), \
         patch("backend.modules.search.service.search_chunks_fulltext", return_value=fulltext_results) as mock_ft, \
         patch("backend.modules.search.routes.log_search_async"):

        res = client.post(
            "/api/search",
            json={"query": "keyword search"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        data = res.get_json()["results"]
        assert len(data) == 1
        assert data[0]["chunk_id"] == 30
        assert data[0]["score"] is None
        mock_ft.assert_called_once_with(user_id=1, query="keyword search", limit=10)


def test_fallback_zero_results_when_fulltext_finds_nothing(client, user1_token):
    """When vector search exceeds 0.75 and FULLTEXT also returns nothing, return empty list []."""
    poor_vector_matches = [{"chunk_id": 10, "doc_id": 1, "score": 0.95}]

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[1]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors", return_value=poor_vector_matches), \
         patch("backend.modules.search.service.search_chunks_fulltext", return_value=[]), \
         patch("backend.modules.search.routes.log_search_async"):

        res = client.post(
            "/api/search",
            json={"query": "non-existent text"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        assert res.get_json() == {"results": [], "cached": False}


# ============================================================================
# 2. Multi-tenant Scoping: FULLTEXT filtered to current user's documents
# ============================================================================

def test_fulltext_results_filtered_to_current_user_only(client, user1_token, user2_token):
    """AC 2: FULLTEXT results are still filtered to the current user's documents."""
    def mock_fulltext(user_id, query, limit=10, conn=None):
        if user_id == 1:
            return [{"chunk_id": 101, "doc_id": 1, "doc_title": "User1 Doc", "snippet": "User 1 text", "score": None}]
        elif user_id == 2:
            return [{"chunk_id": 201, "doc_id": 2, "doc_title": "User2 Doc", "snippet": "User 2 text", "score": None}]
        return []

    poor_vector_matches = [{"chunk_id": 99, "doc_id": 1, "score": 0.88}]

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.get_user_document_ids", side_effect=lambda u: [u]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors", return_value=poor_vector_matches), \
         patch("backend.modules.search.service.search_chunks_fulltext", side_effect=mock_fulltext), \
         patch("backend.modules.search.routes.log_search_async"):

        # User 1 search
        res1 = client.post(
            "/api/search",
            json={"query": "test query"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res1.status_code == 200
        data1 = res1.get_json()["results"]
        assert len(data1) == 1
        assert data1[0]["doc_id"] == 1
        assert data1[0]["chunk_id"] == 101

        # User 2 search
        res2 = client.post(
            "/api/search",
            json={"query": "test query"},
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert res2.status_code == 200
        data2 = res2.get_json()["results"]
        assert len(data2) == 1
        assert data2[0]["doc_id"] == 2
        assert data2[0]["chunk_id"] == 201


def test_search_chunks_fulltext_raw_sql_contract():
    """Verify raw SQL in search_chunks_fulltext joins documents and checks d.user_id and MATCH."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [
        {"chunk_id": 12, "doc_id": 4, "doc_title": "SQL Guide.pdf", "snippet": "Index scan"}
    ]

    results = search_chunks_fulltext(user_id=7, query="Index scan", limit=10, conn=mock_conn)

    assert len(results) == 1
    assert results[0]["chunk_id"] == 12
    assert results[0]["doc_id"] == 4
    assert results[0]["doc_title"] == "SQL Guide.pdf"
    assert results[0]["snippet"] == "Index scan"
    assert results[0]["score"] is None

    # Inspect executed SQL statement
    executed_sql = mock_cursor.execute.call_args[0][0]
    executed_params = mock_cursor.execute.call_args[0][1]

    assert "MATCH(c.chunk_text) AGAINST(%s IN NATURAL LANGUAGE MODE)" in executed_sql
    assert "d.user_id = %s" in executed_sql
    assert "JOIN documents d ON c.doc_id = d.doc_id" in executed_sql
    assert "LIMIT %s" in executed_sql
    assert executed_params == (7, "Index scan", 10)


def test_search_chunks_fulltext_tuple_cursor_support():
    """Verify search_chunks_fulltext works with standard tuple cursors."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # Mock TypeError on dictionary=True to simulate non-dictionary cursor
    def cursor_factory(*args, **kwargs):
        if kwargs.get("dictionary"):
            raise TypeError("dictionary cursor not supported")
        return mock_cursor

    mock_conn.cursor.side_effect = cursor_factory
    mock_cursor.fetchall.return_value = [
        (15, 6, "Guide.pdf", "Snippet text")
    ]

    results = search_chunks_fulltext(user_id=2, query="Guide", limit=5, conn=mock_conn)
    assert len(results) == 1
    assert results[0]["chunk_id"] == 15
    assert results[0]["doc_id"] == 6
    assert results[0]["doc_title"] == "Guide.pdf"
    assert results[0]["snippet"] == "Snippet text"
    assert results[0]["score"] is None


# ============================================================================
# 3. Logging Logic: Every search produces one search_log row (AC 3, 4, 5)
# ============================================================================

def test_every_search_produces_one_search_log_row(client, user1_token):
    """AC 3: Every POST /api/search call produces exactly one search_log row."""
    fake_results = [{"chunk_id": 1, "doc_id": 1, "score": 0.2}]

    with patch("backend.modules.search.routes.execute_semantic_search", return_value=(fake_results, False)), \
         patch("backend.modules.search.routes.log_search_async") as mock_log_async:

        res = client.post(
            "/api/search",
            json={"query": "operating systems"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        mock_log_async.assert_called_once_with(
            user_id=1,
            query="operating systems",
            results=fake_results,
            sync=True,
        )


def test_cache_hit_still_logs_search(client, user1_token):
    """AC 3: A search that hits cache still produces a search_log row."""
    cached_payload = [
        {"chunk_id": 10, "doc_id": 1, "doc_title": "A.pdf", "snippet": "cached", "score": 0.1}
    ]

    with patch("backend.modules.search.service.get_cached_search", return_value=cached_payload), \
         patch("backend.modules.search.routes.log_search_async") as mock_log_async:

        res = client.post(
            "/api/search",
            json={"query": "cached query"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        mock_log_async.assert_called_once_with(
            user_id=1,
            query="cached query",
            results=cached_payload,
            sync=True,
        )


def test_search_results_linked_to_search_log_with_rank_and_score():
    """AC 4: search_results rows are correctly linked to the search_log row with rank 1–10."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 42

    results = [
        {"chunk_id": 101, "score": 0.12},
        {"chunk_id": 102, "score": 0.28},
        {"chunk_id": 103, "score": None},  # from fallback
    ]

    log_id = log_search(user_id=1, query="relational databases", results=results, conn=mock_conn)

    assert log_id == 42

    # Check search_log insert
    search_log_call = mock_cursor.execute.call_args
    assert "INSERT INTO search_log" in search_log_call[0][0]
    assert search_log_call[0][1] == (1, "relational databases")

    # Check search_results executemany insert
    results_call = mock_cursor.executemany.call_args
    assert "INSERT INTO search_results" in results_call[0][0]
    inserted_records = results_call[0][1]

    assert len(inserted_records) == 3
    # Format: (log_id, chunk_id, rank, similarity_score)
    assert inserted_records[0] == (42, 101, 1, 0.12)
    assert inserted_records[1] == (42, 102, 2, 0.28)
    assert inserted_records[2] == (42, 103, 3, None)


def test_search_results_capped_at_top_10():
    """AC 4: search_results rows are linked with rank 1-10 even if results list is longer."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 88

    # Generate 15 results
    results = [{"chunk_id": i, "score": i * 0.05} for i in range(1, 16)]

    log_search(user_id=1, query="top ranks", results=results, conn=mock_conn)

    results_call = mock_cursor.executemany.call_args
    inserted_records = results_call[0][1]

    # Only top 10 results are inserted
    assert len(inserted_records) == 10
    ranks = [r[2] for r in inserted_records]
    assert ranks == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_zero_results_logs_to_search_log_without_search_results():
    """AC 5: A search that returns zero results still logs to search_log (with no search_results rows)."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 99

    log_id = log_search(user_id=1, query="empty search", results=[], conn=mock_conn)

    assert log_id == 99

    # Exactly one insert into search_log
    mock_cursor.execute.assert_called_once_with(
        "INSERT INTO search_log (user_id, query_text) VALUES (%s, %s)",
        (1, "empty search"),
    )
    # search_results executemany was NOT called
    mock_cursor.executemany.assert_not_called()


# ============================================================================
# 4. Resilience & Error Handling (AC 6)
# ============================================================================

def test_logging_failure_does_not_cause_search_response_to_fail(client, user1_token):
    """AC 6: Logging failure does not cause the search response to fail.
    
    Even if the database throws an error during logging, HTTP response is still 200.
    """
    fake_results = [{"chunk_id": 5, "doc_id": 1, "doc_title": "Doc", "snippet": "Text", "score": 0.25}]

    with patch("backend.modules.search.routes.execute_semantic_search", return_value=(fake_results, False)), \
         patch("backend.modules.search.service.insert_search_log", side_effect=Exception("Database connection lost")):

        res = client.post(
            "/api/search",
            json={"query": "test query"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        # Search response MUST NOT fail
        assert res.status_code == 200
        assert res.get_json() == {"results": fake_results, "cached": False}


def test_log_search_function_catches_all_exceptions():
    """Verify log_search suppresses exceptions and returns None on error."""
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = Exception("MySQL down")

    result = log_search(user_id=1, query="query", results=[], conn=mock_conn)
    assert result is None


# ============================================================================
# 5. Non-blocking Async Dispatch
# ============================================================================

def test_log_search_async_launches_daemon_thread():
    """AC: Logging must not block the response — dispatched in background daemon thread."""
    with patch("backend.modules.search.service.log_search") as mock_log:
        t = log_search_async(user_id=1, query="async search", results=[], sync=False)

        assert isinstance(t, threading.Thread)
        assert t.daemon is True
        t.join(timeout=2.0)
        mock_log.assert_called_once_with(1, "async search", [])
