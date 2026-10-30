"""Slice 27: open a search result at its passage.

1. The worker records the pages each chunk starts and ends on, with chunk
   texts unchanged
2. backfill_chunk_pages fills pages only where re-chunking reproduces the
   stored chunks
3. Search results carry the passage's first page
4. GET /api/documents/:doc_id/chunks/:chunk_id returns a passage, scoped to
   the user's own documents

Unit tests use mocks. The integration test at the bottom is opt-in
(PRISM_MYSQL_INTEGRATION=1 plus MYSQL_URL) and only touches TEMPORARY tables.
"""
import os
import random
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app import create_app
from backend.db import backfill_chunk_pages as bf
from backend.modules.auth.service import generate_token
from backend.modules.documents.db import get_chunk
from backend.modules.documents.worker import (
    MAX_WORDS,
    MIN_CHUNK_WORDS,
    OVERLAP_SENTENCES,
    TARGET_WORDS,
    chunk_pages,
    chunk_sentences,
    count_words,
)

MIGRATION_007 = Path(__file__).parent.parent / "db" / "migrations" / "007_chunk_pages.sql"


def _old_chunk_sentences(sentences):
    """chunk_sentences as it was before slice-27, frozen to prove texts are unchanged."""
    chunks, current, current_words = [], [], 0

    def flush():
        nonlocal current, current_words
        if current:
            text = " ".join(current)
            if count_words(text) >= MIN_CHUNK_WORDS:
                chunks.append(text)
        current, current_words = [], 0

    i, n = 0, len(sentences)
    while i < n:
        sentence = sentences[i].strip()
        if not sentence:
            i += 1
            continue
        sentence_words = count_words(sentence)
        if sentence_words > MAX_WORDS:
            flush()
            words = sentence.split()
            for start in range(0, len(words), MAX_WORDS):
                chunks.append(" ".join(words[start:start + MAX_WORDS]))
            i += 1
            continue
        if current_words + sentence_words > TARGET_WORDS and current_words > 0:
            text = " ".join(current)
            if count_words(text) >= MIN_CHUNK_WORDS:
                chunks.append(text)
            overlap = current[-OVERLAP_SENTENCES:]
            overlap_words = sum(count_words(s) for s in overlap)
            if overlap_words + sentence_words > MAX_WORDS:
                overlap, overlap_words = [], 0
            current = overlap + [sentence]
            current_words = overlap_words + sentence_words
            i += 1
        else:
            current.append(sentence)
            current_words += sentence_words
            i += 1
    if current:
        text = " ".join(current)
        if count_words(text) >= MIN_CHUNK_WORDS:
            chunks.append(text)
    return chunks


def _sentence(rng, words):
    return " ".join(rng.choice(["entity", "relation", "key", "schema", "tuple", "join", "index"])
                    for _ in range(words)) + "."


def _pages_and_sentences(sentences_per_page):
    """Page texts plus the sentences sent_tokenize would return for them."""
    page_texts = ["\n".join(page) for page in sentences_per_page]
    sentences = [s for page in sentences_per_page for s in page]
    return page_texts, sentences


# ============================================================================
# 1. Pages per chunk, texts unchanged
# ============================================================================

def test_chunk_texts_are_identical_to_before():
    rng = random.Random(27)
    for _ in range(200):
        sentences = []
        for _ in range(rng.randint(0, 40)):
            kind = rng.random()
            if kind < 0.05:
                sentences.append("   ")                                  # blank piece
            elif kind < 0.12:
                sentences.append(_sentence(rng, rng.randint(251, 700)))  # oversized
            else:
                sentences.append(_sentence(rng, rng.randint(1, 120)))
        assert chunk_sentences(sentences) == _old_chunk_sentences(sentences)


def test_known_sentence_on_page_three_gets_page_three():
    rng = random.Random(3)
    filler = [[_sentence(rng, 60) for _ in range(5)] for _ in range(2)]
    # 212 words: too long to carry the 2-sentence overlap (cap 250), so it starts a chunk
    known = "Weak entities are mapped to relations that include the owner's key " + "and " * 200 + "done."
    page_texts, sentences = _pages_and_sentences(filler + [[known] + [_sentence(rng, 60) for _ in range(4)]])

    chunks = chunk_pages(page_texts, sentences)

    starting = [(start, end) for text, start, end in chunks if text.startswith("Weak entities")]
    assert starting == [(3, 3)]
    # Every chunk that contains the sentence covers page 3
    containing = [(start, end) for text, start, end in chunks if "owner's key" in text]
    assert containing and all(start <= 3 <= end for start, end in containing)


def test_chunk_spanning_two_pages_reports_both():
    page_texts, sentences = _pages_and_sentences([
        ["Alpha " * 30 + "end of page one."],
        ["Beta " * 30 + "start of page two."],
    ])

    (text, page_start, page_end), = chunk_pages(page_texts, sentences)

    assert (page_start, page_end) == (1, 2)
    assert text == chunk_sentences(sentences)[0]


