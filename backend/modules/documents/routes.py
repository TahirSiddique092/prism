import json
import logging
import uuid
from flask import Blueprint, request, jsonify, g, current_app
from werkzeug.utils import secure_filename

try:
    from backend.modules.documents.storage import (
        upload_file,
        delete_file,
        generate_presigned_url,
    )
    from backend.modules.documents.db import (
        insert_document,
        get_user_documents,
        get_document_by_id,
        delete_document,
        delete_chunk_vectors,
    )
    from backend.modules.cache import invalidate_user_cache
    from backend.modules.graph import write_document_to_graph_async, get_related_documents
except ImportError:
    from modules.documents.storage import (
        upload_file,
        delete_file,
        generate_presigned_url,
    )
    from modules.documents.db import (
        insert_document,
        get_user_documents,
        get_document_by_id,
        delete_document,
        delete_chunk_vectors,
    )
    from modules.cache import invalidate_user_cache
    from modules.graph import write_document_to_graph_async, get_related_documents

logger = logging.getLogger(__name__)

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def _parse_topics_from_form():
    """Extract topic tags from the upload form.

    Accepts repeated `topics` / `topics[]` fields, a single JSON-array string,
    or comma-separated values. Returns a flat list of raw strings; normalisation
    (trim/lowercase/dedupe) happens in the graph module.
    """
    raw = request.form.getlist("topics") + request.form.getlist("topics[]")
    topics = []
    for item in raw:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if not s:
            continue
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    topics.extend(str(x) for x in parsed)
                    continue
            except (ValueError, TypeError):
                pass
        if "," in s:
            topics.extend(part for part in s.split(","))
        else:
            topics.append(s)
    return topics

@documents_bp.route("", methods=["GET"], strict_slashes=False)
def list_documents():
    """List documents belonging to the authenticated user.
    
    Response: [{ doc_id, title, uploaded_at, status, chunk_count }]
    """
    user_id = g.user_id
    try:
        docs = get_user_documents(user_id)
        return jsonify(docs), 200
    except Exception as e:
        logger.error(f"Error listing documents for user {user_id}: {e}")
        return jsonify({"error": f"Failed to list documents: {str(e)}"}), 500

@documents_bp.route("/<int:doc_id>/url", methods=["GET"])
def get_document_view_url(doc_id: int):
    """Retrieve temporary pre-signed MinIO URL for the user's document.
    
    Response: { view_url: "..." }
    Returns 404 if doc does not exist or does not belong to user.
    """
    user_id = g.user_id
    try:
        doc = get_document_by_id(doc_id, user_id=user_id)
        if not doc:
            return jsonify({"error": "Document not found"}), 404

        minio_key = doc.get("minio_key")
        if not minio_key:
            return jsonify({"error": "Storage key missing for document"}), 404

        view_url = generate_presigned_url(minio_key, expires_in=3600)
        return jsonify({"view_url": view_url}), 200
    except Exception as e:
        logger.error(f"Error retrieving view url for doc {doc_id}: {e}")
        return jsonify({"error": f"Failed to retrieve document view URL: {str(e)}"}), 500

@documents_bp.route("/<int:doc_id>/related", methods=["GET"])
def get_related_documents_route(doc_id: int):
    """Find documents that share the most topics with this one (Slice 13).

    Response: [{ doc_id, title, shared_topics }] — up to 5, ordered by shared
    topic count descending, scoped to the authenticated user's documents.
    Returns 404 if the document does not exist or belong to the user.
    Returns [] (not an error) when there are no related documents.
    """
    user_id = g.user_id
    try:
        # Ownership is authoritative in MySQL — 404 if the doc isn't the user's.
        doc = get_document_by_id(doc_id, user_id=user_id)
        if not doc:
            return jsonify({"error": "Document not found"}), 404

        # get_related_documents degrades gracefully to [] on any Neo4j failure.
        related = get_related_documents(doc_id, user_id)
        return jsonify(related), 200
    except Exception as e:
        logger.error(f"Error retrieving related docs for doc {doc_id}: {e}")
        return jsonify({"error": f"Failed to retrieve related documents: {str(e)}"}), 500


