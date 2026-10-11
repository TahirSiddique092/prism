import { Suspense } from "react";
import AppHeader from "@/components/AppHeader";
import SearchClient from "./SearchClient";

function SearchLoadingFallback() {
  return (
    <main className="main-content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Semantic Search</h1>
          <p className="page-subtitle">Loading search…</p>
        </div>
      </div>
    </main>
  );
}

/**
 * /search — the core page of the app (slice-18).
 *
 * A search bar at the top; results listed below with document title, matched
 * snippet, similarity score, a semantic/FULLTEXT indicator, and a cache badge.
 *
 * The active query lives in the URL (`?q=`), so navigating away and back — or
 * reloading — restores the previous query and its results (criterion 7). The
 * client component reads that param via `useSearchParams`, which is why this
 * page wraps it in a Suspense boundary.
 */
export default function SearchPage() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <AppHeader />
      <Suspense fallback={<SearchLoadingFallback />}>
        <SearchClient />
      </Suspense>
    </div>
  );
}
