"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import LocalTime from "@/components/LocalTime";
import {
  ADMINS_ONLY_MESSAGE,
  STAT_TILES,
  loadAdminData,
  type AdminData,
  type AdminLoadResult,
} from "@/lib/admin";

type ViewState =
  | { kind: "loading" }
  | { kind: "forbidden" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: AdminData };

const numberCell = { textAlign: "right", fontFamily: "var(--font-mono, monospace)" } as const;
const mutedText = { color: "var(--color-text-muted)" } as const;
const noWrap = { whiteSpace: "nowrap" } as const;

export default function AdminClient() {
  const router = useRouter();
  const [view, setView] = useState<ViewState>({ kind: "loading" });

  const showResult = useCallback(
    (result: AdminLoadResult) => {
      if (result.status === "unauthorized") router.push("/login");
      else if (result.status === "forbidden") setView({ kind: "forbidden" });
      else if (result.status === "error") setView({ kind: "error", message: result.message });
      else setView({ kind: "ready", data: result.data });
    },
    [router],
  );

  useEffect(() => {
    let isCancelled = false;
    loadAdminData().then((result) => {
      if (!isCancelled) showResult(result);
    });
    return () => {
      isCancelled = true;
    };
  }, [showResult]);

  const retry = () => {
    setView({ kind: "loading" });
    loadAdminData().then(showResult);
  };

  if (view.kind === "forbidden") {
    return (
      <div className="empty-state">
        <h3 className="empty-title">{ADMINS_ONLY_MESSAGE}</h3>
        <p className="empty-desc">This page is only available to administrators.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Admin</h1>
          <p className="page-subtitle">Accounts, system totals and the deletion log (read-only)</p>
        </div>
      </div>

      {view.kind === "loading" && (
        <div className="table-container" style={{ padding: 48, textAlign: "center" }}>
          <span className="spinner spinner-lg" style={{ margin: "0 auto 12px" }} />
          <p style={{ ...mutedText, fontSize: "0.875rem" }}>Loading the admin view…</p>
        </div>
      )}

      {view.kind === "error" && (
        <div className="alert-error" role="alert">
          <span style={{ flex: 1 }}>{view.message}</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={retry}>
            Retry
          </button>
        </div>
      )}

      {view.kind === "ready" && (
        <>
          <section className="admin-section" aria-labelledby="admin-stats">
            <h2 id="admin-stats" className="admin-section-title">System stats</h2>
            <div className="stat-grid">
              {STAT_TILES.map(({ key, label }) => (
                <div key={key} className="stat-tile">
                  <span className="detail-meta-label">{label}</span>
                  <span className="stat-value">{view.data.stats[key] ?? 0}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-section" aria-labelledby="admin-users">
            <h2 id="admin-users" className="admin-section-title">Users</h2>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Joined</th>
                    <th style={{ textAlign: "right" }}>Documents</th>
                    <th style={{ textAlign: "right" }}>Passages</th>
                    <th style={{ textAlign: "right" }}>Searches</th>
                    <th>Last search</th>
                  </tr>
                </thead>
                <tbody>
                  {view.data.users.map((user) => (
                    <tr key={user.user_id}>
                      <td style={{ fontWeight: 500, color: "var(--color-text-primary)" }}>{user.name}</td>
                      <td>{user.email}</td>
                      <td>
                        <span className={user.role === "admin" ? "count-pill" : "rank-badge"}>
                          {user.role}
                        </span>
                      </td>
                      <td style={noWrap}><LocalTime iso={user.created_at} /></td>
                      <td style={numberCell}>{user.documents}</td>
                      <td style={numberCell}>{user.chunks}</td>
                      <td style={numberCell}>{user.searches}</td>
                      <td style={noWrap}><LocalTime iso={user.last_search_at} withTime empty="Never" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="admin-section" aria-labelledby="admin-deletions">
            <h2 id="admin-deletions" className="admin-section-title">Deletion log</h2>
            <p className="page-subtitle" style={{ marginBottom: 12 }}>
              Written by the <code>before_document_delete</code> trigger. Latest 50.
            </p>
            {view.data.deletions.length === 0 ? (
              <p style={mutedText}>No documents have been deleted yet.</p>
            ) : (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: "90px" }}>Audit ID</th>
                      <th style={{ width: "90px" }}>Doc ID</th>
                      <th>Title</th>
                      <th style={{ width: "110px" }}>Owner (user ID)</th>
                      <th>Deleted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.data.deletions.map((row) => (
                      <tr key={row.audit_id}>
                        <td style={{ fontFamily: "var(--font-mono, monospace)" }}>{row.audit_id}</td>
                        <td style={{ fontFamily: "var(--font-mono, monospace)" }}>{row.doc_id}</td>
                        <td>{row.title ?? <span style={mutedText}>not recorded</span>}</td>
                        <td style={{ fontFamily: "var(--font-mono, monospace)" }}>
                          {row.user_id ?? <span style={mutedText}>—</span>}
                        </td>
                        <td style={noWrap}><LocalTime iso={row.deleted_at} withTime /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
