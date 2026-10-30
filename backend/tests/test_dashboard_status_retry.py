"""Slice 28: retry failed documents, and recover ones stuck in 'processing'.

1. POST /api/documents/:doc_id/retry reprocesses an 'error' document of the
   user: 202, after clearing its old chunks and vectors; 409 otherwise
2. claim_for_retry changes the status in one conditional UPDATE, so two
   retries can't both start
3. When the server starts, documents left 'processing' become 'error';
   importing the app never does this

Unit tests use mocks. The integration test at the bottom is opt-in
(PRISM_MYSQL_INTEGRATION=1 plus MYSQL_URL) and only touches a TEMPORARY table.
"""
import os
import runpy
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token
from backend.modules.documents.db import claim_for_retry, mark_interrupted_processing_failed

ROUTES = "backend.modules.documents.routes"
ERROR_DOC = {"doc_id": 2, "user_id": 1, "title": "b.pdf", "minio_key": "1/b.pdf", "status": "error"}


@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture
def auth_header():
    return {"Authorization": f"Bearer {generate_token(user_id=1, email='user1@example.com')}"}


def _retry(client, auth_header, doc=ERROR_DOC, claimed=True, clear_error=None, start_error=None):
    steps = MagicMock()
    steps.delete_chunk_vectors.side_effect = clear_error
    steps.start_processing.side_effect = start_error
    with patch(f"{ROUTES}.get_document_by_id", return_value=doc), \
         patch(f"{ROUTES}.claim_for_retry", return_value=claimed) as claim, \
         patch(f"{ROUTES}.delete_chunk_vectors", steps.delete_chunk_vectors), \
         patch(f"{ROUTES}.delete_chunks", steps.delete_chunks), \
         patch(f"{ROUTES}.invalidate_user_cache", steps.invalidate_user_cache), \
         patch(f"{ROUTES}.start_processing", steps.start_processing), \
         patch(f"{ROUTES}.update_document_status", steps.update_document_status):
        res = client.post("/api/documents/2/retry", headers=auth_header)
    return res, claim, steps


# ============================================================================
# 1. Retry route
# ============================================================================

def test_retry_clears_old_data_then_processes_again(client, auth_header):
    res, claim, steps = _retry(client, auth_header)

    assert res.status_code == 202
    assert res.get_json() == {"doc_id": 2, "status": "processing"}
    claim.assert_called_once_with(2, 1)
    # Vectors first, then chunks (which cascades their search_results), then the worker
    assert steps.mock_calls == [
        call.delete_chunk_vectors(2),
        call.delete_chunks(2),
        call.invalidate_user_cache(1),
        call.start_processing(2, "1/b.pdf"),
    ]


def test_retry_of_a_ready_document_is_refused(client, auth_header):
    res, claim, steps = _retry(client, auth_header, doc={**ERROR_DOC, "status": "ready"})

    assert res.status_code == 409
    claim.assert_not_called()
    assert steps.mock_calls == []


def test_second_retry_at_the_same_time_is_refused(client, auth_header):
    res, claim, steps = _retry(client, auth_header, claimed=False)

    assert res.status_code == 409
    assert steps.mock_calls == []


def test_retry_of_another_users_document_is_404(client, auth_header):
    res, _, steps = _retry(client, auth_header, doc=None)

    assert res.status_code == 404
    assert steps.mock_calls == []


def test_retry_requires_a_session(client):
    assert client.post("/api/documents/2/retry").status_code == 401


def test_failed_clean_up_puts_the_document_back_to_error(client, auth_header):
    res, _, steps = _retry(client, auth_header, clear_error=RuntimeError("PostgreSQL connection unavailable"))

    assert res.status_code == 500
    steps.update_document_status.assert_called_once_with(2, "error")
    steps.start_processing.assert_not_called()


def test_failure_to_start_the_worker_puts_the_document_back_to_error(client, auth_header):
    res, _, steps = _retry(client, auth_header, start_error=RuntimeError("can't start new thread"))

    assert res.status_code == 500
    steps.update_document_status.assert_called_once_with(2, "error")


