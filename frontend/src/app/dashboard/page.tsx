import PrismLogo from "@/components/PrismLogo";

import LogoutButton from "./LogoutButton";

/**
 * Placeholder dashboard — the redirect target for successful auth (slice-16).
 *
 * This route is protected by middleware (unauthenticated visitors are sent to
 * /login). The full document-management dashboard is built in slice-17; this
 * stub exists so the auth flow has a real, protected landing page to verify
 * against.
 */
export default function DashboardPage() {
  return (
    <main
      style={{
        maxWidth: 1200,
        margin: "0 auto",
        padding: "48px 24px",
        display: "flex",
        flexDirection: "column",
        gap: 24,
        alignItems: "flex-start",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <PrismLogo size={32} />
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700 }}>Dashboard</h1>
      </div>
      <p style={{ color: "var(--color-text-muted)" }}>
        You are signed in. Document management arrives in slice-17.
      </p>
      <LogoutButton />
    </main>
  );
}
