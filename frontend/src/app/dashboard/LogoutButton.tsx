"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** Clears the auth cookie via the logout route handler, then returns to /login. */
export default function LogoutButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleLogout() {
    setLoading(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <button
      type="button"
      className="btn btn-primary"
      onClick={handleLogout}
      disabled={loading}
    >
      {loading && <span className="spinner" />}
      <span>{loading ? "Logging out…" : "Log out"}</span>
    </button>
  );
}
