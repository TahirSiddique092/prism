import fitz  # PyMuPDF
import nltk
from backend.modules.documents.storage import get_s3_client, BUCKET_NAME
from backend.modules.documents.db import update_document_status, insert_chunks

# Ensure NLTK tokenizers are downloaded
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt')
    nltk.download('punkt_tab')

def count_words(text: str) -> int:
    return len(text.split())

def process_document(doc_id: int, minio_key: str):
    """Background task to extract text, chunk it, and save to database."""
    try:
        s3 = get_s3_client()
        response = s3.get_object(Bucket=BUCKET_NAME, Key=minio_key)
        pdf_bytes = response['Body'].read()
    except Exception as e:
        print(f"Failed to fetch {minio_key} from MinIO: {e}")
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
            
        sentences = nltk.sent_tokenize(text)
        
        chunks = []
        current_chunk_sentences = []
        current_word_count = 0
        
        max_words = 250
        
        i = 0
        while i < len(sentences):
            sentence = sentences[i].strip()
            if not sentence:
                i += 1
                continue
                
            sentence_words = count_words(sentence)
            
            # If adding this sentence exceeds max words (and we already have some text)
            if current_word_count + sentence_words > max_words and current_word_count > 0:
                # Finalize current chunk
                chunk_text = " ".join(current_chunk_sentences)
                if count_words(chunk_text) >= 20:
                    chunks.append(chunk_text)
                
                # Overlap: keep last 1 or 2 sentences
                overlap = current_chunk_sentences[-2:] if len(current_chunk_sentences) >= 2 else current_chunk_sentences[-1:]
                current_chunk_sentences = overlap
                current_word_count = sum(count_words(s) for s in current_chunk_sentences)
                
                # Do not increment i, so the current sentence gets added to the new chunk
            else:
                current_chunk_sentences.append(sentence)
                current_word_count += sentence_words
                i += 1
                
        # Finalize the last chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            if count_words(chunk_text) >= 20:
                chunks.append(chunk_text)
                
        # Insert raw chunks into MySQL
        insert_chunks(doc_id, chunks)
        
    except Exception as e:
        print(f"Failed to process document {doc_id}: {e}")
        update_document_status(doc_id, 'error')
        return

    # --- SLICE-07: Embedding and pgvector insert ---
    try:
        from backend.modules.documents.db import get_chunks_for_document, delete_chunks, get_postgres_conn
        from backend.modules.documents.embed import get_embeddings
        import json

        db_chunks = get_chunks_for_document(doc_id)
        if not db_chunks:
            update_document_status(doc_id, 'ready')
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

            # Everything succeeded
            update_document_status(doc_id, 'ready')

        except Exception as e:
            pg_conn.rollback()
            raise e
        finally:
            pg_conn.close()

    except Exception as e:
        print(f"Failed to embed chunks for doc {doc_id}: {e}")
        # Clean up MySQL chunks on failure
        from backend.modules.documents.db import delete_chunks
        delete_chunks(doc_id)
        update_document_status(doc_id, 'error')
