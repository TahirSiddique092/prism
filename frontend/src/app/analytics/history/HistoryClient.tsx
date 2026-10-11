"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  formatDateTime,
  sortHistoryByRank,
  type SearchHistoryItem,
} from "@/lib/analytics";

export { formatDateTime };

export default function HistoryClient() {
  const router = useRouter();
  const [items, setItems] = useState<SearchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;

    async function fetchHistory() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/analytics/history");
        if (res.status === 401) {
          router.push("/login");
          return;
        }
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.error || `Failed to load search history (${res.status})`);
        }
        const data = await res.json();
        if (!isCancelled) {
          if (Array.isArray(data)) {
            // Guarantee rank ascending (rank 1 at top)
            setItems(sortHistoryByRank(data));
          } else {
            setItems([]);
          }
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err instanceof Error ? err.message : "Failed to load search history");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    fetchHistory();

    return () => {
      isCancelled = true;
    };
  }, [router]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Search Query History</h1>
          <p className="page-subtitle">
            Past queries ranked by frequency using SQL window functions
          </p>
        </div>
      </div>

      {loading && (
        <div className="table-container" style={{ padding: 48, textAlign: "center" }}>
          <span className="spinner spinner-lg" style={{ margin: "0 auto 12px" }} />
          <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
            Loading search history…
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
              fetch("/api/analytics/history")
                .then(async (res) => {
                  if (res.status === 401) {
                    router.push("/login");
                    return;
                  }
                  if (!res.ok) {
                    const b = await res.json().catch(() => ({}));
                    throw new Error(b.error || `Failed to load search history (${res.status})`);
                  }
                  const d = await res.json();
                  const sorted = Array.isArray(d) ? sortHistoryByRank(d) : [];
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
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <h3 className="empty-title">No search queries yet</h3>
          <p className="empty-desc">
            You haven&apos;t run any searches yet. Try searching your document library to build up your query history and frequency rankings.
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
                <th style={{ width: "90px" }}>Rank</th>
                <th>Query</th>
                <th style={{ width: "160px", textAlign: "right" }}>Search Count</th>
                <th style={{ width: "220px", textAlign: "right" }}>Last Searched</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => (
                <tr key={`${item.query_text}-${idx}`}>
                  <td>
                    <span className="rank-badge">#{item.query_rank}</span>
                  </td>
                  <td style={{ fontWeight: 500, color: "var(--color-text-primary)" }}>
                    <Link
                      href={`/search?q=${encodeURIComponent(item.query_text)}`}
                      className="table-query-link"
                      title="Run this search"
                    >
                      {item.query_text}
                    </Link>
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono, monospace)" }}>
                    {item.search_count}
                  </td>
                  <td style={{ textAlign: "right", color: "var(--color-text-muted)" }}>
                    {formatDateTime(item.last_searched)}
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
