import { Suspense } from "react";
import TopDocumentsClient from "./TopDocumentsClient";

function TopDocumentsLoadingFallback() {
  return (
    <div className="table-container" style={{ padding: 48, textAlign: "center" }}>
      <span className="spinner spinner-lg" style={{ margin: "0 auto 12px" }} />
      <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
        Loading top documents…
      </p>
    </div>
  );
}

export default function TopDocumentsPage() {
  return (
    <Suspense fallback={<TopDocumentsLoadingFallback />}>
      <TopDocumentsClient />
    </Suspense>
  );
}
