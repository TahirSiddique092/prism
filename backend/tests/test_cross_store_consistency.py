"""Acceptance criteria tests for slice-24: Cross-store consistency fixes.

Acceptance criteria verified:
1. After DELETE /api/documents/:doc_id, Neo4j has no Document {doc_id} node, and
   Topic nodes left with no ABOUT edges are removed.
2. GET /api/documents/:id/related never returns a document that has been
   deleted, even if the Neo4j delete failed.
3. The delete endpoint still returns 200 when Neo4j is unreachable.
4. Uploading with topics ["SQL", " sql ", "Joins"] stores exactly `sql` and
   `joins` in MySQL topics / doc_topics, and the same two names in Neo4j.
5. Deleting that document removes its doc_topics rows via the existing cascade.
6. If insert_document raises during upload, delete_file is called with the
   generated minio_key and the response is still 500.
7. reconcile.py with no flags changes nothing and lists the orphans it finds.
8. reconcile.py --apply removes exactly those orphans and nothing else.
"""
import datetime
import io
import re
from pathlib import Path
from unittest.mock import DEFAULT, MagicMock, patch

import pytest

from backend.app import create_app
from backend.db import reconcile as rc
from backend.modules.auth.service import generate_token
from backend.modules.documents.db import get_existing_doc_ids, insert_document_topics
from backend.modules.graph.service import (
    DELETE_DOCUMENT_CYPHER,
    DELETE_ORPHAN_TOPICS_CYPHER,
    delete_document_from_graph,
)

MIGRATION_001 = Path(__file__).resolve().parents[1] / "db" / "migrations" / "001_init.sql"


@pytest.fixture
def app():
    # GRAPH_WRITE_SYNC runs the upload's graph write inline for assertions.
    return create_app({"TESTING": True, "GRAPH_WRITE_SYNC": True})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user1_token():
    return generate_token(user_id=1, email="user1@example.com")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _mock_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return driver, session


# ============================================================================
# 1. Neo4j delete on document delete
# ============================================================================

def test_delete_cypher_detaches_users_document_and_sweeps_orphan_topics():
    assert "(:User {user_id: $user_id})-[:UPLOADED]->(d:Document {doc_id: $doc_id})" in DELETE_DOCUMENT_CYPHER
    assert "DETACH DELETE d" in DELETE_DOCUMENT_CYPHER
    assert "WHERE NOT (t)<-[:ABOUT]-()" in DELETE_ORPHAN_TOPICS_CYPHER
    assert "DELETE t" in DELETE_ORPHAN_TOPICS_CYPHER


def test_delete_document_from_graph_runs_delete_then_topic_sweep():
    driver, session = _mock_driver()
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        assert delete_document_from_graph(doc_id=55, user_id=1) is True

    calls = session.run.call_args_list
    assert len(calls) == 2
    assert calls[0].args[0] == DELETE_DOCUMENT_CYPHER
    assert calls[0].kwargs == {"doc_id": 55, "user_id": 1}
    assert calls[1].args[0] == DELETE_ORPHAN_TOPICS_CYPHER


def test_delete_route_removes_graph_node_between_pgvector_and_storage(client, user1_token):
    fake_doc = {"doc_id": 55, "user_id": 1, "minio_key": "1/thesis.pdf"}
    order = []

    with patch("backend.modules.documents.routes.get_document_by_id", return_value=fake_doc), \
         patch("backend.modules.documents.routes.delete_document", return_value=True), \
         patch("backend.modules.documents.routes.delete_chunk_vectors",
               side_effect=lambda *a: order.append("pgvector")), \
         patch("backend.modules.documents.routes.delete_document_from_graph",
               side_effect=lambda *a: order.append("neo4j")) as mock_graph_del, \
         patch("backend.modules.documents.routes.delete_file",
               side_effect=lambda *a: order.append("storage")), \
         patch("backend.modules.documents.routes.invalidate_user_cache",
               side_effect=lambda *a: order.append("redis")):
        res = client.delete("/api/documents/55", headers=_auth(user1_token))

    assert res.status_code == 200
    mock_graph_del.assert_called_once_with(55, 1)
    assert order == ["pgvector", "neo4j", "storage", "redis"]


