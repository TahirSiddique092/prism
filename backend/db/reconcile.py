"""Cross-store reconciliation for PRISM (Slice 24).

MySQL is the source of truth for which documents exist. The deletes in the
other stores are best-effort (see ADR-016), so this script finds anything they
left behind and, with --apply, removes it:

- pgvector  : chunk_vectors rows whose doc_id is not in MySQL documents
- Neo4j     : Document nodes whose doc_id is not in MySQL, then Topics left
              with no documents
- Storage   : objects whose key matches no documents.minio_key
- Topics    : tags present in Neo4j but missing from MySQL topics / doc_topics
              (backfill for documents uploaded before Slice 24)

Dry run by default — nothing is changed unless --apply is passed.

    python backend/db/reconcile.py            # report only
    python backend/db/reconcile.py --apply    # report and fix
"""
import argparse
import datetime
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Allow running as `python backend/db/reconcile.py` from the repo root
# (the Docker image already sets PYTHONPATH=/app).
sys.path.insert(0, str(REPO_ROOT))

# Importing this module has no side effects: .env is loaded, and the modules
# that read it at import time (migrate, storage) are imported, only in main().
from backend.modules.documents.db import insert_document_topics  # noqa: E402
from backend.modules.graph.client import get_driver  # noqa: E402
from backend.modules.graph.service import DELETE_ORPHAN_TOPICS_CYPHER  # noqa: E402

# An upload stores the PDF a moment before its documents row is inserted, so
# very recent objects are skipped instead of being treated as orphans.
RECENT_OBJECT_GRACE = datetime.timedelta(minutes=10)

GRAPH_DOCUMENTS_CYPHER = """
MATCH (d:Document)
OPTIONAL MATCH (d)-[:ABOUT]->(t:Topic)
RETURN d.doc_id AS doc_id, collect(t.name) AS topics
"""

DELETE_GRAPH_DOCUMENTS_CYPHER = """
MATCH (d:Document)
WHERE d.doc_id IN $doc_ids
DETACH DELETE d
"""


# ----------------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------------

def fetch_mysql_documents(mysql_conn) -> dict:
    """Return {doc_id: minio_key} for every document in MySQL."""
    cursor = mysql_conn.cursor()
    cursor.execute("SELECT doc_id, minio_key FROM documents")
    rows = cursor.fetchall()
    cursor.close()
    return {row[0]: row[1] for row in rows}


def fetch_mysql_doc_topics(mysql_conn) -> set:
    """Return the (doc_id, topic name) pairs already stored in doc_topics."""
    cursor = mysql_conn.cursor()
    cursor.execute("""
        SELECT dt.doc_id, t.name
        FROM doc_topics dt
        JOIN topics t ON dt.topic_id = t.topic_id
    """)
    rows = cursor.fetchall()
    cursor.close()
    return {(row[0], row[1]) for row in rows}


def fetch_vector_doc_ids(pg_conn) -> set:
    """Return every doc_id that has rows in chunk_vectors."""
    with pg_conn.cursor() as cursor:
        cursor.execute("SELECT DISTINCT doc_id FROM chunk_vectors")
        return {row[0] for row in cursor.fetchall()}


def fetch_graph_documents(driver) -> dict:
    """Return {doc_id: [topic names]} for every Document node in Neo4j."""
    with driver.session() as session:
        result = session.run(GRAPH_DOCUMENTS_CYPHER)
        return {
            record["doc_id"]: list(record["topics"])
            for record in result
            if record["doc_id"] is not None
        }


def fetch_storage_keys(s3, bucket, now) -> set:
    """Return the bucket's object keys, ignoring objects newer than the grace period."""
    keys = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            if now - obj["LastModified"] >= RECENT_OBJECT_GRACE:
                keys.add(obj["Key"])
    return keys


# ----------------------------------------------------------------------------
# Writes (only called with --apply)
# ----------------------------------------------------------------------------

def delete_vectors(pg_conn, doc_ids) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute("DELETE FROM chunk_vectors WHERE doc_id = ANY(%s)", (sorted(doc_ids),))
    pg_conn.commit()


def delete_graph_documents(driver, doc_ids) -> None:
    with driver.session() as session:
        session.run(DELETE_GRAPH_DOCUMENTS_CYPHER, doc_ids=sorted(doc_ids))
        session.run(DELETE_ORPHAN_TOPICS_CYPHER)


def delete_storage_objects(s3, bucket, keys) -> None:
    for key in sorted(keys):
        s3.delete_object(Bucket=bucket, Key=key)


# ----------------------------------------------------------------------------
# Reconcile
# ----------------------------------------------------------------------------

