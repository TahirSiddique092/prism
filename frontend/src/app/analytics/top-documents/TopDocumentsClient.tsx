"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  sortTopDocsByCount,
  type TopDocumentItem,
} from "@/lib/analytics";

export default function TopDocumentsClient() {
  const router = useRouter();
  const [items, setItems] = useState<TopDocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;

    async function fetchTopDocuments() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/analytics/top-documents");
        if (res.status === 401) {
          router.push("/login");
          return;
        }
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.error || `Failed to load top documents (${res.status})`);
        }
        const data = await res.json();
        if (!isCancelled) {
          if (Array.isArray(data)) {
            // Guarantee appearance count descending
            setItems(sortTopDocsByCount(data));
          } else {
            setItems([]);
          }
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err instanceof Error ? err.message : "Failed to load top documents");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    fetchTopDocuments();

    return () => {
      isCancelled = true;
    };
  }, [router]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Top Documents</h1>
          <p className="page-subtitle">
            Most frequently surfaced documents across search results
          </p>
        </div>
      </div>

      {loading && (
        <div className="table-container" style={{ padding: 48, textAlign: "center" }}>
          <span className="spinner spinner-lg" style={{ margin: "0 auto 12px" }} />
          <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
            Loading top documents…
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
              fetch("/api/analytics/top-documents")
                .then(async (res) => {
                  if (res.status === 401) {
                    router.push("/login");
                    return;
                  }
                  if (!res.ok) {
                    const b = await res.json().catch(() => ({}));
                    throw new Error(b.error || `Failed to load top documents (${res.status})`);
                  }
                  const d = await res.json();
                  const sorted = Array.isArray(d) ? sortTopDocsByCount(d) : [];
                  setItems(sorted);
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
              <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
              <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
              <path d="M4 22h16" />
              <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
              <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
              <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
            </svg>
          </div>
          <h3 className="empty-title">No search appearances yet</h3>
          <p className="empty-desc">
            No documents have appeared in search results yet. Run searches against your library to see which documents surface most often.
          </p>
          <Link href="/search" className="btn btn-primary btn-sm">
            Go to Search
          </Link>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "80px" }}>Rank</th>
                <th>Document Title</th>
                <th style={{ width: "190px", textAlign: "right" }}>Appearance Count</th>
                <th style={{ width: "210px", textAlign: "right" }}>Avg. Similarity Score</th>
              </tr>
            </thead>
            <tbody>
              {items.map((doc, idx) => (
                <tr key={doc.doc_id}>
                  <td>
                    <span className="rank-badge">#{idx + 1}</span>
                  </td>
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
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono, monospace)" }}>
                    <span className="count-pill">{doc.appearance_count} appearances</span>
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono, monospace)" }}>
                    {doc.avg_score !== null && doc.avg_score !== undefined ? (
                      // avg_score from the backend is average cosine DISTANCE
                      // (lower = closer). Display it as a similarity (higher =
                      // more relevant) so the column matches its "Similarity" label.
                      <span className="result-score">{(1 - doc.avg_score).toFixed(4)}</span>
                    ) : (
                      <span style={{ color: "var(--color-text-muted)" }}>—</span>
                    )}
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