# ============================================================================
# 3. Delete still succeeds when Neo4j is unreachable
# ============================================================================

def test_delete_document_from_graph_is_graceful_when_neo4j_down():
    driver = MagicMock()
    driver.session.side_effect = Exception("neo4j down")
    with patch("backend.modules.graph.service.get_driver", return_value=driver):
        assert delete_document_from_graph(doc_id=55, user_id=1) is False


def test_delete_document_from_graph_skips_when_not_configured():
    with patch("backend.modules.graph.service.get_driver", return_value=None):
        assert delete_document_from_graph(doc_id=55, user_id=1) is False


def test_delete_route_returns_200_when_neo4j_unreachable(client, user1_token):
    fake_doc = {"doc_id": 55, "user_id": 1, "minio_key": "1/thesis.pdf"}
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=fake_doc), \
         patch("backend.modules.documents.routes.delete_document", return_value=True), \
         patch("backend.modules.documents.routes.delete_chunk_vectors"), \
         patch("backend.modules.graph.service.get_driver", side_effect=Exception("neo4j down")), \
         patch("backend.modules.documents.routes.delete_file") as mock_storage_del, \
         patch("backend.modules.documents.routes.invalidate_user_cache"):
        res = client.delete("/api/documents/55", headers=_auth(user1_token))

    assert res.status_code == 200
    assert res.get_json() == {"message": "deleted"}
    # The later cleanup steps still run after the graph failure
    mock_storage_del.assert_called_once_with("1/thesis.pdf")


# ============================================================================
# 2. Related documents are filtered against MySQL
# ============================================================================

def test_related_endpoint_drops_documents_missing_from_mysql(client, user1_token):
    graph_related = [
        {"doc_id": 2, "title": "Kept.pdf", "shared_topics": 3},
        {"doc_id": 3, "title": "Deleted.pdf", "shared_topics": 2},
        {"doc_id": 4, "title": "Also Kept.pdf", "shared_topics": 1},
    ]
    with patch("backend.modules.documents.routes.get_document_by_id", return_value={"doc_id": 1, "user_id": 1}), \
         patch("backend.modules.documents.routes.get_related_documents", return_value=graph_related), \
         patch("backend.modules.documents.routes.get_existing_doc_ids", return_value={2, 4}) as mock_existing:
        res = client.get("/api/documents/1/related", headers=_auth(user1_token))

    assert res.status_code == 200
    assert [d["doc_id"] for d in res.get_json()] == [2, 4]  # order preserved
    mock_existing.assert_called_once_with(1, [2, 3, 4])


def test_related_endpoint_skips_mysql_check_when_graph_returns_nothing(client, user1_token):
    with patch("backend.modules.documents.routes.get_document_by_id", return_value={"doc_id": 1, "user_id": 1}), \
         patch("backend.modules.documents.routes.get_related_documents", return_value=[]), \
         patch("backend.modules.documents.routes.get_existing_doc_ids") as mock_existing:
        res = client.get("/api/documents/1/related", headers=_auth(user1_token))

    assert res.status_code == 200
    assert res.get_json() == []
    mock_existing.assert_not_called()


def test_get_existing_doc_ids_sql_is_scoped_to_user():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.return_value = [(2,), (4,)]

    assert get_existing_doc_ids(1, [2, 3, 4], conn=conn) == {2, 4}
    sql, params = cursor.execute.call_args.args
    assert "FROM documents WHERE user_id = %s AND doc_id IN (%s,%s,%s)" in sql
    assert params == (1, 2, 3, 4)


def test_get_existing_doc_ids_empty_input_does_not_query():
    conn = MagicMock()
    assert get_existing_doc_ids(1, [], conn=conn) == set()
    conn.cursor.assert_not_called()


# ============================================================================
# 4. Topics mirrored into MySQL on upload
# ============================================================================