@documents_bp.route("/<int:doc_id>", methods=["DELETE"])
def delete_document_route(doc_id: int):
    """Delete a document and cascade its data.
    
    - Deletes document row from MySQL (fires before_document_delete trigger and cascades chunks)
    - Deletes chunk_vectors from pgvector
    - Deletes file from MinIO after MySQL deletion succeeds
    - Invalidates user's Redis cache
    - Response: { message: "deleted" }
    - Returns 404 if doc does not exist or does not belong to user
    """
    user_id = g.user_id
    try:
        # Check existence and ownership
        doc = get_document_by_id(doc_id, user_id=user_id)
        if not doc:
            return jsonify({"error": "Document not found"}), 404

        minio_key = doc.get("minio_key")

        # 1. Delete from MySQL — trigger handles deletion_audit and cascade chunks
        deleted = delete_document(doc_id, user_id=user_id)
        if not deleted:
            return jsonify({"error": "Document not found"}), 404

        # 2. Cleanup chunk_vectors in pgvector
        try:
            delete_chunk_vectors(doc_id)
        except Exception as e:
            logger.warning(f"Failed to cleanup chunk vectors for doc {doc_id}: {e}")

        # 3. Delete file from MinIO after MySQL deletion succeeds
        if minio_key:
            try:
                delete_file(minio_key)
            except Exception as e:
                logger.warning(f"Failed to delete file {minio_key} from MinIO: {e}")

        # 4. Invalidate the user's Redis cache
        try:
            invalidate_user_cache(user_id)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for user {user_id}: {e}")

        return jsonify({"message": "deleted"}), 200
    except Exception as e:
        logger.error(f"Error deleting doc {doc_id}: {e}")
        return jsonify({"error": f"Failed to delete document: {str(e)}"}), 500

@documents_bp.route("/upload", methods=["POST"])
def upload_document():
    # 1. Size check via headers
    if request.content_length and request.content_length > MAX_FILE_SIZE:
        return jsonify({"error": "File size limit exceeded (20MB max)"}), 413
        
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
        
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
        
    # 2. File type validation
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only .pdf files are accepted"}), 400
        
    if file.mimetype != "application/pdf":
        return jsonify({"error": "Invalid mime type, expected application/pdf"}), 400

    # 3. Size check via read (fallback if content_length is missing/spoofed)
    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        return jsonify({"error": "File size limit exceeded (20MB max)"}), 413
    
    file.seek(0) # reset pointer for upload
        
    user_id = g.user_id
    
    filename = secure_filename(file.filename)
    title = filename if filename else "Untitled Document"
    
    # Generate minio key: {user_id}/{uuid4}.pdf
    file_uuid = uuid.uuid4()
    minio_key = f"{user_id}/{file_uuid}.pdf"
    
    # 4. Upload to MinIO
    try:
        upload_file(file, minio_key)
    except Exception as e:
        return jsonify({"error": f"Failed to upload to storage: {str(e)}"}), 500
        
    # 5. Insert into MySQL
    try:
        doc_id = insert_document(user_id=user_id, title=title, minio_key=minio_key)
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    # Invalidate search cache for this user
    try:
        invalidate_user_cache(user_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate cache after upload for user {user_id}: {e}")

    # 6. Write the topic graph to Neo4j (non-blocking; failure never fails upload)
    try:
        topics = _parse_topics_from_form()
        email = g.user.get("email") if getattr(g, "user", None) else None
        sync_graph = current_app.config.get("GRAPH_WRITE_SYNC", False)
        write_document_to_graph_async(
            user_id=user_id,
            email=email,
            doc_id=doc_id,
            title=title,
            topics=topics,
            sync=sync_graph,
        )
    except Exception as e:
        logger.warning(f"Failed to dispatch graph write for doc {doc_id}: {e}")

    # 7. Trigger background chunking task
    try:
        from backend.modules.documents.worker import process_document
        import threading
        threading.Thread(target=process_document, args=(doc_id, minio_key)).start()
    except Exception as e:
        # We don't fail the upload if background task fails to start, but we should log it
        print(f"Warning: Failed to start background task for doc {doc_id}: {e}")
        
    return jsonify({
        "doc_id": doc_id,
        "minio_key": minio_key
    }), 201

