"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ANALYTICS_NAV_ITEMS } from "@/lib/analytics";

export default function AnalyticsNav() {
  const pathname = usePathname();

  return (
    <nav className="analytics-nav" aria-label="Analytics Navigation">
      {ANALYTICS_NAV_ITEMS.map((item) => {
        const isActive =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`analytics-tab ${isActive ? "active" : ""}`}
            aria-current={isActive ? "page" : undefined}
          >
            {item.id === "history" && (
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            )}
            {item.id === "unsearched" && (
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <line x1="9" y1="15" x2="15" y2="15" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            )}
            {item.id === "top-documents" && (
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
                <polyline points="16 7 22 7 22 13" />
              </svg>
            )}
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
