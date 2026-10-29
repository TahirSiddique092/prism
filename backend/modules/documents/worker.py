import bisect
import logging

import fitz  # PyMuPDF
import nltk
from backend.modules.documents.storage import get_s3_client, BUCKET_NAME
from backend.modules.documents.db import update_document_status, insert_chunks

logger = logging.getLogger(__name__)


def _ensure_nltk():
    """Ensure NLTK sentence tokenizers are available, downloading if missing.

    Done lazily (not at import) so importing this module has no network/filesystem
    side effects — importing it must stay cheap for tests and the request path.
    """
    for resource in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{resource}")
        except (LookupError, OSError):
            nltk.download(resource, quiet=True)

# Chunking parameters (see AGENTS.md "Chunking" rule):
#   ~200-word target, hard cap of 250, 1–2 sentence overlap, min 20 words.
TARGET_WORDS = 200
MAX_WORDS = 250
MIN_CHUNK_WORDS = 20
OVERLAP_SENTENCES = 2


def count_words(text: str) -> int:
    return len(text.split())


def _chunk_with_bounds(sentences: list) -> list:
    """Group sentences into overlapping ~200-word chunks (hard cap 250 words).

    Returns [(chunk_text, first, last)], where ``first`` and ``last`` say where
    the chunk starts and ends: (sentence_index, None) for a whole sentence, or
    (sentence_index, word_index) for a word window cut from one oversized
    sentence. chunk_sentences() returns just the texts; chunk_pages() turns
    the bounds into page numbers (slice-27).

    Guarantees termination: the sentence index advances on every iteration, so
    an oversized sentence can never cause an infinite loop. A single sentence
    longer than the hard cap is split into fixed word windows.
    """
    stripped = [s.strip() for s in sentences]
    chunks = []
    current = []          # indices of the sentences in the in-progress chunk
    current_words = 0

    def emit(indices):
        text = " ".join(stripped[k] for k in indices)
        if count_words(text) >= MIN_CHUNK_WORDS:
            chunks.append((text, (indices[0], None), (indices[-1], None)))

    i = 0
    n = len(sentences)
    while i < n:
        sentence = stripped[i]
        if not sentence:
            i += 1
            continue

        sentence_words = count_words(sentence)

        # A single sentence larger than the cap can never fit a chunk; emit it
        # as its own fixed-size word windows so downstream limits still hold.
        if sentence_words > MAX_WORDS:
            if current:
                emit(current)
            current = []
            current_words = 0
            words = sentence.split()
            for start in range(0, len(words), MAX_WORDS):
                end = min(start + MAX_WORDS, len(words))
                chunks.append((" ".join(words[start:end]), (i, start), (i, end - 1)))
            i += 1
            continue

        if current_words + sentence_words > TARGET_WORDS and current_words > 0:
            # Finalise the current chunk, then start a new one that carries a
            # small overlap for context — but always consume THIS sentence so
            # the loop makes forward progress.
            emit(current)

            overlap = current[-OVERLAP_SENTENCES:]
            overlap_words = sum(count_words(stripped[k]) for k in overlap)
            # Drop the overlap if carrying it plus this sentence would blow the
            # hard cap (keeps every chunk <= MAX_WORDS).
            if overlap_words + sentence_words > MAX_WORDS:
                overlap = []
                overlap_words = 0

            current = overlap + [i]
            current_words = overlap_words + sentence_words
        else:
            current.append(i)
            current_words += sentence_words
        i += 1

    # Finalise trailing chunk.
    if current:
        emit(current)

    return chunks


def chunk_sentences(sentences: list) -> list:
    """Group sentences into overlapping ~200-word chunks (hard cap 250 words)."""
    return [text for text, _, _ in _chunk_with_bounds(sentences)]


def _word_spans(text: str) -> list:
    """(start, end) of each word, splitting exactly like str.split()."""
    spans = []
    start = None
    for pos, char in enumerate(text):
        if char.isspace():
            if start is not None:
                spans.append((start, pos))
                start = None
        elif start is None:
            start = pos
    if start is not None:
        spans.append((start, len(text)))
    return spans


