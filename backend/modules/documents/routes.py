import uuid
from flask import Blueprint, request, jsonify, g
from werkzeug.utils import secure_filename

try:
    from backend.modules.documents.storage import upload_file
    from backend.modules.documents.db import insert_document
except ImportError:
    from modules.documents.storage import upload_file
    from modules.documents.db import insert_document

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

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
        
    # 6. Trigger background chunking task
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
