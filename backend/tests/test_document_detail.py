"""Acceptance criteria tests for slice-20: Document detail metadata + topics.

The frontend document-detail page (`/documents/:doc_id`) needs a single
endpoint that returns a document's metadata, chunk count, and topic tags. Topics
live only in Neo4j (the MySQL `doc_topics` table is never populated), so the
endpoint reads them from the graph and must degrade gracefully when Neo4j is
unavailable.

Criteria verified here (the backend half of the slice):
1. GET /api/documents/:doc_id returns title, uploaded_at, status, chunk_count, topics.
2. Returns 404 if the doc doesn't belong to the current user — and never reads the graph.
3. Requires authentication (401 without a token).
4. Topics come from Neo4j scoped to the user, in a stable order.
5. A down/empty Neo4j yields topics: [] (not an error).
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token
from backend.modules.graph.service import DOCUMENT_TOPICS_CYPHER, get_document_topics


@pytest.fixture
def app():
    return create_app({"TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user1_token():
    return generate_token(user_id=1, email="user1@example.com")


def _mock_driver(records):
    """A Neo4j driver whose session.run yields the given record dicts."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.run.return_value = iter(records)
    return driver, session


# ============================================================================
# Cypher contract (criterion 4)
# ============================================================================

def test_document_topics_cypher_scopes_to_user_and_orders():
    # The document must be UPLOADED by the authenticated user.
    assert "(u:User {user_id: $user_id})-[:UPLOADED]->(d:Document {doc_id: $doc_id})" in DOCUMENT_TOPICS_CYPHER
    assert "-[:ABOUT]->(t:Topic)" in DOCUMENT_TOPICS_CYPHER
    assert "RETURN t.name AS name" in DOCUMENT_TOPICS_CYPHER
    assert "ORDER BY t.name" in DOCUMENT_TOPICS_CYPHER


# ============================================================================
# get_document_topics service behaviour (criteria 4 & 5)
# ============================================================================

def test_get_document_topics_returns_names():
    records = [{"name": "indexing"}, {"name": "normalization"}]
    driver, session = _mock_driver(records)
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        result = get_document_topics(doc_id=1, user_id=1)

    assert result == ["indexing", "normalization"]
    kwargs = session.run.call_args.kwargs
    assert kwargs == {"doc_id": 1, "user_id": 1}
    assert session.run.call_args.args[0] == DOCUMENT_TOPICS_CYPHER


def test_get_document_topics_empty_when_no_topics():
    driver, _ = _mock_driver([])
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        assert get_document_topics(doc_id=1, user_id=1) == []


def test_get_document_topics_empty_when_neo4j_not_configured():
    with patch("backend.modules.graph.service.get_driver", return_value=None):
        assert get_document_topics(doc_id=1, user_id=1) == []


def test_get_document_topics_graceful_when_session_raises():
    driver = MagicMock()
    driver.session.side_effect = Exception("neo4j down")
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        assert get_document_topics(doc_id=1, user_id=1) == []


# ============================================================================
# Endpoint (criteria 1, 2, 3, 5)
# ============================================================================

def test_detail_endpoint_requires_auth(client):
    res = client.get("/api/documents/1")
    assert res.status_code == 401


def test_detail_endpoint_returns_metadata_and_topics(client, user1_token):
    doc = {
        "doc_id": 1,
        "user_id": 1,
        "title": "Database Indexing.pdf",
        "minio_key": "1/abc.pdf",
        "uploaded_at": "2026-10-10T14:00:00",
        "status": "ready",
    }
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=doc), \
         patch("backend.modules.documents.routes.get_document_chunk_count", return_value=14), \
         patch("backend.modules.documents.routes.get_document_topics", return_value=["indexing", "normalization"]) as mock_topics:

        res = client.get(
            "/api/documents/1",
            headers={"Authorization": f"Bearer {user1_token}"},
        )

    assert res.status_code == 200
    body = res.get_json()
    assert body == {
        "doc_id": 1,
        "title": "Database Indexing.pdf",
        "uploaded_at": "2026-10-10T14:00:00",
        "status": "ready",
        "chunk_count": 14,
        "topics": ["indexing", "normalization"],
    }
    # Topics are scoped to the authenticated user.
    mock_topics.assert_called_once_with(1, 1)


def test_detail_endpoint_404_when_doc_not_owned(client, user1_token):
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=None), \
         patch("backend.modules.documents.routes.get_document_chunk_count") as mock_count, \
         patch("backend.modules.documents.routes.get_document_topics") as mock_topics:

        res = client.get(
            "/api/documents/999",
            headers={"Authorization": f"Bearer {user1_token}"},
        )

    assert res.status_code == 404
    # Must not touch chunks or the graph for a doc the user doesn't own.
    mock_count.assert_not_called()
    mock_topics.assert_not_called()


def test_detail_endpoint_topics_empty_is_not_an_error(client, user1_token):
    doc = {
        "doc_id": 2,
        "user_id": 1,
        "title": "Untagged.pdf",
        "minio_key": "1/def.pdf",
        "uploaded_at": "2026-10-11T09:00:00",
        "status": "processing",
    }
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=doc), \
         patch("backend.modules.documents.routes.get_document_chunk_count", return_value=0), \
         patch("backend.modules.documents.routes.get_document_topics", return_value=[]):

        res = client.get(
            "/api/documents/2",
            headers={"Authorization": f"Bearer {user1_token}"},
        )

    assert res.status_code == 200
    body = res.get_json()
    assert body["topics"] == []
    assert body["chunk_count"] == 0
    assert body["status"] == "processing"
