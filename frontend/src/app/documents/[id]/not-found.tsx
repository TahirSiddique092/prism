import Link from "next/link";
import AppHeader from "@/components/AppHeader";

/**
 * 404 for /documents/:doc_id (slice-20).
 *
 * Rendered via `notFound()` when a doc_id doesn't exist or doesn't belong to
 * the current user. Ownership mismatches surface as "not found" so the page
 * never leaks the existence of another user's document.
 */
export default function DocumentNotFound() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <AppHeader />
      <main className="main-content">
        <div className="empty-state" data-testid="document-not-found">
          <div className="empty-icon-wrap">
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
          </div>
          <h3 className="empty-title">Document not found</h3>
          <p className="empty-desc">
            This document doesn&apos;t exist or isn&apos;t part of your library.
            It may have been deleted, or the link may be incorrect.
          </p>
          <Link href="/dashboard" className="btn btn-primary btn-sm">
            Back to Document Library
          </Link>
        </div>
      </main>
    </div>
  );
}