def _pdf_upload(topics):
    return {
        "file": (io.BytesIO(b"%PDF-1.4 fake pdf bytes"), "doc.pdf", "application/pdf"),
        "topics": topics,
    }


def test_upload_stores_same_normalized_topics_in_mysql_and_neo4j(client, user1_token):
    driver, session = _mock_driver()
    with patch("backend.modules.documents.routes.upload_file"), \
         patch("backend.modules.documents.routes.insert_document", return_value=42), \
         patch("backend.modules.documents.routes.insert_document_topics") as mock_topics, \
         patch("backend.modules.documents.routes.invalidate_user_cache"), \
         patch("backend.modules.graph.service.get_driver", return_value=driver), \
         patch("threading.Thread"):
        res = client.post(
            "/api/documents/upload",
            data=_pdf_upload(["SQL", " sql ", "Joins"]),
            content_type="multipart/form-data",
            headers=_auth(user1_token),
        )

    assert res.status_code == 201
    mock_topics.assert_called_once_with(42, ["sql", "joins"])
    assert session.run.call_args.kwargs["topics"] == ["sql", "joins"]


def test_upload_succeeds_when_mysql_topic_write_fails(client, user1_token):
    with patch("backend.modules.documents.routes.upload_file"), \
         patch("backend.modules.documents.routes.insert_document", return_value=42), \
         patch("backend.modules.documents.routes.insert_document_topics", side_effect=Exception("db down")), \
         patch("backend.modules.documents.routes.invalidate_user_cache"), \
         patch("backend.modules.graph.service.get_driver", return_value=None), \
         patch("threading.Thread"):
        res = client.post(
            "/api/documents/upload",
            data=_pdf_upload(["SQL"]),
            content_type="multipart/form-data",
            headers=_auth(user1_token),
        )

    assert res.status_code == 201
    assert res.get_json()["doc_id"] == 42


def test_insert_document_topics_sql_inserts_each_topic_once_and_links_them():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    insert_document_topics(42, ["sql", "joins"], conn=conn)

    topics_sql, topic_rows = cursor.executemany.call_args.args
    assert topics_sql == "INSERT IGNORE INTO topics (name) VALUES (%s)"
    assert topic_rows == [("sql",), ("joins",)]

    link_sql, link_params = cursor.execute.call_args.args
    assert "INSERT IGNORE INTO doc_topics (doc_id, topic_id)" in link_sql
    assert "SELECT %s, topic_id FROM topics WHERE name IN (%s,%s)" in link_sql
    assert link_params == (42, "sql", "joins")
    conn.commit.assert_called_once()


def test_insert_document_topics_no_topics_does_not_query():
    conn = MagicMock()
    insert_document_topics(42, [], conn=conn)
    conn.cursor.assert_not_called()


# ============================================================================
# 5. doc_topics rows are removed by the existing cascade
# ============================================================================

def test_doc_topics_cascades_on_document_delete():
    ddl = MIGRATION_001.read_text()
    doc_topics = re.search(r"CREATE TABLE doc_topics \((.*?)\);", ddl, re.S).group(1)
    assert "FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE" in doc_topics


# ============================================================================
# 6. Stored PDF removed when the MySQL insert fails
# ============================================================================

def test_upload_removes_stored_pdf_when_insert_document_fails(client, user1_token):
    with patch("backend.modules.documents.routes.upload_file") as mock_upload, \
         patch("backend.modules.documents.routes.insert_document", side_effect=Exception("db down")), \
         patch("backend.modules.documents.routes.delete_file") as mock_delete_file, \
         patch("backend.modules.documents.routes.insert_document_topics") as mock_topics:
        res = client.post(
            "/api/documents/upload",
            data=_pdf_upload(["SQL"]),
            content_type="multipart/form-data",
            headers=_auth(user1_token),
        )

    assert res.status_code == 500
    generated_key = mock_upload.call_args.args[1]
    assert re.fullmatch(r"1/[0-9a-f-]{36}\.pdf", generated_key)
    mock_delete_file.assert_called_once_with(generated_key)
    mock_topics.assert_not_called()