def test_upload_still_starts_the_worker_through_the_shared_helper(client, auth_header):
    with patch(f"{ROUTES}.upload_file"), \
         patch(f"{ROUTES}.insert_document", return_value=9), \
         patch(f"{ROUTES}.insert_document_topics"), \
         patch(f"{ROUTES}.invalidate_user_cache"), \
         patch(f"{ROUTES}.write_document_to_graph_async"), \
         patch(f"{ROUTES}.start_processing") as start:
        from io import BytesIO
        res = client.post(
            "/api/documents/upload",
            data={"file": (BytesIO(b"%PDF-1.4 test"), "notes.pdf")},
            headers=auth_header,
            content_type="multipart/form-data",
        )

    assert res.status_code == 201
    start.assert_called_once()
    assert start.call_args.args[0] == 9


# ============================================================================
# 2. & 3. SQL
# ============================================================================

def _conn(rowcount):
    conn = MagicMock()
    conn.cursor.return_value.rowcount = rowcount
    return conn


def test_claim_is_one_conditional_update():
    conn = _conn(1)
    assert claim_for_retry(2, 1, conn=conn) is True

    sql, params = conn.cursor.return_value.execute.call_args.args
    assert sql == "UPDATE documents SET status = 'processing' WHERE doc_id = %s AND user_id = %s AND status = 'error'"
    assert params == (2, 1)
    conn.commit.assert_called_once()


def test_claim_fails_when_nothing_was_in_error():
    assert claim_for_retry(2, 1, conn=_conn(0)) is False


def test_interrupted_processing_becomes_error():
    conn = _conn(3)
    assert mark_interrupted_processing_failed(conn=conn) == 3

    sql = conn.cursor.return_value.execute.call_args.args[0]
    assert sql == "UPDATE documents SET status = 'error' WHERE status = 'processing'"
    conn.commit.assert_called_once()


def test_creating_the_app_does_not_touch_document_status():
    with patch("backend.modules.documents.db.mark_interrupted_processing_failed") as recover:
        create_app({"TESTING": True})
    recover.assert_not_called()


def test_starting_the_server_recovers_interrupted_documents():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    with patch("backend.modules.documents.db.mark_interrupted_processing_failed", return_value=2) as recover, \
         patch("flask.Flask.run") as run, \
         patch("backend.modules.documents.storage.ensure_bucket_exists"):
        runpy.run_path(str(app_path), run_name="__main__")

    recover.assert_called_once_with()
    run.assert_called_once()


def test_server_still_starts_if_recovery_fails():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    with patch("backend.modules.documents.db.mark_interrupted_processing_failed",
               side_effect=RuntimeError("MySQL unreachable")), \
         patch("flask.Flask.run") as run, \
         patch("backend.modules.documents.storage.ensure_bucket_exists"):
        runpy.run_path(str(app_path), run_name="__main__")

    run.assert_called_once()


# ============================================================================
# Integration (opt-in): real MySQL, TEMPORARY table only
# ============================================================================

integration = pytest.mark.skipif(
    os.getenv("PRISM_MYSQL_INTEGRATION") != "1" or not os.getenv("MYSQL_URL"),
    reason="set PRISM_MYSQL_INTEGRATION=1 and MYSQL_URL to run against a real MySQL server",
)


@integration
def test_integration_claim_once_and_recover():
    import mysql.connector

    from backend.modules.auth.db import get_db_config

    conn = mysql.connector.connect(**get_db_config())
    try:
        cur = conn.cursor()
        # Shadows the real documents table for this connection only
        cur.execute("CREATE TEMPORARY TABLE documents (doc_id INT PRIMARY KEY, user_id INT, status VARCHAR(50))")
        cur.execute("INSERT INTO documents VALUES (1, 9, 'error'), (2, 9, 'processing'), (3, 9, 'ready')")
        cur.close()

        assert claim_for_retry(1, 8, conn=conn) is False   # not the owner
        assert claim_for_retry(1, 9, conn=conn) is True
        assert claim_for_retry(1, 9, conn=conn) is False   # already claimed
        assert claim_for_retry(3, 9, conn=conn) is False   # ready, not error

        assert mark_interrupted_processing_failed(conn=conn) == 2  # docs 1 (just claimed) and 2
        cur = conn.cursor()
        cur.execute("SELECT doc_id, status FROM documents ORDER BY doc_id")
        assert cur.fetchall() == [(1, "error"), (2, "error"), (3, "ready")]
        cur.close()
    finally:
        conn.close()