def test_word_windows_of_one_long_sentence_get_their_own_pages():
    # One 600-word "sentence" (slides often have no full stops) across 3 pages
    page_texts = [" ".join(["one"] * 200), " ".join(["two"] * 200), " ".join(["three"] * 200)]
    sentences = [" ".join(page_texts)]

    chunks = chunk_pages(page_texts, sentences)

    # Windows of 250 words: 1-250, 251-500, 501-600
    assert [(start, end) for _, start, end in chunks] == [(1, 2), (2, 3), (3, 3)]
    assert [text for text, _, _ in chunks] == chunk_sentences(sentences)


def test_sentence_that_cannot_be_located_leaves_pages_unknown():
    page_texts = ["word " * 40]
    sentences = ["this text is not in the document " * 5]

    (_, page_start, page_end), = chunk_pages(page_texts, sentences)

    assert (page_start, page_end) == (None, None)


def test_migration_007_adds_nullable_page_columns_in_one_statement():
    sql = MIGRATION_007.read_text()
    assert sql.startswith("-- ENGINE: MySQL")
    assert "ADD COLUMN page_start INT NULL" in sql
    assert "ADD COLUMN page_end INT NULL" in sql
    script = sql.split("-- ENGINE: MySQL", 1)[1]
    assert len([s for s in script.split(";") if s.strip()]) == 1  # migrate.py splits on ";"


# ============================================================================
# 2. Backfill
# ============================================================================

def _mysql_with(documents, stored_by_doc):
    conn = MagicMock()

    def cursor_factory():
        cursor = MagicMock()

        def execute(sql, params=None):
            cursor.rows = documents if "DISTINCT d.doc_id" in sql else stored_by_doc[params[0]]

        cursor.execute.side_effect = execute
        cursor.fetchall.side_effect = lambda: cursor.rows
        conn.cursors.append(cursor)
        return cursor

    conn.cursors = []
    conn.cursor.side_effect = cursor_factory
    return conn


STORED = {2: [(10, 0, "first chunk"), (11, 1, "second chunk")]}
REGENERATED = [("first chunk", 1, 1), ("second chunk", 1, 2)]


def test_backfill_dry_run_changes_nothing():
    conn = _mysql_with([(2, "er-model.pdf", "2/a.pdf")], STORED)

    report = bf.backfill(conn, load_pdf=lambda key: b"%PDF", chunk_pdf=lambda data: REGENERATED)

    assert report["filled"] == [(2, "er-model.pdf", 2)]
    assert not any(c.executemany.called for c in conn.cursors)
    conn.commit.assert_not_called()


def test_backfill_apply_writes_pages_by_chunk_id():
    conn = _mysql_with([(2, "er-model.pdf", "2/a.pdf")], STORED)

    bf.backfill(conn, load_pdf=lambda key: b"%PDF", chunk_pdf=lambda data: REGENERATED, apply=True)

    (sql, rows), = [c.executemany.call_args.args for c in conn.cursors if c.executemany.called]
    assert sql == "UPDATE chunks SET page_start = %s, page_end = %s WHERE chunk_id = %s"
    assert rows == [(1, 1, 10), (1, 2, 11)]
    conn.commit.assert_called_once()


@pytest.mark.parametrize("regenerated", [
    [("first chunk", 1, 1)],                                    # different count
    [("first chunk", 1, 1), ("second chunk, edited", 1, 2)],   # different text
])
def test_backfill_skips_documents_that_no_longer_match(regenerated):
    conn = _mysql_with([(2, "er-model.pdf", "2/a.pdf")], STORED)

    report = bf.backfill(conn, load_pdf=lambda key: b"%PDF", chunk_pdf=lambda data: regenerated, apply=True)

    assert report["skipped"] == [(2, "er-model.pdf")]
    assert report["filled"] == []
    assert not any(c.executemany.called for c in conn.cursors)


def test_backfill_reports_documents_it_cannot_read():
    conn = _mysql_with([(2, "er-model.pdf", "2/a.pdf")], STORED)

    def missing(key):
        raise FileNotFoundError("NoSuchKey")

    report = bf.backfill(conn, load_pdf=missing, chunk_pdf=lambda data: REGENERATED, apply=True)

    assert report["errors"] == [(2, "er-model.pdf", "NoSuchKey")]
    assert "error: er-model.pdf (doc 2)" in bf.format_report(report)


def test_backfill_only_looks_at_ready_documents_with_missing_pages():
    sql = bf.DOCUMENTS_MISSING_PAGES_QUERY
    assert "d.status = 'ready'" in sql
    assert "c.page_start IS NULL" in sql


# ============================================================================
# 3. Search results carry the page
# ============================================================================

