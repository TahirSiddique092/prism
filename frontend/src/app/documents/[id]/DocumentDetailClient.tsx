"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LocalTime from "@/components/LocalTime";
import PdfViewer from "@/components/PdfViewer";

export interface DocumentDetail {
  doc_id: number;
  title: string;
  uploaded_at: string | null;
  status: "processing" | "ready" | "error";
  chunk_count: number;
  topics: string[];
}

export interface RelatedDocument {
  doc_id: number;
  title: string;
  shared_topics: number;
}

interface DocumentDetailClientProps {
  detail: DocumentDetail;
  related: RelatedDocument[];
}

function StatusBadge({ status }: { status: DocumentDetail["status"] }) {
  const cls =
    status === "ready"
      ? "badge-ready"
      : status === "error"
        ? "badge-error"
        : "badge-processing";
  return (
    <span className={`badge ${cls}`} data-testid="detail-status-badge">
      <span className="badge-dot" />
      {status}
    </span>
  );
}

const FileIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="#EF4444"
    strokeWidth="2"
    aria-hidden="true"
  >
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

export default function DocumentDetailClient({
  detail,
  related,
}: DocumentDetailClientProps) {
  const [viewUrl, setViewUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(true);
  const [pdfError, setPdfError] = useState<string | null>(null);

  // Fetch the pre-signed URL fresh on mount so the embedded viewer never points
  // at a link that expired between server render and user interaction.
  useEffect(() => {
    let cancelled = false;

    async function loadViewUrl() {
      setPdfLoading(true);
      setPdfError(null);
      try {
        const res = await fetch(`/api/documents/${detail.doc_id}/url`);
        const data = await res.json().catch(() => ({}));
        if (cancelled) return;

        if (!res.ok || typeof data?.view_url !== "string") {
          setPdfError(
            typeof data?.error === "string"
              ? data.error
              : "Unable to load the document preview."
          );
          return;
        }
        setViewUrl(data.view_url);
      } catch {
        if (!cancelled) {
          setPdfError("Network error while loading the document preview.");
        }
      } finally {
        if (!cancelled) setPdfLoading(false);
      }
    }

    loadViewUrl();
    return () => {
      cancelled = true;
    };
  }, [detail.doc_id]);

  return (
    <main className="main-content">
      {/* Breadcrumb / back link */}
      <Link
        href="/dashboard"
        className="detail-back-link"
        data-testid="back-to-dashboard"
      >
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <line x1="19" y1="12" x2="5" y2="12" />
          <polyline points="12 19 5 12 12 5" />
        </svg>
        Back to Document Library
      </Link>

      {/* Header */}
      <div className="page-header">
        <div>
          <h1
            className="page-title"
            style={{ display: "flex", alignItems: "center", gap: 10 }}
            data-testid="detail-title"
          >
            <FileIcon />
            {detail.title}
          </h1>
          <p className="page-subtitle">
            Document metadata, topic relationships, and the original source PDF.
          </p>
        </div>
      </div>

      {/* Metadata card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-body">
          <div className="detail-meta-grid">
            <div className="detail-meta-item">
              <span className="detail-meta-label">Uploaded</span>
              <span className="detail-meta-value" data-testid="detail-uploaded-at">
                <LocalTime iso={detail.uploaded_at} />
              </span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Status</span>
              <span className="detail-meta-value">
                <StatusBadge status={detail.status} />
              </span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Chunks</span>
              <span className="detail-meta-value" data-testid="detail-chunk-count">
                <span className="count-pill">{detail.chunk_count} chunks</span>
              </span>
            </div>
          </div>

          {/* Topic tags */}
          <div className="detail-topics" data-testid="detail-topics">
            <span className="detail-meta-label" style={{ marginBottom: 8 }}>
              Topic Tags
            </span>
            {detail.topics.length > 0 ? (
              <div className="topic-tag-list">
                {detail.topics.map((topic) => (
                  <span
                    key={topic}
                    className="topic-tag"
                    data-testid={`topic-tag-${topic}`}
                  >
                    {topic}
                  </span>
                ))}
              </div>
            ) : (
              <span
                style={{ color: "var(--color-text-muted)", fontSize: "0.8125rem" }}
                data-testid="no-topics"
              >
                No topics tagged
              </span>
            )}
          </div>
        </div>
      </div>

      {/* PDF viewer (full width), related documents below */}
      <div className="detail-layout">
        {/* Inline PDF viewer */}
        <div className="card detail-viewer-card">
          <div className="card-header">
            <h2 className="card-title" style={{ fontSize: "1rem" }}>
              Document Preview
            </h2>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
              Served from object storage
            </span>
          </div>
          <div className="detail-viewer-body">
            {pdfLoading && (
              <div className="detail-viewer-state" data-testid="pdf-loading">
                <span className="spinner spinner-lg" style={{ marginBottom: 12 }} />
                <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
                  Loading document preview…
                </p>
              </div>
            )}

            {!pdfLoading && pdfError && (
              <div className="detail-viewer-state" data-testid="pdf-error">
                <svg
                  width="28"
                  height="28"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#f87171"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ marginBottom: 10 }}
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem", marginBottom: 12 }}>
                  {pdfError}
                </p>
                <a
                  className="btn btn-secondary btn-sm"
                  href={`/api/documents/${detail.doc_id}/open`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open in new tab
                </a>
              </div>
            )}

            {!pdfLoading && !pdfError && viewUrl && (
              <PdfViewer
                key={viewUrl}
                url={viewUrl}
                title={detail.title}
                openHref={`/api/documents/${detail.doc_id}/open`}
              />
            )}
          </div>
        </div>

        {/* Related documents */}
        <div className="card detail-related-card">
          <div className="card-header">
            <h2 className="card-title" style={{ fontSize: "1rem" }}>
              Related Documents
            </h2>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
              By shared topics
            </span>
          </div>
          <div className="card-body">
            {related.length > 0 ? (
              <ul className="related-list" data-testid="related-list">
                {related.map((doc) => (
                  <li key={doc.doc_id}>
                    <Link
                      href={`/documents/${doc.doc_id}`}
                      className="related-item"
                      data-testid={`related-item-${doc.doc_id}`}
                    >
                      <span className="related-item-title">
                        <FileIcon />
                        {doc.title}
                      </span>
                      <span
                        className="related-shared"
                        data-testid={`related-shared-${doc.doc_id}`}
                        title="Number of topics shared with this document"
                      >
                        {doc.shared_topics} shared
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <div
                style={{
                  color: "var(--color-text-muted)",
                  fontSize: "0.875rem",
                  padding: "8px 0",
                }}
                data-testid="no-related"
              >
                No related documents found
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
