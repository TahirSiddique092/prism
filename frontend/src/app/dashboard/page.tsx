import { Suspense } from "react";
import { cookies } from "next/headers";
import AppHeader from "@/components/AppHeader";
import DashboardClient, { type DocumentItem } from "./DashboardClient";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

async function DashboardContent() {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;

  let initialDocuments: DocumentItem[] = [];

  if (token) {
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/documents`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      });

      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          initialDocuments = data;
        }
      }
    } catch {
      // Backend unavailable during SSR; client can retry or refresh
      initialDocuments = [];
    }
  }

  return <DashboardClient initialDocuments={initialDocuments} />;
}

function DashboardLoadingFallback() {
  return (
    <main className="main-content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Document Library</h1>
          <p className="page-subtitle">Loading your document collection…</p>
        </div>
      </div>
      <div className="table-container" style={{ padding: 40, textAlign: "center" }}>
        <span className="spinner" style={{ margin: "0 auto 12px" }} />
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
          Retrieving documents…
        </p>
      </div>
    </main>
  );
}

/**
 * /dashboard — The user's home page (slice-17).
 *
 * Shows the user's uploaded documents and a form to upload a new PDF with topic tags.
 * Wrapped in Suspense to support Next 16 Cache Components and Partial Prerendering.
 */
export default function DashboardPage() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <AppHeader />
      <Suspense fallback={<DashboardLoadingFallback />}>
        <DashboardContent />
      </Suspense>
    </div>
  );
}