def reconcile(mysql_conn, pg_conn=None, driver=None, s3=None, bucket=None,
              apply=False, now=None) -> dict:
    """Compare every store against MySQL and, if ``apply``, remove the orphans.

    A store passed as None is skipped. A failure in one store is recorded in
    ``errors`` and the others still run. A failure reading MySQL is raised:
    without the source of truth nothing can be judged an orphan.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    documents = fetch_mysql_documents(mysql_conn)
    doc_ids = set(documents)
    known_keys = set(documents.values())

    report = {
        "applied": apply,
        "mysql_documents": len(documents),
        "orphan_vector_doc_ids": [],
        "orphan_graph_doc_ids": [],
        "orphan_storage_keys": [],
        "missing_topics": {},
        "skipped": [],
        "errors": {},
    }

    if pg_conn is None:
        report["skipped"].append("pgvector")
    else:
        try:
            orphans = fetch_vector_doc_ids(pg_conn) - doc_ids
            report["orphan_vector_doc_ids"] = sorted(orphans)
            if apply and orphans:
                delete_vectors(pg_conn, orphans)
        except Exception as e:
            report["errors"]["pgvector"] = str(e)

    if driver is None:
        report["skipped"].append("neo4j")
    else:
        try:
            graph_docs = fetch_graph_documents(driver)
            orphans = set(graph_docs) - doc_ids
            report["orphan_graph_doc_ids"] = sorted(orphans)

            stored_pairs = fetch_mysql_doc_topics(mysql_conn)
            for doc_id in sorted(set(graph_docs) & doc_ids):
                missing = [n for n in graph_docs[doc_id] if (doc_id, n) not in stored_pairs]
                if missing:
                    report["missing_topics"][doc_id] = sorted(missing)

            if apply:
                if orphans:
                    delete_graph_documents(driver, orphans)
                for doc_id, names in report["missing_topics"].items():
                    insert_document_topics(doc_id, names, conn=mysql_conn)
        except Exception as e:
            report["errors"]["neo4j"] = str(e)

    if s3 is None:
        report["skipped"].append("storage")
    else:
        try:
            orphans = fetch_storage_keys(s3, bucket, now) - known_keys
            report["orphan_storage_keys"] = sorted(orphans)
            if apply and orphans:
                delete_storage_objects(s3, bucket, orphans)
        except Exception as e:
            report["errors"]["storage"] = str(e)

    return report


def format_report(report: dict) -> str:
    def ids(values):
        return ", ".join(str(v) for v in values) if values else "none"

    if report["applied"]:
        header = "PRISM reconcile — APPLIED (orphans below were removed)"
    else:
        header = "PRISM reconcile — DRY RUN (nothing changed; re-run with --apply to fix)"

    missing = report["missing_topics"]
    lines = [
        header,
        f"MySQL documents       : {report['mysql_documents']}",
        f"pgvector orphan docs  : {ids(report['orphan_vector_doc_ids'])}",
        f"Neo4j orphan docs     : {ids(report['orphan_graph_doc_ids'])}",
        f"Storage orphan objects: {ids(report['orphan_storage_keys'])}",
        f"Topics to backfill    : {'none' if not missing else ''}",
    ]
    for doc_id, names in missing.items():
        lines.append(f"    doc {doc_id}: {', '.join(names)}")
    for store in report["skipped"]:
        lines.append(f"Skipped {store} (not configured)")
    for store, message in report["errors"].items():
        lines.append(f"ERROR in {store}: {message}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Find, and with --apply remove, data left in pgvector, Neo4j and "
                    "object storage for documents that no longer exist in MySQL."
    )
    parser.add_argument("--apply", action="store_true", help="make the changes (default: report only)")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    from backend.db.migrate import get_mysql_conn, get_postgres_conn
    from backend.modules.documents.storage import BUCKET_NAME, get_s3_client

    try:
        mysql_conn = get_mysql_conn()
    except Exception as e:
        print(f"Cannot connect to MySQL: {e}")
        return 1
    if mysql_conn is None:
        print("MYSQL_URL is not set. MySQL is the source of truth, so nothing can be reconciled.")
        return 1

    try:
        pg_conn = get_postgres_conn()
    except Exception as e:
        print(f"Cannot connect to PostgreSQL, skipping pgvector: {e}")
        pg_conn = None

    driver = get_driver()
    configured_storage = os.getenv("S3_ENDPOINT") or os.getenv("MINIO_ENDPOINT")
    s3 = get_s3_client() if configured_storage else None

    try:
        report = reconcile(
            mysql_conn, pg_conn=pg_conn, driver=driver, s3=s3,
            bucket=BUCKET_NAME, apply=args.apply,
        )
    finally:
        mysql_conn.close()
        if pg_conn is not None:
            pg_conn.close()
        if driver is not None:
            driver.close()

    print(format_report(report))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
