import { Suspense } from "react";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";
import DocumentDetailClient, {
  type DocumentDetail,
  type RelatedDocument,
} from "./DocumentDetailClient";

interface PageProps {
  params: Promise<{ id: string }>;
}

async function DocumentDetailContent({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const docId = Number.parseInt(id, 10);

  // Non-numeric / non-positive ids can never belong to a user → 404.
  if (!Number.isInteger(docId) || docId <= 0) {
    notFound();
  }

  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;

  // Page is protected — middleware already redirects unauthenticated users,
  // but guard here too so a missing token never hits the backend unauthenticated.
  if (!token) {
    redirect("/login");
  }

  const base = getApiBaseUrl();
  const authHeaders = { Authorization: `Bearer ${token}` };

  // Metadata is fatal (drives the 404); related is best-effort — the backend
  // already returns [] on any graph failure, so a failed fetch degrades to
  // "No related documents found" rather than erroring the whole page.
  const [detailRes, relatedRes] = await Promise.all([
    fetch(`${base}/api/documents/${docId}`, {
      headers: authHeaders,
      cache: "no-store",
    }),
    fetch(`${base}/api/documents/${docId}/related`, {
      headers: authHeaders,
      cache: "no-store",
    }).catch(() => null),
  ]);

  // A valid session whose token expired server-side → back to login.
  if (detailRes.status === 401) {
    redirect("/login");
  }
  // Doc doesn't exist or doesn't belong to this user → render the 404 page.
  if (detailRes.status === 404) {
    notFound();
  }
  if (!detailRes.ok) {
    throw new Error(`Failed to load document (${detailRes.status})`);
  }

  const detail = (await detailRes.json()) as DocumentDetail;

  let related: RelatedDocument[] = [];
  if (relatedRes && relatedRes.ok) {
    const data = await relatedRes.json().catch(() => []);
    if (Array.isArray(data)) {
      related = data;
    }
  }

  return (
    <>
      <AppHeader />
      <DocumentDetailClient detail={detail} related={related} />
    </>
  );
}

/**
 * Prerendered shell shown while the document loads. Must stay free of runtime
 * hooks (`usePathname`, `cookies`, dynamic `params`) — under Cache Components
 * those can only run inside the Suspense boundary, so the header here is a
 * static skeleton rather than the interactive <AppHeader />.
 */
function DocumentDetailFallback() {
  return (
    <>
      <header className="app-header" aria-hidden="true">
        <div className="app-header-inner">
          <div className="brand">
            <div className="prism-logo-icon" />
            <div className="brand-text-wrap">
              <span className="brand-title">PRISM</span>
              <span className="brand-subtitle">Relational Search</span>
            </div>
          </div>
        </div>
      </header>
      <main className="main-content">
        <div className="table-container" style={{ padding: 48, textAlign: "center" }}>
          <span className="spinner spinner-lg" style={{ margin: "0 auto 12px" }} />
          <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
            Loading document…
          </p>
        </div>
      </main>
    </>
  );
}

/**
 * /documents/:doc_id — Document detail page (slice-20).
 *
 * Shows a document's metadata and topic tags, lists up to 5 related documents
 * from the Neo4j topic graph, and embeds the original PDF via a pre-signed URL.
 *
 * The entire body (interactive header included) sits inside one Suspense
 * boundary: this is a dynamic-segment route, so `params`, `cookies()`, and
 * AppHeader's `usePathname()` all read request-time data that Cache Components
 * only permits within Suspense.
 */
export default function DocumentDetailPage({ params }: PageProps) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Suspense fallback={<DocumentDetailFallback />}>
        <DocumentDetailContent params={params} />
      </Suspense>
    </div>
  );
}
