import { Suspense } from "react";
import UnsearchedClient from "./UnsearchedClient";

function UnsearchedLoadingFallback() {
  return (
    <div className="table-container" style={{ padding: 48, textAlign: "center" }}>
      <span className="spinner spinner-lg" style={{ margin: "0 auto 12px" }} />
      <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
        Loading unsearched documents…
      </p>
    </div>
  );
}

export default function UnsearchedPage() {
  return (
    <Suspense fallback={<UnsearchedLoadingFallback />}>
      <UnsearchedClient />
    </Suspense>
  );
}
