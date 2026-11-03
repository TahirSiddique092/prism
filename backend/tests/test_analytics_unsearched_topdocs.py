"""Acceptance criteria tests for slice-15: Analytics — unsearched docs CTE and top documents view.

Acceptance criteria verified:
1. /unsearched returns only documents with zero appearances in search_results for this user
2. /top-documents returns documents ordered by appearance_count descending
3. Both endpoints return empty lists (not errors) when no data exists
4. Neither endpoint ever returns another user's documents
5. top_documents view is defined in the migration script from slice-02 (001_init.sql), not dynamically in slice-15
"""
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token
from backend.modules.analytics.db import (
    get_unsearched_documents,
    get_top_documents,
    TOP_DOCUMENTS_QUERY,
)


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

def test_unsearched_unauthenticated_returns_401(client):
    """Unauthenticated request to GET /api/analytics/unsearched returns 401."""
    res = client.get("/api/analytics/unsearched")
    assert res.status_code == 401


def test_top_documents_unauthenticated_returns_401(client):
    """Unauthenticated request to GET /api/analytics/top-documents returns 401."""
    res = client.get("/api/analytics/top-documents")
    assert res.status_code == 401


# ============================================================================
# 2. Acceptance Criterion 1: /unsearched returns zero-appearance docs for user
# ============================================================================

