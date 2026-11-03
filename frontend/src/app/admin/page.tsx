import { Suspense } from "react";
import AppHeader from "@/components/AppHeader";
import AdminClient from "./AdminClient";

function AdminLoadingFallback() {
  return (
    <div className="table-container" style={{ padding: 48, textAlign: "center" }}>
      <span className="spinner spinner-lg" style={{ margin: "0 auto 12px" }} />
      <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
        Loading the admin view…
      </p>
    </div>
  );
}

export default function AdminPage() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <AppHeader />
      <main className="main-content">
        <Suspense fallback={<AdminLoadingFallback />}>
          <AdminClient />
        </Suspense>
      </main>
    </div>
  );
}