def test_vector_results_include_the_first_page():
    from backend.modules.search.service import execute_semantic_search

    with patch("backend.modules.search.service.get_cached_search", return_value=None), \
         patch("backend.modules.search.service.set_cached_search"), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[7]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors",
               return_value=[{"chunk_id": 42, "doc_id": 7, "score": 0.2}]), \
         patch("backend.modules.search.service.get_chunks_metadata",
               return_value={42: {"doc_title": "notes.pdf", "snippet": "text", "page": 12}}):
        results, _ = execute_semantic_search(user_id=1, query="weak entities")

    assert results[0]["page"] == 12


def test_chunk_metadata_selects_page_start():
    from backend.modules.search.db import get_chunks_metadata

    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [
        {"chunk_id": 42, "doc_id": 7, "snippet": "text", "doc_title": "notes.pdf", "page": 12},
    ]
    meta = get_chunks_metadata([42], conn=conn)

    assert "c.page_start AS page" in conn.cursor.return_value.execute.call_args.args[0]
    assert meta[42]["page"] == 12


def test_fulltext_results_include_the_first_page():
    from backend.modules.search.db import search_chunks_fulltext

    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [(42, 7, "notes.pdf", "text", 12)]
    results = search_chunks_fulltext(user_id=1, query="weak entities", conn=conn)

    assert "c.page_start AS page" in conn.cursor.return_value.execute.call_args.args[0]
    assert results[0]["page"] == 12


# ============================================================================
# 4. The passage endpoint
# ============================================================================

@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture
def auth_header():
    return {"Authorization": f"Bearer {generate_token(user_id=1, email='user1@example.com')}"}


def test_passage_endpoint_returns_text_and_pages(client, auth_header):
    passage = {"chunk_id": 42, "chunk_text": "Weak entities…", "page_start": 12, "page_end": 13}
    with patch("backend.modules.documents.routes.get_chunk", return_value=passage) as lookup:
        res = client.get("/api/documents/7/chunks/42", headers=auth_header)

    assert res.status_code == 200
    assert res.get_json() == passage
    lookup.assert_called_once_with(7, 42, 1)


def test_passage_endpoint_returns_404_for_someone_elses_or_mismatched_chunk(client, auth_header):
    with patch("backend.modules.documents.routes.get_chunk", return_value=None):
        res = client.get("/api/documents/7/chunks/42", headers=auth_header)
    assert res.status_code == 404


def test_passage_endpoint_requires_a_session(client):
    assert client.get("/api/documents/7/chunks/42").status_code == 401


def test_get_chunk_is_scoped_to_the_document_and_its_owner():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (42, "text", 12, 13)

    chunk = get_chunk(7, 42, 1, conn=conn)

    sql, params = conn.cursor.return_value.execute.call_args.args
    assert "WHERE c.chunk_id = %s AND c.doc_id = %s AND d.user_id = %s" in sql
    assert params == (42, 7, 1)
    assert chunk == {"chunk_id": 42, "chunk_text": "text", "page_start": 12, "page_end": 13}


# ============================================================================
# Integration (opt-in): real MySQL, TEMPORARY tables only
# ============================================================================

integration = pytest.mark.skipif(
    os.getenv("PRISM_MYSQL_INTEGRATION") != "1" or not os.getenv("MYSQL_URL"),
    reason="set PRISM_MYSQL_INTEGRATION=1 and MYSQL_URL to run against a real MySQL server",
)


@integration
def test_integration_pages_round_trip_and_scoping():
    import mysql.connector

    from backend.modules.auth.db import get_db_config
    from backend.modules.documents.db import insert_chunks

    conn = mysql.connector.connect(**get_db_config())
    try:
        cur = conn.cursor()
        cur.execute("CREATE TEMPORARY TABLE documents (doc_id INT PRIMARY KEY, user_id INT, title VARCHAR(255))")
        cur.execute("CREATE TEMPORARY TABLE chunks (chunk_id INT AUTO_INCREMENT PRIMARY KEY, doc_id INT NOT NULL,"
                    " chunk_text TEXT NOT NULL, chunk_index INT NOT NULL, page_start INT NULL, page_end INT NULL)")
        cur.execute("INSERT INTO documents VALUES (7, 1, 'er-model.pdf')")
        cur.close()

        insert_chunks(7, ["first passage", "second passage"], conn=conn, pages=[(3, 3), (3, 4)])
        cur = conn.cursor()
        cur.execute("SELECT chunk_id FROM chunks WHERE chunk_index = 1")
        chunk_id = cur.fetchone()[0]
        cur.close()

        assert get_chunk(7, chunk_id, 1, conn=conn) == {
            "chunk_id": chunk_id, "chunk_text": "second passage", "page_start": 3, "page_end": 4,
        }
        assert get_chunk(7, chunk_id, 2, conn=conn) is None   # another user
        assert get_chunk(8, chunk_id, 1, conn=conn) is None   # another document
    finally:
        conn.close()