def test_upload_still_500_when_cleanup_of_pdf_also_fails(client, user1_token):
    with patch("backend.modules.documents.routes.upload_file"), \
         patch("backend.modules.documents.routes.insert_document", side_effect=Exception("db down")), \
         patch("backend.modules.documents.routes.delete_file", side_effect=Exception("storage down")):
        res = client.post(
            "/api/documents/upload",
            data=_pdf_upload(["SQL"]),
            content_type="multipart/form-data",
            headers=_auth(user1_token),
        )

    assert res.status_code == 500
    assert "error" in res.get_json()


# ============================================================================
# 7 & 8. Reconciliation script
# ============================================================================

# MySQL has docs 1 and 2. Every other store also holds leftovers of doc 3
# (pgvector), doc 9 (Neo4j) and an unreferenced PDF; doc 2's topics were never
# mirrored into MySQL.
MYSQL_DOCS = {1: "1/a.pdf", 2: "1/b.pdf"}
VECTOR_DOC_IDS = {1, 2, 3}
GRAPH_DOCS = {1: ["sql"], 2: ["sql", "joins"], 9: ["old topic"]}
STORED_TOPIC_PAIRS = {(1, "sql")}
STORAGE_KEYS = {"1/a.pdf", "1/b.pdf", "1/stale.pdf"}


def _patch_stores():
    return patch.multiple(
        "backend.db.reconcile",
        fetch_mysql_documents=MagicMock(return_value=MYSQL_DOCS),
        fetch_vector_doc_ids=MagicMock(return_value=set(VECTOR_DOC_IDS)),
        fetch_graph_documents=MagicMock(return_value=dict(GRAPH_DOCS)),
        fetch_mysql_doc_topics=MagicMock(return_value=set(STORED_TOPIC_PAIRS)),
        fetch_storage_keys=MagicMock(return_value=set(STORAGE_KEYS)),
        delete_vectors=DEFAULT,
        delete_graph_documents=DEFAULT,
        delete_storage_objects=DEFAULT,
        insert_document_topics=DEFAULT,
    )


def test_reconcile_dry_run_lists_orphans_and_changes_nothing():
    mysql, pg, driver, s3 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    with _patch_stores() as writes:
        report = rc.reconcile(mysql, pg_conn=pg, driver=driver, s3=s3, bucket="prism-documents")

    assert report["applied"] is False
    assert report["mysql_documents"] == 2
    assert report["orphan_vector_doc_ids"] == [3]
    assert report["orphan_graph_doc_ids"] == [9]
    assert report["orphan_storage_keys"] == ["1/stale.pdf"]
    assert report["missing_topics"] == {2: ["joins", "sql"]}
    assert report["errors"] == {}
    for mock in writes.values():
        mock.assert_not_called()


def test_reconcile_apply_removes_exactly_the_orphans():
    mysql, pg, driver, s3 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    with _patch_stores() as writes:
        rc.reconcile(mysql, pg_conn=pg, driver=driver, s3=s3, bucket="prism-documents", apply=True)

    writes["delete_vectors"].assert_called_once_with(pg, {3})
    writes["delete_graph_documents"].assert_called_once_with(driver, {9})
    writes["delete_storage_objects"].assert_called_once_with(s3, "prism-documents", {"1/stale.pdf"})
    writes["insert_document_topics"].assert_called_once_with(2, ["joins", "sql"], conn=mysql)


def test_reconcile_apply_with_nothing_orphaned_writes_nothing():
    mysql, pg, driver, s3 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    with patch.multiple(
        "backend.db.reconcile",
        fetch_mysql_documents=MagicMock(return_value=MYSQL_DOCS),
        fetch_vector_doc_ids=MagicMock(return_value={1, 2}),
        fetch_graph_documents=MagicMock(return_value={1: ["sql"]}),
        fetch_mysql_doc_topics=MagicMock(return_value={(1, "sql")}),
        fetch_storage_keys=MagicMock(return_value={"1/a.pdf", "1/b.pdf"}),
        delete_vectors=DEFAULT,
        delete_graph_documents=DEFAULT,
        delete_storage_objects=DEFAULT,
        insert_document_topics=DEFAULT,
    ) as writes:
        rc.reconcile(mysql, pg_conn=pg, driver=driver, s3=s3, bucket="b", apply=True)

    for mock in writes.values():
        mock.assert_not_called()


