"""Acceptance criteria tests for slice-14: Analytics — search history with window functions.

Acceptance criteria verified:
1. Response includes query_text, search_count, query_rank, last_searched, total_searches
2. Queries are ranked correctly — most searched query has rank 1
3. total_searches is the same across all rows (it's a grand total)
4. Returns an empty list if the user has no search history
5. Only returns the current user's queries — never another user's
"""
import datetime
from unittest.mock import MagicMock, patch
import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token
from backend.modules.analytics.db import get_search_history, SEARCH_HISTORY_QUERY


@pytest.fixture
def app():
    """Create test application."""
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
# 1. Authentication & Route Accessibility
# ============================================================================

def test_search_history_unauthenticated_returns_401(client):
    """Unauthenticated request to GET /api/analytics/history returns 401."""
    res = client.get("/api/analytics/history")
    assert res.status_code == 401


# ============================================================================
# 2. Acceptance Criteria 1, 2, 3: Structure, Ranking, and Grand Total
# ============================================================================

def test_search_history_response_structure_and_ranking(client, user1_token):
    """AC 1, 2, 3: Returns ranked search history with window functions.
    
    - Fields: query_text, search_count, query_rank, last_searched, total_searches
    - Query rank 1 for highest search_count
    - total_searches identical across all rows
    """
    mock_history = [
        {
            "query_text": "relational database normalization",
            "search_count": 10,
            "query_rank": 1,
            "last_searched": "2026-10-10T15:30:00",
            "total_searches": 18,
        },
        {
            "query_text": "b-tree indexing strategies",
            "search_count": 5,
            "query_rank": 2,
            "last_searched": "2026-10-09T11:00:00",
            "total_searches": 18,
        },
        {
            "query_text": "concurrency control two phase locking",
            "search_count": 3,
            "query_rank": 3,
            "last_searched": "2026-10-08T09:15:00",
            "total_searches": 18,
        },
    ]

    with patch("backend.modules.analytics.routes.get_search_history", return_value=mock_history) as mock_fn:
        res = client.get(
            "/api/analytics/history",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 200
        mock_fn.assert_called_once_with(user_id=1)

        data = res.get_json()
        assert isinstance(data, list)
        assert len(data) == 3

        # AC 1: All required fields present
        for row in data:
            assert "query_text" in row
            assert "search_count" in row
            assert "query_rank" in row
            assert "last_searched" in row
            assert "total_searches" in row

        # AC 2: Queries are ranked correctly — most searched query has rank 1
        assert data[0]["query_text"] == "relational database normalization"
        assert data[0]["query_rank"] == 1
        assert data[0]["search_count"] == 10
        assert data[1]["query_rank"] == 2
        assert data[2]["query_rank"] == 3

        # AC 3: total_searches is the same across all rows (grand total)
        assert data[0]["total_searches"] == 18
        assert data[1]["total_searches"] == 18
        assert data[2]["total_searches"] == 18


def test_search_history_handles_ties_with_rank(client, user1_token):
    """SQL RANK() assigns identical rank to tied query counts."""
    mock_history = [
        {
            "query_text": "query A",
            "search_count": 5,
            "query_rank": 1,
            "last_searched": "2026-10-10T12:00:00",
            "total_searches": 12,
        },
        {
            "query_text": "query B",
            "search_count": 5,
            "query_rank": 1,
            "last_searched": "2026-10-10T11:00:00",
            "total_searches": 12,
        },
        {
            "query_text": "query C",
            "search_count": 2,
            "query_rank": 3,
            "last_searched": "2026-10-09T08:00:00",
            "total_searches": 12,
        },
    ]

    with patch("backend.modules.analytics.routes.get_search_history", return_value=mock_history):
        res = client.get(
            "/api/analytics/history",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert len(data) == 3
        assert data[0]["query_rank"] == 1
        assert data[1]["query_rank"] == 1
        assert data[2]["query_rank"] == 3


# ============================================================================
# 3. Acceptance Criterion 4: Empty list when no search history
# ============================================================================

def test_search_history_empty_returns_empty_list(client, user1_token):
    """AC 4: Returns an empty list if the user has no search history (status 200)."""
    with patch("backend.modules.analytics.routes.get_search_history", return_value=[]):
        res = client.get(
            "/api/analytics/history",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data == []


# ============================================================================
# 4. Acceptance Criterion 5: User Scoping Isolation
# ============================================================================

def test_search_history_user_scoping_isolation(client, user1_token, user2_token):
    """AC 5: Only returns the current user's queries — never another user's."""
    user1_history = [
        {
            "query_text": "user 1 unique query",
            "search_count": 4,
            "query_rank": 1,
            "last_searched": "2026-10-10T10:00:00",
            "total_searches": 4,
        }
    ]
    user2_history = [
        {
            "query_text": "user 2 confidential query",
            "search_count": 7,
            "query_rank": 1,
            "last_searched": "2026-10-10T14:00:00",
            "total_searches": 7,
        }
    ]

    def mock_get_history(user_id):
        if user_id == 1:
            return user1_history
        elif user_id == 2:
            return user2_history
        return []

    with patch("backend.modules.analytics.routes.get_search_history", side_effect=mock_get_history):
        # User 1 request
        res1 = client.get(
            "/api/analytics/history",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res1.status_code == 200
        data1 = res1.get_json()
        assert len(data1) == 1
        assert data1[0]["query_text"] == "user 1 unique query"
        assert not any(d["query_text"] == "user 2 confidential query" for d in data1)

        # User 2 request
        res2 = client.get(
            "/api/analytics/history",
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert len(data2) == 1
        assert data2[0]["query_text"] == "user 2 confidential query"
        assert not any(d["query_text"] == "user 1 unique query" for d in data2)


# ============================================================================
# 5. Error Handling
# ============================================================================

def test_search_history_db_error_returns_500(client, user1_token):
    """Graceful error response when DB operation raises an exception."""
    with patch("backend.modules.analytics.routes.get_search_history", side_effect=Exception("DB connection error")):
        res = client.get(
            "/api/analytics/history",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 500
        data = res.get_json()
        assert "error" in data


# ============================================================================
# 6. Raw SQL Window Function Contract Tests
# ============================================================================

def test_raw_sql_search_history_contract():
    """Verify get_search_history query contains exact window functions and parameter binding."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Simulate dictionary cursor rows
    mock_cursor.fetchall.return_value = [
        {
            "query_text": "postgresql pgvector",
            "search_count": 8,
            "query_rank": 1,
            "last_searched": datetime.datetime(2026, 10, 10, 14, 20, 0),
            "total_searches": 12,
        },
        {
            "query_text": "mysql transactions",
            "search_count": 4,
            "query_rank": 2,
            "last_searched": datetime.datetime(2026, 10, 9, 10, 15, 0),
            "total_searches": 12,
        },
    ]

    history = get_search_history(user_id=42, conn=mock_conn)

    # 1. SQL query assertions
    mock_cursor.execute.assert_called_once()
    query_called, params_called = mock_cursor.execute.call_args[0]

    assert "FROM search_log" in query_called
    assert "WHERE user_id = %s" in query_called
    assert "GROUP BY query_text" in query_called
    assert "RANK() OVER (ORDER BY COUNT(*) DESC)" in query_called
    assert "SUM(COUNT(*)) OVER ()" in query_called
    assert "ORDER BY query_rank" in query_called
    assert params_called == (42,)

    # 2. Result mapping assertions
    assert len(history) == 2
    assert history[0]["query_text"] == "postgresql pgvector"
    assert history[0]["search_count"] == 8
    assert history[0]["query_rank"] == 1
    assert history[0]["last_searched"] == "2026-10-10T14:20:00"
    assert history[0]["total_searches"] == 12

    assert history[1]["query_text"] == "mysql transactions"
    assert history[1]["search_count"] == 4
    assert history[1]["query_rank"] == 2
    assert history[1]["last_searched"] == "2026-10-09T10:15:00"
    assert history[1]["total_searches"] == 12


def test_raw_sql_search_history_tuple_cursor_fallback():
    """Verify get_search_history works correctly with tuple cursor format."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # Simulate cursor without dictionary support
    mock_conn.cursor.side_effect = lambda dictionary=False: mock_cursor if not dictionary else (_ for _ in ()).throw(TypeError())

    mock_cursor.fetchall.return_value = [
        (
            "acid properties",
            3,
            1,
            datetime.datetime(2026, 10, 8, 16, 45, 0),
            3,
        )
    ]

    history = get_search_history(user_id=99, conn=mock_conn)

    assert len(history) == 1
    assert history[0]["query_text"] == "acid properties"
    assert history[0]["search_count"] == 3
    assert history[0]["query_rank"] == 1
    assert history[0]["last_searched"] == "2026-10-08T16:45:00"
    assert history[0]["total_searches"] == 3


def test_raw_sql_search_history_empty_db_result():
    """Verify get_search_history returns empty list when MySQL returns 0 rows."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = []

    history = get_search_history(user_id=10, conn=mock_conn)

    assert history == []