def chunk_pages(page_texts: list, sentences: list) -> list:
    """Chunk a document and find the pages each chunk starts and ends on (slice-27).

    ``page_texts`` are joined with single spaces, as before sentence splitting,
    and ``sentences`` is nltk.sent_tokenize of that text. Punkt returns pieces
    of the text in order, so each sentence is located with a forward search.
    Returns [(chunk_text, page_start, page_end)], pages 1-based, or None for a
    chunk whose position can't be found. Chunk texts are exactly those of
    chunk_sentences(sentences).
    """
    text = " ".join(page_texts)
    page_starts = []
    offset = 0
    for page_text in page_texts:
        page_starts.append(offset)
        offset += len(page_text) + 1

    spans = []
    cursor = 0
    for sentence in sentences:
        piece = sentence.strip()
        start = text.find(piece, cursor) if piece else -1
        if start < 0:
            spans.append(None)
            continue
        spans.append((start, start + len(piece)))
        cursor = start + len(piece)

    def char_at(bound, at_end):
        sentence_index, word_index = bound
        span = spans[sentence_index]
        if span is None:
            return None
        if word_index is None:
            return span[1] - 1 if at_end else span[0]
        word_start, word_end = _word_spans(sentences[sentence_index].strip())[word_index]
        return span[0] + (word_end - 1 if at_end else word_start)

    def page_of(char):
        return None if char is None else bisect.bisect_right(page_starts, char)

    return [
        (chunk_text, page_of(char_at(first, False)), page_of(char_at(last, True)))
        for chunk_text, first, last in _chunk_with_bounds(sentences)
    ]


def extract_page_texts(pdf_bytes: bytes) -> list:
    """The text of each page of a PDF, in page order."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_text() for page in doc]


def chunk_document(page_texts: list) -> list:
    """Split a document's pages into chunks: [(chunk_text, page_start, page_end)].

    Shared by process_document and the page backfill (backend/db/backfill_chunk_pages.py),
    so both produce exactly the same chunks.
    """
    _ensure_nltk()
    sentences = nltk.sent_tokenize(" ".join(page_texts))
    return chunk_pages(page_texts, sentences)

def process_document(doc_id: int, minio_key: str):
    """Background task to extract text, chunk it, and save to database."""
    try:
        s3 = get_s3_client()
        response = s3.get_object(Bucket=BUCKET_NAME, Key=minio_key)
        pdf_bytes = response['Body'].read()
    except Exception as e:
        logger.error(f"Failed to fetch {minio_key} from MinIO: {e}")
        update_document_status(doc_id, 'error')
        return

    try:
        page_texts = extract_page_texts(pdf_bytes)
        if not " ".join(page_texts).strip():
            # No text layer
            update_document_status(doc_id, 'error')
            return

        chunks = chunk_document(page_texts)

        # Insert raw chunks, with the pages each one covers, into MySQL
        insert_chunks(
            doc_id,
            [chunk_text for chunk_text, _, _ in chunks],
            pages=[(page_start, page_end) for _, page_start, page_end in chunks],
        )

    except Exception as e:
        logger.error(f"Failed to process document {doc_id}: {e}")
        update_document_status(doc_id, 'error')
        return

    # --- SLICE-07: Embedding and pgvector insert ---
    try:
        from backend.modules.documents.db import (
            get_chunks_for_document,
            delete_chunks,
            get_document_owner,
        )
        from backend.modules.documents.embed import get_embeddings
        from backend.modules.postgres import run_pg
        import json

        db_chunks = get_chunks_for_document(doc_id)
        if not db_chunks:
            update_document_status(doc_id, 'ready')
            _invalidate_owner_cache(doc_id)
            return

        chunk_texts = [row['chunk_text'] for row in db_chunks]
        chunk_ids = [row['chunk_id'] for row in db_chunks]

        # Compute embeddings
        embeddings = get_embeddings(chunk_texts)

        insert_query = "INSERT INTO chunk_vectors (chunk_id, doc_id, embedding) VALUES (%s, %s, %s)"
        data = [(c_id, doc_id, json.dumps(emb)) for c_id, emb in zip(chunk_ids, embeddings)]

        def insert_vectors(pg_conn):
            # One transaction on the pooled connection: every vector or none.
            with pg_conn:
                with pg_conn.cursor() as cursor:
                    cursor.executemany(insert_query, data)

        run_pg(insert_vectors)

        # Everything succeeded — the document is now searchable, so drop the
        # owner's cached (possibly empty) search results that were computed
        # before these vectors existed. Otherwise a search run between upload
        # and this point would stay pinned for the full cache TTL.
        update_document_status(doc_id, 'ready')
        _invalidate_owner_cache(doc_id)

    except Exception as e:
        logger.error(f"Failed to embed chunks for doc {doc_id}: {e}")
        # Clean up MySQL chunks on failure
        from backend.modules.documents.db import delete_chunks
        delete_chunks(doc_id)
        update_document_status(doc_id, 'error')


def _invalidate_owner_cache(doc_id: int):
    """Best-effort invalidation of the document owner's search cache."""
    try:
        from backend.modules.documents.db import get_document_owner
        from backend.modules.cache import invalidate_user_cache

        owner_id = get_document_owner(doc_id)
        if owner_id is not None:
            invalidate_user_cache(owner_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate cache for owner of doc {doc_id}: {e}")
