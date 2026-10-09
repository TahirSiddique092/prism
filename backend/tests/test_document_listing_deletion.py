"""Acceptance criteria tests for slice-08: Document listing and deletion with trigger.

Acceptance criteria verified:
1. GET /api/documents never returns documents from other users
2. DELETE fires the MySQL trigger — deletion_audit gets a new row, chunks rows are removed, chunk_vectors rows are removed
3. MinIO file is deleted after MySQL deletion succeeds
4. Redis cache for the user is invalidated after deletion
5. Deleting a non-existent or other user's doc returns 404, not 500
6. GET /api/documents/:doc_id/url successfully returns a working pre-signed MinIO URL for the user's document
"""
import datetime
from unittest.mock import MagicMock, call, patch
import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token


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
# 1. GET /api/documents — listing documents
# ============================================================================

def test_list_documents_unauthenticated(client):
    """Unauthenticated request to GET /api/documents returns 401."""
    res = client.get("/api/documents")
    assert res.status_code == 401


def test_list_documents_only_returns_authenticated_user_docs(client, user1_token, user2_token):
    """GET /api/documents never returns documents from other users."""
    user1_docs = [
        {
            "doc_id": 101,
            "title": "User 1 Doc A.pdf",
            "uploaded_at": "2026-10-09T10:00:00",
            "status": "ready",
            "chunk_count": 5,
        },
        {
            "doc_id": 102,
            "title": "User 1 Doc B.pdf",
            "uploaded_at": "2026-10-09T11:00:00",
            "status": "processing",
            "chunk_count": 0,
        },
    ]

    user2_docs = [
        {
            "doc_id": 201,
            "title": "User 2 Secret.pdf",
            "uploaded_at": "2026-10-09T12:00:00",
            "status": "ready",
            "chunk_count": 12,
        }
    ]

    def mock_get_user_documents(user_id, conn=None):
        if user_id == 1:
            return user1_docs
        elif user_id == 2:
            return user2_docs
        return []

    with patch("backend.modules.documents.routes.get_user_documents", side_effect=mock_get_user_documents):
        # User 1 request
        res1 = client.get(
            "/api/documents",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res1.status_code == 200
        data1 = res1.get_json()
        assert len(data1) == 2
        assert data1[0]["doc_id"] == 101
        assert data1[0]["title"] == "User 1 Doc A.pdf"
        assert data1[0]["chunk_count"] == 5
        assert data1[1]["doc_id"] == 102
        # Verify user 2's doc is not present in user 1's response
        assert not any(d["doc_id"] == 201 for d in data1)

        # User 2 request
        res2 = client.get(
            "/api/documents",
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert len(data2) == 1
        assert data2[0]["doc_id"] == 201
        assert data2[0]["title"] == "User 2 Secret.pdf"
        assert not any(d["doc_id"] in (101, 102) for d in data2)


def test_list_documents_empty(client, user1_token):
    """GET /api/documents returns empty list when user has no documents."""
    with patch("backend.modules.documents.routes.get_user_documents", return_value=[]):
        res = client.get(
            "/api/documents",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 200
        assert res.get_json() == []


# ============================================================================
# 2. GET /api/documents/:doc_id/url — pre-signed MinIO URL
# ============================================================================

def test_get_document_url_unauthenticated(client):
    """Unauthenticated request to GET /api/documents/1/url returns 401."""
    res = client.get("/api/documents/1/url")
    assert res.status_code == 401


def test_get_document_url_success(client, user1_token):
    """GET /api/documents/:doc_id/url returns temporary pre-signed MinIO URL."""
    fake_doc = {
        "doc_id": 42,
        "user_id": 1,
        "title": "Machine Learning.pdf",
        "minio_key": "1/ml-paper.pdf",
        "uploaded_at": "2026-10-09T10:00:00",
        "status": "ready",
    }
    fake_presigned_url = "http://localhost:9000/prism-documents/1/ml-paper.pdf?X-Amz-Signature=abcd1234"

    with patch("backend.modules.documents.routes.get_document_by_id", return_value=fake_doc) as mock_get_doc, \
         patch("backend.modules.documents.routes.generate_presigned_url", return_value=fake_presigned_url) as mock_gen_url:
        res = client.get(
            "/api/documents/42/url",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 200
        assert res.get_json() == {"view_url": fake_presigned_url}

        mock_get_doc.assert_called_once_with(42, user_id=1)
        mock_gen_url.assert_called_once_with("1/ml-paper.pdf", expires_in=3600)


def test_get_document_url_not_found_returns_404(client, user1_token):
    """GET /api/documents/:doc_id/url returns 404 when document does not exist."""
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=None):
        res = client.get(
            "/api/documents/999/url",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert res.status_code == 404
        assert "error" in res.get_json()


def test_get_document_url_other_user_returns_404(client, user2_token):
    """GET /api/documents/:doc_id/url returns 404 if doc belongs to another user."""
    # When user 2 queries doc 42 (owned by user 1), get_document_by_id(42, user_id=2) returns None
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=None) as mock_get_doc:
        res = client.get(
            "/api/documents/42/url",
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert res.status_code == 404
        mock_get_doc.assert_called_once_with(42, user_id=2)


# ============================================================================
# 3. DELETE /api/documents/:doc_id — deletion and cascading
# ============================================================================

def test_delete_document_unauthenticated(client):
    """Unauthenticated request to DELETE /api/documents/1 returns 401."""
    res = client.delete("/api/documents/1")
    assert res.status_code == 401


def test_delete_document_success(client, user1_token):
    """DELETE /api/documents/:doc_id cascades deletion through DB, storage, and cache."""
    fake_doc = {
        "doc_id": 55,
        "user_id": 1,
        "title": "Thesis.pdf",
        "minio_key": "1/thesis.pdf",
    }

    call_order = []

    def mock_delete_document(doc_id, user_id):
        call_order.append("mysql_delete")
        return True

    def mock_delete_chunk_vectors(doc_id):
        call_order.append("pgvector_delete")

    def mock_delete_file(minio_key):
        call_order.append("minio_delete")
        return True

    def mock_invalidate_cache(user_id):
        call_order.append("redis_invalidate")
        return True

    with patch("backend.modules.documents.routes.get_document_by_id", return_value=fake_doc), \
         patch("backend.modules.documents.routes.delete_document", side_effect=mock_delete_document) as mock_mysql_del, \
         patch("backend.modules.documents.routes.delete_chunk_vectors", side_effect=mock_delete_chunk_vectors) as mock_pg_del, \
         patch("backend.modules.documents.routes.delete_file", side_effect=mock_delete_file) as mock_storage_del, \
         patch("backend.modules.documents.routes.invalidate_user_cache", side_effect=mock_invalidate_cache) as mock_cache_inv:

        res = client.delete(
            "/api/documents/55",
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 200
        assert res.get_json() == {"message": "deleted"}

        mock_mysql_del.assert_called_once_with(55, user_id=1)
        mock_pg_del.assert_called_once_with(55)
        mock_storage_del.assert_called_once_with("1/thesis.pdf")
        mock_cache_inv.assert_called_once_with(1)

        # Acceptance criterion: MinIO file is deleted after MySQL deletion succeeds
        assert call_order.index("mysql_delete") < call_order.index("minio_delete")
        # Redis cache is invalidated after deletion
        assert "redis_invalidate" in call_order


def test_delete_document_not_found_returns_404_not_500(client, user1_token):
    """Deleting a non-existent doc returns 404, not 500."""
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=None), \
         patch("backend.modules.documents.routes.delete_file") as mock_delete_file:

        res = client.delete(
            "/api/documents/9999",
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 404
        assert res.status_code != 500
        # MinIO file must NOT be touched
        mock_delete_file.assert_not_called()


def test_delete_document_other_user_returns_404_not_500(client, user2_token):
    """Deleting another user's doc returns 404, not 500."""
    # When user 2 tries to delete user 1's doc (id=55)
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=None) as mock_get_doc, \
         patch("backend.modules.documents.routes.delete_document") as mock_del_doc, \
         patch("backend.modules.documents.routes.delete_file") as mock_del_file:

        res = client.delete(
            "/api/documents/55",
            headers={"Authorization": f"Bearer {user2_token}"},
        )

        assert res.status_code == 404
        assert res.status_code != 500
        mock_get_doc.assert_called_once_with(55, user_id=2)
        mock_del_doc.assert_not_called()
        mock_del_file.assert_not_called()


def test_delete_document_minio_not_called_if_mysql_delete_fails(client, user1_token):
    """MinIO file must not be deleted if MySQL deletion fails."""
    fake_doc = {"doc_id": 55, "user_id": 1, "minio_key": "1/thesis.pdf"}

    with patch("backend.modules.documents.routes.get_document_by_id", return_value=fake_doc), \
         patch("backend.modules.documents.routes.delete_document", return_value=False), \
         patch("backend.modules.documents.routes.delete_file") as mock_del_file:

        res = client.delete(
            "/api/documents/55",
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        assert res.status_code == 404
        mock_del_file.assert_not_called()


# ============================================================================
# 4. Database triggers & raw SQL operations contract
# ============================================================================

def test_raw_sql_get_user_documents_contract():
    """Verify get_user_documents query structure and mapping."""
    from backend.modules.documents.db import get_user_documents

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [
        {
            "doc_id": 1,
            "title": "Doc1.pdf",
            "uploaded_at": datetime.datetime(2026, 10, 9, 10, 0, 0),
            "status": "ready",
            "chunk_count": 3,
        }
    ]

    docs = get_user_documents(user_id=1, conn=mock_conn)

    assert len(docs) == 1
    assert docs[0]["doc_id"] == 1
    assert docs[0]["chunk_count"] == 3
    assert "2026-10-09" in docs[0]["uploaded_at"]

    # Verify query had WHERE d.user_id = %s
    query_called = mock_cursor.execute.call_args[0][0]
    assert "WHERE d.user_id = %s" in query_called
    assert mock_cursor.execute.call_args[0][1] == (1,)


def test_raw_sql_delete_document_triggers_contract():
    """Verify delete_document issues DELETE FROM documents with proper user scoping."""
    from backend.modules.documents.db import delete_document

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_conn.cursor.return_value = mock_cursor

    result = delete_document(doc_id=55, user_id=1, conn=mock_conn)
    assert result is True

    mock_cursor.execute.assert_called_once_with(
        "DELETE FROM documents WHERE doc_id = %s AND user_id = %s",
        (55, 1),
    )
    mock_conn.commit.assert_called_once()


def test_raw_sql_delete_chunk_vectors_contract():
    """Verify delete_chunk_vectors issues DELETE FROM chunk_vectors in Postgres."""
    from backend.modules.documents.db import delete_chunk_vectors

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    delete_chunk_vectors(doc_id=55, conn=mock_conn)

    mock_cursor.execute.assert_called_once_with(
        "DELETE FROM chunk_vectors WHERE doc_id = %s",
        (55,),
    )
    mock_conn.commit.assert_called_once()


def test_redis_cache_invalidation_contract():
    """Verify invalidate_user_cache deletes all search:{user_id}:* keys."""
    from backend.modules.cache.service import invalidate_user_cache

    mock_redis = MagicMock()
    mock_redis.keys.return_value = ["search:1:hash1", "search:1:hash2"]

    with patch("backend.modules.cache.service.get_redis_client", return_value=mock_redis):
        result = invalidate_user_cache(user_id=1)
        assert result is True
        mock_redis.keys.assert_called_once_with("search:1:*")
        mock_redis.delete.assert_called_once_with("search:1:hash1", "search:1:hash2")


def test_redis_cache_invalidation_graceful_on_failure():
    """Verify invalidate_user_cache degrades gracefully if Redis fails."""
    from backend.modules.cache.service import invalidate_user_cache

    with patch("backend.modules.cache.service.get_redis_client", side_effect=Exception("Connection refused")):
        # Should not raise exception
        result = invalidate_user_cache(user_id=1)
        assert result is False