def test_unsearched_documents_response_structure(client, user1_token):
    """AC 1: /unsearched returns only documents with zero appearances in search_results."""
    mock_unsearched = [
        {
            "doc_id": 101,
            "title": "Machine Learning Fundamentals.pdf",
            "uploaded_at": "2026-10-10T11:00:00",
        },
        {
            "doc_id": 102,
            "title": "Compiler Design Principles.pdf",
            "uploaded_at": "2026-10-09T09:30:00",
        },
    ]

    with patch("backend.modules.analytics.routes.get_unsearched_documents", return_value=mock_unsearched) as mock_fn:
        res = client.get(
            "/api/analytics/unsearched",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 200
        mock_fn.assert_called_once_with(user_id=1)

        data = res.get_json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Required fields present
        for doc in data:
            assert "doc_id" in doc
            assert "title" in doc
            assert "uploaded_at" in doc

        assert data[0]["doc_id"] == 101
        assert data[0]["title"] == "Machine Learning Fundamentals.pdf"


def test_unsearched_documents_empty_list(client, user1_token):
    """AC 3: /unsearched returns empty list (not error) when all docs have been searched."""
    with patch("backend.modules.analytics.routes.get_unsearched_documents", return_value=[]):
        res = client.get(
            "/api/analytics/unsearched",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data == []


def test_unsearched_documents_user_scoping(client, user1_token, user2_token):
    """AC 4: Neither endpoint ever returns another user's documents."""
    user1_docs = [
        {"doc_id": 1, "title": "User1 Doc.pdf", "uploaded_at": "2026-10-10T10:00:00"}
    ]
    user2_docs = [
        {"doc_id": 2, "title": "User2 Secret.pdf", "uploaded_at": "2026-10-10T12:00:00"}
    ]

    def mock_get_unsearched(user_id):
        if user_id == 1:
            return user1_docs
        elif user_id == 2:
            return user2_docs
        return []

    with patch("backend.modules.analytics.routes.get_unsearched_documents", side_effect=mock_get_unsearched):
        # User 1
        res1 = client.get(
            "/api/analytics/unsearched",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res1.status_code == 200
        data1 = res1.get_json()
        assert len(data1) == 1
        assert data1[0]["doc_id"] == 1
        assert not any(d["doc_id"] == 2 for d in data1)

        # User 2
        res2 = client.get(
            "/api/analytics/unsearched",
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert len(data2) == 1
        assert data2[0]["doc_id"] == 2
        assert not any(d["doc_id"] == 1 for d in data2)


# ============================================================================
# 3. Acceptance Criterion 2: /top-documents ordered by appearance_count DESC
# ============================================================================

def test_top_documents_response_structure_and_ordering(client, user1_token):
    """AC 2: /top-documents returns documents ordered by appearance_count descending."""
    mock_top = [
        {
            "doc_id": 201,
            "title": "Database Systems Concepts.pdf",
            "appearance_count": 45,
            "avg_score": 0.885,
        },
        {
            "doc_id": 202,
            "title": "Distributed Systems Principles.pdf",
            "appearance_count": 22,
            "avg_score": 0.742,
        },
        {
            "doc_id": 203,
            "title": "Algorithm Design Manual.pdf",
            "appearance_count": 10,
            "avg_score": 0.691,
        },
    ]

    with patch("backend.modules.analytics.routes.get_top_documents", return_value=mock_top) as mock_fn:
        res = client.get(
            "/api/analytics/top-documents",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 200
        mock_fn.assert_called_once_with(user_id=1)

        data = res.get_json()
        assert isinstance(data, list)
        assert len(data) == 3

        for item in data:
            assert "doc_id" in item
            assert "title" in item
            assert "appearance_count" in item
            assert "avg_score" in item

        # Verify descending order
        counts = [item["appearance_count"] for item in data]
        assert counts == sorted(counts, reverse=True)
        assert data[0]["appearance_count"] == 45
        assert data[1]["appearance_count"] == 22
        assert data[2]["appearance_count"] == 10


def test_top_documents_empty_list(client, user1_token):
    """AC 3: /top-documents returns empty list (not error) when no search appearances exist."""
    with patch("backend.modules.analytics.routes.get_top_documents", return_value=[]):
        res = client.get(
            "/api/analytics/top-documents",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data == []


def test_top_documents_user_scoping(client, user1_token, user2_token):
    """AC 4: /top-documents never returns another user's documents."""
    user1_top = [
        {"doc_id": 11, "title": "User1 Top.pdf", "appearance_count": 15, "avg_score": 0.85}
    ]
    user2_top = [
        {"doc_id": 22, "title": "User2 Top.pdf", "appearance_count": 30, "avg_score": 0.92}
    ]

    def mock_get_top(user_id):
        if user_id == 1:
            return user1_top
        elif user_id == 2:
            return user2_top
        return []

    with patch("backend.modules.analytics.routes.get_top_documents", side_effect=mock_get_top):
        # User 1
        res1 = client.get(
            "/api/analytics/top-documents",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res1.status_code == 200
        data1 = res1.get_json()
        assert len(data1) == 1
        assert data1[0]["doc_id"] == 11
        assert not any(d["doc_id"] == 22 for d in data1)

        # User 2
        res2 = client.get(
            "/api/analytics/top-documents",
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert len(data2) == 1
        assert data2[0]["doc_id"] == 22
        assert not any(d["doc_id"] == 11 for d in data2)


# ============================================================================
# 4. Error Handling
# ============================================================================

def test_unsearched_db_error_returns_500(client, user1_token):
    """Graceful error response when unsearched query encounters database exception."""
    with patch("backend.modules.analytics.routes.get_unsearched_documents", side_effect=Exception("DB Error")):
        res = client.get(
            "/api/analytics/unsearched",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 500
        assert "error" in res.get_json()


def test_top_documents_db_error_returns_500(client, user1_token):
    """Graceful error response when top documents query encounters database exception."""
    with patch("backend.modules.analytics.routes.get_top_documents", side_effect=Exception("DB Error")):
        res = client.get(
            "/api/analytics/top-documents",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 500
        assert "error" in res.get_json()


# ============================================================================
# 5. Raw SQL Contract Tests
# ============================================================================

MIGRATION_008 = Path(__file__).parent.parent / "db" / "migrations" / "008_stored_procedures.sql"


def _procedure_body(name):
    """The body of a stored procedure as created by migration 008 (slice-33)."""
    sql = MIGRATION_008.read_text()
    start = sql.index(f"CREATE PROCEDURE {name}(")
    return sql[start:sql.index("END //", start)]


def _proc_conn(columns, rows):
    """A mock connection whose cursor.callproc yields one result set."""
    conn = MagicMock()
    result = MagicMock()
    result.column_names = columns
    result.fetchall.return_value = rows
    conn.cursor.return_value.stored_results.return_value = [result]
    return conn


def test_raw_sql_unsearched_docs_contract():
    """get_unsearched_documents calls sp_unsearched_documents, which holds the CTE (slice-33)."""
    mock_conn = _proc_conn(
        ("doc_id", "title", "uploaded_at"),
        [(50, "Unsearched Research Paper.pdf", datetime.datetime(2026, 10, 10, 10, 0, 0))],
    )

    docs = get_unsearched_documents(user_id=7, conn=mock_conn)

    mock_conn.cursor.return_value.callproc.assert_called_once_with("sp_unsearched_documents", (7,))

    # Verify CTE structure inside the procedure
    body = _procedure_body("sp_unsearched_documents")
    assert "WITH searched_docs AS" in body
    assert "JOIN search_log sl ON sr.log_id = sl.log_id" in body
    assert "WHERE sl.user_id = p_user_id" in body
    assert "WHERE user_id = p_user_id" in body
    assert "doc_id NOT IN (SELECT doc_id FROM searched_docs)" in body

    assert len(docs) == 1
    assert docs[0]["doc_id"] == 50
    assert docs[0]["title"] == "Unsearched Research Paper.pdf"
    assert docs[0]["uploaded_at"] == "2026-10-10T10:00:00Z"  # UTC, marked with Z (slice-25)


def test_raw_sql_unsearched_docs_maps_columns_by_name():
    """Rows are read by the procedure's column names, not their position."""
    mock_conn = _proc_conn(
        ("uploaded_at", "doc_id", "title"),
        [(datetime.datetime(2026, 10, 9, 14, 0, 0), 88, "Tuple Document.pdf")],
    )

    docs = get_unsearched_documents(user_id=1, conn=mock_conn)
    assert len(docs) == 1
    assert docs[0]["doc_id"] == 88
    assert docs[0]["title"] == "Tuple Document.pdf"
    assert "2026-10-09" in docs[0]["uploaded_at"]


def test_raw_sql_top_documents_contract():
    """Verify get_top_documents queries top_documents view with user filter, order, and limit."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [
        {
            "doc_id": 12,
            "title": "Database Normalization.pdf",
            "search_count": 4,
            "appearance_count": 18,
            "avg_score": 0.81234,
        }
    ]

    docs = get_top_documents(user_id=3, conn=mock_conn)

    mock_cursor.execute.assert_called_once()
    query_called, params_called = mock_cursor.execute.call_args[0]

    assert "FROM top_documents" in query_called
    assert "WHERE user_id = %s" in query_called
    assert "ORDER BY search_count DESC, appearance_count DESC" in query_called
    assert "LIMIT 10" in query_called
    assert params_called == (3,)

    assert len(docs) == 1
    assert docs[0]["doc_id"] == 12
    assert docs[0]["title"] == "Database Normalization.pdf"
    assert docs[0]["search_count"] == 4
    assert docs[0]["appearance_count"] == 18
    assert docs[0]["avg_score"] == 0.81234


def test_raw_sql_top_documents_tuple_fallback():
    """Verify get_top_documents works with tuple cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.side_effect = lambda dictionary=False: mock_cursor if not dictionary else (_ for _ in ()).throw(TypeError())

    # Tuple with (doc_id, title, search_count, appearance_count, avg_score, avg_similarity)
    mock_cursor.fetchall.return_value = [
        (99, "Tuple Top Doc.pdf", 3, 7, 0.75, 0.25)
    ]

    docs = get_top_documents(user_id=4, conn=mock_conn)
    assert len(docs) == 1
    assert docs[0]["doc_id"] == 99
    assert docs[0]["title"] == "Tuple Top Doc.pdf"
    assert docs[0]["search_count"] == 3
    assert docs[0]["appearance_count"] == 7
    assert docs[0]["avg_score"] == 0.75
    assert docs[0]["avg_similarity"] == 0.25  # from fn_similarity (slice-34)


# ============================================================================
# 6. Acceptance Criterion 5: top_documents view created in migration script
# ============================================================================

def test_top_documents_view_in_migration_script():
    """AC 5: top_documents view is defined in 001_init.sql, not dynamically in slice-15."""
    migration_path = Path(__file__).parent.parent / "db" / "migrations" / "001_init.sql"
    assert migration_path.exists(), "001_init.sql migration must exist"

    with open(migration_path, "r") as f:
        content = f.read()

    assert "VIEW top_documents" in content
    assert "COUNT(sr.result_id)" in content
    assert "AVG(sr.similarity_score)" in content
    assert "GROUP BY d.doc_id, d.user_id, d.title" in content
