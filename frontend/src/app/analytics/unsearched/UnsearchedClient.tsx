"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  formatDate,
  UNSEARCHED_NUDGE_MESSAGE,
  type UnsearchedDocumentItem,
} from "@/lib/analytics";

export { formatDate };

export default function UnsearchedClient() {
  const router = useRouter();
  const [items, setItems] = useState<UnsearchedDocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;

    async function fetchUnsearched() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/analytics/unsearched");
        if (res.status === 401) {
          router.push("/login");
          return;
        }
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.error || `Failed to load unsearched documents (${res.status})`);
        }
        const data = await res.json();
        if (!isCancelled) {
          setItems(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err instanceof Error ? err.message : "Failed to load unsearched documents");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    fetchUnsearched();

    return () => {
      isCancelled = true;
    };
  }, [router]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Unsearched Documents</h1>
          <p className="page-subtitle">
            Documents that have never appeared in any search result
          </p>
        </div>
      </div>

      {/* Acceptance criteria nudge message */}
      <div className="analytics-nudge" role="note">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>{UNSEARCHED_NUDGE_MESSAGE}</span>
      </div>

      {loading && (
        <div className="table-container" style={{ padding: 48, textAlign: "center" }}>
          <span className="spinner spinner-lg" style={{ margin: "0 auto 12px" }} />
          <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
            Loading unsearched documents…
          </p>
        </div>
      )}

      {error && !loading && (
        <div className="alert-error" role="alert">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span style={{ flex: 1 }}>{error}</span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setLoading(true);
              setError(null);
              fetch("/api/analytics/unsearched")
                .then(async (res) => {
                  if (res.status === 401) {
                    router.push("/login");
                    return;
                  }
                  if (!res.ok) {
                    const b = await res.json().catch(() => ({}));
                    throw new Error(b.error || `Failed to load unsearched documents (${res.status})`);
                  }
                  const d = await res.json();
                  setItems(Array.isArray(d) ? d : []);
                })
                .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
                .finally(() => setLoading(false));
            }}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon-wrap">
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <h3 className="empty-title">All documents have been searched</h3>
          <p className="empty-desc">
            Every document in your library has surfaced in at least one search result.
          </p>
          <Link href="/dashboard" className="btn btn-secondary btn-sm">
            View Library
          </Link>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Document Title</th>
                <th style={{ width: "220px", textAlign: "right" }}>Upload Date</th>
              </tr>
            </thead>
            <tbody>
              {items.map((doc) => (
                <tr key={doc.doc_id}>
                  <td style={{ fontWeight: 500, color: "var(--color-text-primary)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <svg
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        style={{ color: "var(--color-primary)", flexShrink: 0 }}
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                      <span>{doc.title}</span>
                    </div>
                  </td>
                  <td style={{ textAlign: "right", color: "var(--color-text-muted)" }}>
                    {formatDate(doc.uploaded_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
