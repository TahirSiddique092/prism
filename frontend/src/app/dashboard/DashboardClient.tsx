"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export interface DocumentItem {
  doc_id: number;
  title: string;
  uploaded_at: string | null;
  status: "processing" | "ready" | "error";
  chunk_count: number;
}

interface DashboardClientProps {
  initialDocuments?: DocumentItem[];
}

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB

function formatUploadDate(isoString: string | null | undefined): string {
  if (!isoString) return "Just now";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return String(isoString);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return String(isoString);
  }
}

export default function DashboardClient({ initialDocuments = [] }: DashboardClientProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [documents, setDocuments] = useState<DocumentItem[]>(initialDocuments);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [topics, setTopics] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [docToDelete, setDocToDelete] = useState<DocumentItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [isRefreshing, setIsRefreshing] = useState(false);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setUploadError(null);
    const file = e.target.files?.[0];
    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Only .pdf files are accepted");
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setUploadError("File size limit exceeded (20MB max)");
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setSelectedFile(file);
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    setUploadError(null);

    if (!selectedFile) {
      setUploadError("Please select a PDF file to upload");
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Only .pdf files are accepted");
      return;
    }

    if (selectedFile.size > MAX_FILE_SIZE) {
      setUploadError("File size limit exceeded (20MB max)");
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      if (topics.trim()) {
        formData.append("topics", topics.trim());
      }

      const res = await fetch("/api/documents/upload", {
        method: "POST",
        body: formData,
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const message =
          typeof data?.error === "string"
            ? data.error
            : "Upload failed. Please try again.";
        setUploadError(message);
        return;
      }

      // Immediately add the new document with status "processing" to state
      const newDoc: DocumentItem = {
        doc_id: data.doc_id ?? Date.now(),
        title: selectedFile.name,
        uploaded_at: new Date().toISOString(),
        status: "processing",
        chunk_count: 0,
      };

      setDocuments((prev) => [newDoc, ...prev]);

      // Reset form fields
      setSelectedFile(null);
      setTopics("");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch {
      setUploadError("Network error while uploading. Please try again.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleConfirmDelete() {
    if (!docToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);

    try {
      const res = await fetch(`/api/documents/${docToDelete.doc_id}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const message =
          typeof data?.error === "string"
            ? data.error
            : "Failed to delete document";
        setDeleteError(message);
        return;
      }

      // Acceptance criteria: Deleted document disappears from the list without a full page reload
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docToDelete.doc_id));
      setDocToDelete(null);
    } catch {
      setDeleteError("Network error during document deletion.");
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleRefresh() {
    setIsRefreshing(true);
    try {
      const res = await fetch("/api/documents");
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setDocuments(data);
        }
      }
      router.refresh();
    } catch {
      // Graceful fallback
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <main className="main-content">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Document Library</h1>
          <p className="page-subtitle">
            Upload and manage PDFs. Each document is chunked, vectorized with pgvector, and linked to topics in Neo4j.
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
            aria-label="Refresh Status"
          >
            {isRefreshing ? (
              <span className="spinner" />
            ) : (
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M23 4v6h-6" />
                <path d="M1 20v-6h6" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
            )}
            Refresh Status
          </button>
        </div>
      </div>

      {/* Upload Card */}
      <div className="card" style={{ marginBottom: 32 }}>
        <div className="card-header">
          <h2
            className="card-title"
            style={{ fontSize: "1rem", display: "flex", alignItems: "center", gap: 8 }}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#3B82F6"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            Upload New Document
          </h2>
          <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            PDF format only • Max 20MB
          </span>
        </div>

        <div className="card-body">
          {uploadError && (
            <div className="alert-error" role="alert" data-testid="upload-error">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{uploadError}</span>
            </div>
          )}

          <form onSubmit={handleUpload}>
            {/* File Dropzone / Picker */}
            <div
              className="upload-dropzone"
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
              aria-label="Upload PDF dropzone"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                style={{ display: "none" }}
                onChange={handleFileChange}
                data-testid="file-input"
              />
              <div className="upload-icon-wrap">
                <svg
                  width="26"
                  height="26"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>

              {selectedFile ? (
                <div>
                  <p className="upload-title" style={{ color: "#60A5FA" }}>
                    {selectedFile.name}
                  </p>
                  <p className="upload-subtitle">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Click to change file
                  </p>
                </div>
              ) : (
                <div>
                  <p className="upload-title">
                    Select your PDF here, or <span style={{ color: "#60A5FA" }}>browse file</span>
                  </p>
                  <p className="upload-subtitle">
                    Academic papers, lecture notes, textbook chapters (Max 20MB)
                  </p>
                </div>
              )}
            </div>

            {/* Topic Tags & Submit Button */}
            <div
              style={{
                marginTop: 16,
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: 16,
                alignItems: "flex-end",
              }}
            >
              <div>
                <label className="form-label" htmlFor="topics">
                  Topic Tags (for Neo4j Graph relations)
                </label>
                <input
                  type="text"
                  id="topics"
                  name="topics"
                  className="form-input"
                  placeholder="e.g. Relational Algebra, Query Optimization, Joins"
                  value={topics}
                  onChange={(e) => setTopics(e.target.value)}
                  disabled={isUploading}
                  data-testid="topics-input"
                />
                <span className="form-hint">
                  Separate multiple topics with commas to build graph connections.
                </span>
              </div>

              <button
                type="submit"
                id="upload-btn"
                className="btn btn-primary"
                disabled={isUploading || !selectedFile}
                data-testid="upload-button"
              >
                {isUploading ? (
                  <>
                    <span className="spinner" />
                    <span>Uploading…</span>
                  </>
                ) : (
                  <>
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    <span>Upload & Vectorize</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Document List Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <h2 style={{ fontSize: "1.125rem", fontWeight: 600 }}>
          Uploaded Documents (<span data-testid="doc-count">{documents.length}</span>)
        </h2>
        <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
          Stored in MinIO • Vectors in Postgres
        </span>
      </div>

      {/* Populated Table or Empty State */}
      {documents.length > 0 ? (
        <div className="table-container" data-testid="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "42%" }}>Document Title</th>
                <th>Uploaded Date</th>
                <th>Chunks</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody data-testid="doc-table-body">
              {documents.map((doc) => (
                <tr key={doc.doc_id} data-testid={`doc-row-${doc.doc_id}`}>
                  <td>
                    <Link
                      href={`/documents/${doc.doc_id}`}
                      style={{
                        fontWeight: 600,
                        color: "#F8FAFC",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                      data-testid={`doc-title-${doc.doc_id}`}
                    >
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#EF4444"
                        strokeWidth="2"
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                      {doc.title}
                    </Link>
                  </td>
                  <td
                    style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}
                    data-testid={`doc-date-${doc.doc_id}`}
                  >
                    {formatUploadDate(doc.uploaded_at)}
                  </td>
                  <td>
                    <span
                      style={{
                        fontFamily: "var(--font-mono, monospace)",
                        fontSize: "0.75rem",
                        background: "rgba(255,255,255,0.05)",
                        padding: "2px 6px",
                        borderRadius: "4px",
                      }}
                      data-testid={`doc-chunks-${doc.doc_id}`}
                    >
                      {doc.chunk_count} chunks
                    </span>
                  </td>
                  <td>
                    {doc.status === "ready" && (
                      <span className="badge badge-ready" data-testid={`status-badge-${doc.doc_id}`}>
                        <span className="badge-dot" />
                        ready
                      </span>
                    )}
                    {doc.status === "processing" && (
                      <span
                        className="badge badge-processing"
                        data-testid={`status-badge-${doc.doc_id}`}
                      >
                        <span className="badge-dot" />
                        processing
                      </span>
                    )}
                    {doc.status === "error" && (
                      <span className="badge badge-error" data-testid={`status-badge-${doc.doc_id}`}>
                        <span className="badge-dot" />
                        error
                      </span>
                    )}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => {
                        setDeleteError(null);
                        setDocToDelete(doc);
                      }}
                      title="Delete Document"
                      aria-label={`Delete ${doc.title}`}
                      data-testid={`delete-btn-${doc.doc_id}`}
                    >
                      <svg
                        width="15"
                        height="15"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#EF4444"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        <line x1="10" y1="11" x2="10" y2="17" />
                        <line x1="14" y1="11" x2="14" y2="17" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state" data-testid="empty-state">
          <div className="empty-icon-wrap">
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <h3 className="empty-title">No documents uploaded yet</h3>
          <p className="empty-desc">
            Upload your study PDFs above to chunk, embed, and index them for natural language semantic search.
          </p>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => fileInputRef.current?.click()}
          >
            Upload First PDF
          </button>
        </div>
      )}

      {/* Native Confirmation Modal for Delete */}
      {docToDelete && (
        <div
          role="presentation"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(6, 9, 16, 0.75)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: 16,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !isDeleting) {
              setDocToDelete(null);
            }
          }}
        >
          <dialog
            open
            className="prism-dialog"
            style={{ position: "relative", margin: "auto" }}
            aria-labelledby="delete-dialog-title"
            aria-describedby="delete-dialog-desc"
            data-testid="delete-modal"
          >
            <div className="dialog-header">
              <div className="dialog-icon-danger">
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <div>
                <h3
                  id="delete-dialog-title"
                  style={{ fontSize: "1.125rem", fontWeight: 700, color: "#FFFFFF" }}
                >
                  Delete Document
                </h3>
                <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                  This action is permanent and cannot be undone.
                </p>
              </div>
            </div>

            <div className="dialog-body" id="delete-dialog-desc">
              {deleteError && (
                <div className="alert-error" style={{ marginBottom: 16 }}>
                  <span>{deleteError}</span>
                </div>
              )}
              Are you sure you want to delete{" "}
              <strong style={{ color: "#F8FAFC" }}>&ldquo;{docToDelete.title}&rdquo;</strong>?
              All associated text chunks, pgvector embeddings, and Neo4j topic relationships will be purged from the database.
            </div>

            <div className="dialog-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDocToDelete(null)}
                disabled={isDeleting}
                data-testid="cancel-delete-btn"
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                data-testid="confirm-delete-btn"
              >
                {isDeleting ? (
                  <>
                    <span className="spinner" />
                    <span>Deleting…</span>
                  </>
                ) : (
                  <span>Delete Document</span>
                )}
              </button>
            </div>
          </dialog>
        </div>
      )}
    </main>
  );
}
