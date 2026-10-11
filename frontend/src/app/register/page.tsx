"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import PrismLogo from "@/components/PrismLogo";

const GENERIC_REGISTER_ERROR = "Could not create your account. Please try again.";

export default function RegisterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);

    const form = new FormData(event.currentTarget);
    const payload = {
      name: form.get("name"),
      email: form.get("email"),
      password: form.get("password"),
    };

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        // Registration logs the user straight in; cookie is already set.
        router.replace("/dashboard");
        router.refresh();
        return;
      }

      // Surface the backend message (e.g. "Email already exists") when present.
      const data = await res.json().catch(() => ({}));
      setError(
        typeof data?.error === "string" ? data.error : GENERIC_REGISTER_ERROR,
      );
    } catch {
      setError(GENERIC_REGISTER_ERROR);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <PrismLogo />
          <h1 className="auth-title">Create your account</h1>
          <p className="auth-subtitle">
            Get started with AI-driven vector search for your PDFs
          </p>
        </div>

        {error && (
          <div className="alert-error" role="alert">
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="name">
              Full name <span className="required">*</span>
            </label>
            <input
              id="name"
              name="name"
              type="text"
              className="form-input"
              placeholder="Alex Rivera"
              autoComplete="name"
              required
              disabled={loading}
            />
          </div>

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
              placeholder="Create a password"
              autoComplete="new-password"
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
            <span>{loading ? "Creating account…" : "Sign up"}</span>
          </button>
        </form>

        <div className="auth-footer-links">
          Already have an account? <Link href="/login">Log in</Link>
        </div>
      </div>
    </div>
  );
}
