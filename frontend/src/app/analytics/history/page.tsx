import { Suspense } from "react";
import HistoryClient from "./HistoryClient";

function HistoryLoadingFallback() {
  return (
    <div className="table-container" style={{ padding: 48, textAlign: "center" }}>
      <span className="spinner spinner-lg" style={{ margin: "0 auto 12px" }} />
      <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
        Loading search history…
      </p>
    </div>
  );
}

export default function HistoryPage() {
  return (
    <Suspense fallback={<HistoryLoadingFallback />}>
      <HistoryClient />
    </Suspense>
  );
}
