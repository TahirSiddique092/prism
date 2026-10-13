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


def chunk_sentences(sentences: list) -> list:
    """Group sentences into overlapping ~200-word chunks (hard cap 250 words).

    Guarantees termination: the sentence index advances on every iteration, so
    an oversized sentence can never cause an infinite loop. A single sentence
    longer than the hard cap is split into fixed word windows.
    """
    chunks = []
    current = []          # sentences accumulated for the in-progress chunk
    current_words = 0

    def flush():
        nonlocal current, current_words
        if current:
            text = " ".join(current)
            if count_words(text) >= MIN_CHUNK_WORDS:
                chunks.append(text)
        current = []
        current_words = 0

    i = 0
    n = len(sentences)
    while i < n:
        sentence = sentences[i].strip()
        if not sentence:
            i += 1
            continue

        sentence_words = count_words(sentence)

        # A single sentence larger than the cap can never fit a chunk; emit it
        # as its own fixed-size word windows so downstream limits still hold.
        if sentence_words > MAX_WORDS:
            flush()
            words = sentence.split()
            for start in range(0, len(words), MAX_WORDS):
                chunks.append(" ".join(words[start:start + MAX_WORDS]))
            i += 1
            continue

        if current_words + sentence_words > TARGET_WORDS and current_words > 0:
            # Finalise the current chunk, then start a new one that carries a
            # small overlap for context — but always consume THIS sentence so
            # the loop makes forward progress.
            text = " ".join(current)
            if count_words(text) >= MIN_CHUNK_WORDS:
                chunks.append(text)

            overlap = current[-OVERLAP_SENTENCES:]
            overlap_words = sum(count_words(s) for s in overlap)
            # Drop the overlap if carrying it plus this sentence would blow the
            # hard cap (keeps every chunk <= MAX_WORDS).
            if overlap_words + sentence_words > MAX_WORDS:
                overlap = []
                overlap_words = 0

            current = overlap + [sentence]
            current_words = overlap_words + sentence_words
            i += 1
        else:
            current.append(sentence)
            current_words += sentence_words
            i += 1

    # Finalise trailing chunk.
    if current:
        text = " ".join(current)
        if count_words(text) >= MIN_CHUNK_WORDS:
            chunks.append(text)

    return chunks

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
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = []
        for page in doc:
            full_text.append(page.get_text())

        text = " ".join(full_text)
        if not text.strip():
            # No text layer
            update_document_status(doc_id, 'error')
            return

        _ensure_nltk()
        sentences = nltk.sent_tokenize(text)
        chunks = chunk_sentences(sentences)

        # Insert raw chunks into MySQL
        insert_chunks(doc_id, chunks)

    except Exception as e:
        logger.error(f"Failed to process document {doc_id}: {e}")
        update_document_status(doc_id, 'error')
        return

    # --- SLICE-07: Embedding and pgvector insert ---
    try:
        from backend.modules.documents.db import (
            get_chunks_for_document,
            delete_chunks,
            get_postgres_conn,
            get_document_owner,
        )
        from backend.modules.documents.embed import get_embeddings
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

        pg_conn = get_postgres_conn()
        if not pg_conn:
            raise Exception("Could not connect to Postgres")

        try:
            with pg_conn.cursor() as cursor:
                insert_query = "INSERT INTO chunk_vectors (chunk_id, doc_id, embedding) VALUES (%s, %s, %s)"
                data = [(c_id, doc_id, json.dumps(emb)) for c_id, emb in zip(chunk_ids, embeddings)]
                cursor.executemany(insert_query, data)
            pg_conn.commit()

            # Everything succeeded — the document is now searchable, so drop the
            # owner's cached (possibly empty) search results that were computed
            # before these vectors existed. Otherwise a search run between upload
            # and this point would stay pinned for the full cache TTL.
            update_document_status(doc_id, 'ready')
            _invalidate_owner_cache(doc_id)

        except Exception as e:
            pg_conn.rollback()
            raise e
        finally:
            pg_conn.close()

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
