"""Acceptance criteria tests for slice-12: Neo4j topic graph on upload.

Acceptance criteria verified:
1. Uploading a document with topics creates Topic nodes and [:ABOUT] relationships.
2. MERGE is used for User and Topic nodes — no duplicates on repeated uploads.
3. (User)-[:UPLOADED]->(Document) relationship is created on every upload.
4. Topic names are stored lowercase and trimmed — "Normalization" == "normalization".
5. If Neo4j is unreachable, the upload still succeeds (graph failure is logged,
   never blocks or fails the response).
"""
import io
from unittest.mock import MagicMock, patch

import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token
from backend.modules.graph.service import (
    WRITE_CYPHER,
    normalize_topics,
    sync_document_to_graph,
)


@pytest.fixture
def app():
    # GRAPH_WRITE_SYNC makes the upload's graph write run inline for assertions.
    return create_app({"TESTING": True, "GRAPH_WRITE_SYNC": True})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user1_token():
    return generate_token(user_id=1, email="user1@example.com")


def _pdf_upload(topics=None):
    """Build multipart form data for a fake PDF upload."""
    data = {"file": (io.BytesIO(b"%PDF-1.4 fake pdf bytes"), "doc.pdf", "application/pdf")}
    if topics is not None:
        data["topics"] = topics
    return data


def _mock_driver():
    """A Neo4j driver whose session is a context manager exposing `.run`."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return driver, session


# ============================================================================
# Unit tests: normalization (criterion 4)
# ============================================================================

def test_normalize_topics_lowercases_and_trims():
    assert normalize_topics(["Normalization", "  SQL  "]) == ["normalization", "sql"]


def test_normalize_topics_dedupes_case_insensitively():
    # "Normalization" and "normalization" collapse to one node
    assert normalize_topics(["Normalization", "normalization", "SQL"]) == ["normalization", "sql"]


def test_normalize_topics_drops_empty_and_nonstrings():
    assert normalize_topics(["SQL", "", "   ", None, 5, "Joins"]) == ["sql", "joins"]


def test_normalize_topics_handles_none():
    assert normalize_topics(None) == []


# ============================================================================
# Cypher contract (criteria 2 & 3)
# ============================================================================

def test_write_cypher_uses_merge_for_user_and_topic():
    assert "MERGE (u:User {user_id: $user_id})" in WRITE_CYPHER
    assert "MERGE (t:Topic {name: topic_name})" in WRITE_CYPHER


def test_write_cypher_creates_uploaded_and_about_relationships():
    assert "MERGE (u)-[:UPLOADED]->(d)" in WRITE_CYPHER
    assert "MERGE (d)-[:ABOUT]->(t)" in WRITE_CYPHER


# ============================================================================
# Service behaviour
# ============================================================================

def test_sync_passes_normalized_topics_to_neo4j():
    driver, session = _mock_driver()
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        ok = sync_document_to_graph(
            user_id=1, email="a@b.com", doc_id=7, title="Doc.pdf",
            topics=["Normalization", "normalization", " SQL "],
        )

    assert ok is True
    session.run.assert_called_once()
    kwargs = session.run.call_args.kwargs
    assert kwargs["topics"] == ["normalization", "sql"]
    assert kwargs["user_id"] == 1
    assert kwargs["doc_id"] == 7
    assert kwargs["email"] == "a@b.com"
    assert kwargs["title"] == "Doc.pdf"
    # Cypher sent is the write statement
    assert session.run.call_args.args[0] == WRITE_CYPHER


def test_sync_runs_write_even_with_no_topics():
    """User/Document/UPLOADED must still be written when a doc has no topics."""
    driver, session = _mock_driver()
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        ok = sync_document_to_graph(
            user_id=1, email="a@b.com", doc_id=8, title="NoTopics.pdf", topics=[],
        )

    assert ok is True
    session.run.assert_called_once()
    assert session.run.call_args.kwargs["topics"] == []


def test_sync_returns_false_when_neo4j_not_configured():
    with patch("backend.modules.graph.service.get_driver", return_value=None):
        assert sync_document_to_graph(1, "a@b.com", 9, "D.pdf", ["sql"]) is False


def test_sync_is_graceful_when_session_raises():
    driver = MagicMock()
    driver.session.side_effect = Exception("connection refused")
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        # Must not raise
        assert sync_document_to_graph(1, "a@b.com", 9, "D.pdf", ["sql"]) is False


# ============================================================================
# Upload integration (criteria 1, 4, 5)
# ============================================================================

def _patch_upload_side_effects():
    """Patch MinIO, MySQL, cache, and the background chunking thread so the
    upload test isolates graph behaviour. The graph write runs inline (step 6)
    before chunking (step 7), so stubbing the thread doesn't affect it."""
    return [
        patch("backend.modules.documents.routes.upload_file"),
        patch("backend.modules.documents.routes.insert_document", return_value=42),
        patch("backend.modules.documents.routes.invalidate_user_cache"),
        patch("threading.Thread"),
    ]


def test_upload_with_topics_writes_graph(client, user1_token):
    """Criterion 1: uploading with topics drives the Neo4j write with normalized topics."""
    driver, session = _mock_driver()
    patches = _patch_upload_side_effects()
    for p in patches:
        p.start()
    try:
        with patch("backend.modules.graph.service.get_driver", return_value=driver):
            res = client.post(
                "/api/documents/upload",
                data=_pdf_upload(topics=["Normalization", "SQL"]),
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {user1_token}"},
            )
    finally:
        for p in patches:
            p.stop()

    assert res.status_code == 201
    session.run.assert_called_once()
    kwargs = session.run.call_args.kwargs
    assert kwargs["doc_id"] == 42
    assert kwargs["user_id"] == 1
    assert kwargs["email"] == "user1@example.com"
    assert kwargs["topics"] == ["normalization", "sql"]


def test_upload_succeeds_when_neo4j_unreachable(client, user1_token):
    """Criterion 5: a graph failure must not fail the upload."""
    patches = _patch_upload_side_effects()
    for p in patches:
        p.start()
    try:
        with patch(
            "backend.modules.graph.service.get_driver",
            side_effect=Exception("neo4j down"),
        ):
            res = client.post(
                "/api/documents/upload",
                data=_pdf_upload(topics=["SQL"]),
                content_type="multipart/form-data",
                headers={"Authorization": f"Bearer {user1_token}"},
            )
    finally:
        for p in patches:
            p.stop()

    # Upload still succeeds despite the graph failure
    assert res.status_code == 201
    assert res.get_json()["doc_id"] == 42
