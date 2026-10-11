"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import PrismLogo from "@/components/PrismLogo";

/** Shown to the user on any failed login — never reveals which field was wrong. */
const GENERIC_LOGIN_ERROR = "Invalid email or password. Please try again.";

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);

    const form = new FormData(event.currentTarget);
    const payload = {
      email: form.get("email"),
      password: form.get("password"),
    };

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        // Cookie is set by the route handler; refresh so middleware sees it.
        router.replace("/dashboard");
        router.refresh();
        return;
      }

      setError(GENERIC_LOGIN_ERROR);
    } catch {
      setError(GENERIC_LOGIN_ERROR);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <PrismLogo />
          <h1 className="auth-title">Welcome back</h1>
          <p className="auth-subtitle">
            Sign in to search your relational study library
          </p>
        </div>

        {error && (
          <div className="alert-error" role="alert">
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="email">
              Email address <span className="required">*</span>
            </label>
            <input
              id="email"
              name="email"
              type="email"
              className="form-input"
              placeholder="student@university.edu"
              autoComplete="email"
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">
              Password <span className="required">*</span>
            </label>
            <input
              id="password"
              name="password"
              type="password"
              className="form-input"
              placeholder="••••••••••••"
              autoComplete="current-password"
              required
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", marginTop: 8 }}
            disabled={loading}
          >
            {loading && <span className="spinner" />}
            <span>{loading ? "Signing in…" : "Log in"}</span>
          </button>
        </form>

        <div className="auth-footer-links">
          Don&apos;t have an account? <Link href="/register">Create an account</Link>
        </div>
      </div>
    </div>
  );
}
