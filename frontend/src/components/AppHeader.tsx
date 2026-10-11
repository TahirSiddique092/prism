"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import PrismLogo from "@/components/PrismLogo";
import LogoutButton from "@/app/dashboard/LogoutButton";

export default function AppHeader() {
  const pathname = usePathname();

  const isDashboard = pathname === "/dashboard";
  const isSearch = pathname.startsWith("/search");
  const isAnalytics = pathname.startsWith("/analytics");

  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Link href="/dashboard" className="brand" aria-label="PRISM Dashboard">
          <div className="prism-logo-icon">
            <PrismLogo size={28} />
          </div>
          <div className="brand-text-wrap">
            <span className="brand-title">PRISM</span>
            <span className="brand-subtitle">Relational Search</span>
          </div>
        </Link>

        <nav className="nav-links" aria-label="Main Navigation">
          <Link
            href="/dashboard"
            className={`nav-link ${isDashboard ? "active" : ""}`}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            Dashboard
          </Link>
          <Link
            href="/search"
            className={`nav-link ${isSearch ? "active" : ""}`}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            Search
          </Link>
          <Link
            href="/analytics/history"
            className={`nav-link ${isAnalytics ? "active" : ""}`}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="20" x2="18" y2="10" />
              <line x1="12" y1="20" x2="12" y2="4" />
              <line x1="6" y1="20" x2="6" y2="14" />
            </svg>
            Analytics
          </Link>
        </nav>

        <div className="user-session">
          <LogoutButton className="btn btn-ghost btn-sm" />
        </div>
      </div>
    </header>
  );
}
