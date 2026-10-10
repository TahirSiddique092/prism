"""Acceptance criteria tests for slice-13: Related documents via Cypher.

Acceptance criteria verified:
1. Returns up to 5 related documents ordered by number of shared topics.
2. Only returns documents belonging to the authenticated user.
3. Returns an empty list (not an error) if no related documents exist.
4. `shared_topics` count is included in the response.
5. Returns 404 if `doc_id` doesn't belong to the current user.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token
from backend.modules.graph.service import RELATED_CYPHER, get_related_documents


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
# Cypher contract (criteria 1 & 2)
# ============================================================================

def test_related_cypher_scopes_to_user_and_orders_and_limits():
    # Both source and candidate docs must be uploaded by the same user.
    assert "(u:User {user_id: $user_id})-[:UPLOADED]->(d1:Document {doc_id: $doc_id})" in RELATED_CYPHER
    assert "<-[:UPLOADED]-(u)" in RELATED_CYPHER
    # Exclude the document itself, order by shared topics desc, cap the count.
    assert "WHERE d2.doc_id <> $doc_id" in RELATED_CYPHER
    assert "COUNT(t) AS shared_topics" in RELATED_CYPHER
    assert "ORDER BY shared_topics DESC" in RELATED_CYPHER
    assert "LIMIT $limit" in RELATED_CYPHER


# ============================================================================
# Service behaviour (criteria 1, 3, 4)
# ============================================================================

def test_get_related_maps_records_with_shared_topics():
    records = [
        {"doc_id": 2, "title": "SQL Deep Dive.pdf", "shared_topics": 3},
        {"doc_id": 3, "title": "Indexing.pdf", "shared_topics": 1},
    ]
    driver, session = _mock_driver(records)
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        result = get_related_documents(doc_id=1, user_id=1)

    assert result == records  # shared_topics included, order preserved
    # query parameterised by doc_id, user_id, and default limit 5
    kwargs = session.run.call_args.kwargs
    assert kwargs == {"doc_id": 1, "user_id": 1, "limit": 5}
    assert session.run.call_args.args[0] == RELATED_CYPHER


def test_get_related_returns_empty_when_no_matches():
    driver, _ = _mock_driver([])
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        assert get_related_documents(doc_id=1, user_id=1) == []


def test_get_related_returns_empty_when_neo4j_not_configured():
    with patch("backend.modules.graph.service.get_driver", return_value=None):
        assert get_related_documents(doc_id=1, user_id=1) == []


def test_get_related_is_graceful_when_session_raises():
    driver = MagicMock()
    driver.session.side_effect = Exception("neo4j down")
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        assert get_related_documents(doc_id=1, user_id=1) == []


# ============================================================================
# Endpoint (criteria 2, 3, 5)
# ============================================================================

def test_related_endpoint_returns_related_docs(client, user1_token):
    related = [
        {"doc_id": 2, "title": "SQL Deep Dive.pdf", "shared_topics": 3},
        {"doc_id": 3, "title": "Indexing.pdf", "shared_topics": 2},
    ]
    with patch("backend.modules.documents.routes.get_document_by_id", return_value={"doc_id": 1, "user_id": 1}), \
         patch("backend.modules.documents.routes.get_related_documents", return_value=related) as mock_related:

        res = client.get(
            "/api/documents/1/related",
            headers={"Authorization": f"Bearer {user1_token}"},
        )

    assert res.status_code == 200
    assert res.get_json() == related
    # Scoped to the authenticated user
    mock_related.assert_called_once_with(1, 1)


def test_related_endpoint_404_when_doc_not_owned(client, user1_token):
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=None), \
         patch("backend.modules.documents.routes.get_related_documents") as mock_related:

        res = client.get(
            "/api/documents/999/related",
            headers={"Authorization": f"Bearer {user1_token}"},
        )

    assert res.status_code == 404
    # Must not query the graph for a doc the user doesn't own
    mock_related.assert_not_called()


def test_related_endpoint_returns_empty_list_not_error(client, user1_token):
    with patch("backend.modules.documents.routes.get_document_by_id", return_value={"doc_id": 1, "user_id": 1}), \
         patch("backend.modules.documents.routes.get_related_documents", return_value=[]):

        res = client.get(
            "/api/documents/1/related",
            headers={"Authorization": f"Bearer {user1_token}"},
        )

    assert res.status_code == 200
    assert res.get_json() == []


def test_related_endpoint_requires_auth(client):
    res = client.get("/api/documents/1/related")
    assert res.status_code == 401
