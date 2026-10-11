import AppHeader from "@/components/AppHeader";
import AnalyticsNav from "@/components/AnalyticsNav";

export default function AnalyticsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <AppHeader />
      <main className="main-content">
        <AnalyticsNav />
        {children}
      </main>
    </div>
  );
}
