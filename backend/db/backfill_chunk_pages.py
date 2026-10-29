"""Fill in chunk page numbers for documents processed before slice-27.

Chunks stored before migration 007 have no page_start / page_end, so their
search results open the PDF at page 1. For each ready document with such
chunks, this downloads the PDF, splits it again exactly as the worker does,
and fills in the pages, but only if the regenerated chunks are identical to
the stored ones (same count, same text at each chunk_index). Any other
document is reported and left alone.

Dry run by default — nothing is changed unless --apply is passed.

    python backend/db/backfill_chunk_pages.py            # report only
    python backend/db/backfill_chunk_pages.py --apply    # report and fill in
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Allow running as `python backend/db/backfill_chunk_pages.py` from the repo
# root (the Docker image already sets PYTHONPATH=/app).
sys.path.insert(0, str(REPO_ROOT))

DOCUMENTS_MISSING_PAGES_QUERY = """
SELECT DISTINCT d.doc_id, d.title, d.minio_key
FROM documents d
JOIN chunks c ON c.doc_id = d.doc_id
WHERE d.status = 'ready' AND c.page_start IS NULL
ORDER BY d.doc_id
"""

STORED_CHUNKS_QUERY = """
SELECT chunk_id, chunk_index, chunk_text
FROM chunks
WHERE doc_id = %s
ORDER BY chunk_index
"""

UPDATE_PAGES_QUERY = "UPDATE chunks SET page_start = %s, page_end = %s WHERE chunk_id = %s"


def fetch_documents_missing_pages(mysql_conn) -> list:
    """[(doc_id, title, minio_key)] of ready documents with chunks lacking pages."""
    cursor = mysql_conn.cursor()
    cursor.execute(DOCUMENTS_MISSING_PAGES_QUERY)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_stored_chunks(mysql_conn, doc_id: int) -> list:
    """[(chunk_id, chunk_index, chunk_text)] of a document, in order."""
    cursor = mysql_conn.cursor()
    cursor.execute(STORED_CHUNKS_QUERY, (doc_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def match_pages(stored: list, regenerated: list) -> list | None:
    """Pair stored chunks with regenerated ones: [(chunk_id, page_start, page_end)].

    Returns None unless the regenerated chunks are exactly the stored ones:
    the same number, with the same text at every chunk_index.
    """
    if len(stored) != len(regenerated):
        return None
    updates = []
    for index, ((chunk_id, chunk_index, text), (new_text, page_start, page_end)) in enumerate(
        zip(stored, regenerated)
    ):
        if chunk_index != index or text != new_text:
            return None
        updates.append((chunk_id, page_start, page_end))
    return updates


def write_pages(mysql_conn, updates: list) -> None:
    cursor = mysql_conn.cursor()
    cursor.executemany(
        UPDATE_PAGES_QUERY,
        [(page_start, page_end, chunk_id) for chunk_id, page_start, page_end in updates],
    )
    mysql_conn.commit()
    cursor.close()


def backfill(mysql_conn, load_pdf, chunk_pdf, apply: bool = False) -> dict:
    """Find, and with apply=True fill in, missing chunk pages.

    ``load_pdf(minio_key)`` returns the PDF bytes; ``chunk_pdf(pdf_bytes)``
    returns [(chunk_text, page_start, page_end)] the way the worker does.
    """
    report = {"filled": [], "skipped": [], "errors": [], "applied": apply}
    for doc_id, title, minio_key in fetch_documents_missing_pages(mysql_conn):
        try:
            regenerated = chunk_pdf(load_pdf(minio_key))
        except Exception as e:
            report["errors"].append((doc_id, title, str(e)))
            continue

        updates = match_pages(fetch_stored_chunks(mysql_conn, doc_id), regenerated)
        if updates is None:
            report["skipped"].append((doc_id, title))
            continue
        if apply:
            write_pages(mysql_conn, updates)
        report["filled"].append((doc_id, title, len(updates)))
    return report


def format_report(report: dict) -> str:
    if report["applied"]:
        lines = ["Chunk page backfill (applied):"]
    else:
        lines = ["Chunk page backfill (dry run: nothing changed; run with --apply to fill in):"]
    verb = "filled" if report["applied"] else "would fill"
    for doc_id, title, count in report["filled"]:
        lines.append(f"  {verb}: {title} (doc {doc_id}), {count} chunks")
    for doc_id, title in report["skipped"]:
        lines.append(f"  skipped: {title} (doc {doc_id}), the PDF no longer splits into the stored chunks")
    for doc_id, title, error in report["errors"]:
        lines.append(f"  error: {title} (doc {doc_id}): {error}")
    if len(lines) == 1:
        lines.append("  nothing to do: every ready document already has chunk pages")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Fill in page_start / page_end for chunks stored before slice-27."
    )
    parser.add_argument("--apply", action="store_true", help="write the pages (default: report only)")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    from backend.db.migrate import get_mysql_conn
    from backend.modules.documents.storage import BUCKET_NAME, get_s3_client
    from backend.modules.documents.worker import chunk_document, extract_page_texts

    try:
        mysql_conn = get_mysql_conn()
    except Exception as e:
        print(f"Cannot connect to MySQL: {e}")
        return 1
    if mysql_conn is None:
        print("MYSQL_URL is not set.")
        return 1

    s3 = get_s3_client()

    def load_pdf(minio_key):
        return s3.get_object(Bucket=BUCKET_NAME, Key=minio_key)["Body"].read()

    def chunk_pdf(pdf_bytes):
        return chunk_document(extract_page_texts(pdf_bytes))

    try:
        report = backfill(mysql_conn, load_pdf, chunk_pdf, apply=args.apply)
    finally:
        mysql_conn.close()

    print(format_report(report))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