def test_reconcile_mysql_read_failure_raises_before_touching_other_stores():
    with patch("backend.db.reconcile.fetch_mysql_documents", side_effect=Exception("mysql down")), \
         patch("backend.db.reconcile.fetch_vector_doc_ids") as mock_vectors, \
         patch("backend.db.reconcile.delete_vectors") as mock_delete:
        with pytest.raises(Exception, match="mysql down"):
            rc.reconcile(MagicMock(), pg_conn=MagicMock(), apply=True)

    mock_vectors.assert_not_called()
    mock_delete.assert_not_called()


def test_reconcile_store_error_is_reported_and_other_stores_still_run():
    with _patch_stores() as writes, \
         patch("backend.db.reconcile.fetch_vector_doc_ids", side_effect=Exception("neon down")):
        report = rc.reconcile(MagicMock(), pg_conn=MagicMock(), driver=MagicMock(),
                              s3=MagicMock(), bucket="b", apply=True)

    assert report["errors"] == {"pgvector": "neon down"}
    writes["delete_vectors"].assert_not_called()
    writes["delete_graph_documents"].assert_called_once()
    writes["delete_storage_objects"].assert_called_once()


def test_reconcile_skips_unconfigured_stores():
    with _patch_stores():
        report = rc.reconcile(MagicMock())

    assert report["skipped"] == ["pgvector", "neo4j", "storage"]


def test_fetch_storage_keys_ignores_objects_inside_grace_period():
    now = datetime.datetime(2026, 10, 27, 12, 0, tzinfo=datetime.timezone.utc)
    s3 = MagicMock()
    s3.get_paginator.return_value.paginate.return_value = [
        {"Contents": [
            {"Key": "1/old.pdf", "LastModified": now - datetime.timedelta(hours=1)},
            {"Key": "1/uploading.pdf", "LastModified": now - datetime.timedelta(minutes=1)},
        ]},
        {},  # an empty page has no "Contents"
    ]

    assert rc.fetch_storage_keys(s3, "prism-documents", now) == {"1/old.pdf"}
    s3.get_paginator.return_value.paginate.assert_called_once_with(Bucket="prism-documents")


def test_delete_vectors_sql():
    pg = MagicMock()
    cursor = pg.cursor.return_value.__enter__.return_value
    rc.delete_vectors(pg, {5, 3})

    cursor.execute.assert_called_once_with("DELETE FROM chunk_vectors WHERE doc_id = ANY(%s)", ([3, 5],))
    pg.commit.assert_called_once()


def test_delete_graph_documents_detaches_nodes_then_sweeps_topics():
    driver, session = _mock_driver()
    rc.delete_graph_documents(driver, {9, 7})

    calls = session.run.call_args_list
    assert "DETACH DELETE d" in calls[0].args[0]
    assert calls[0].kwargs == {"doc_ids": [7, 9]}
    assert calls[1].args[0] == DELETE_ORPHAN_TOPICS_CYPHER


def test_format_report_dry_run_mentions_apply_flag():
    with _patch_stores():
        report = rc.reconcile(MagicMock(), pg_conn=MagicMock(), driver=MagicMock(), s3=MagicMock(), bucket="b")

    text = rc.format_report(report)
    assert "DRY RUN" in text and "--apply" in text
    assert "1/stale.pdf" in text
    assert "doc 2: joins, sql" in text


def test_main_refuses_to_run_without_mysql(capsys):
    with patch("dotenv.load_dotenv"), \
         patch("backend.db.migrate.get_mysql_conn", return_value=None), \
         patch("backend.db.reconcile.reconcile") as mock_reconcile:
        assert rc.main([]) == 1

    mock_reconcile.assert_not_called()
    assert "MYSQL_URL is not set" in capsys.readouterr().out
