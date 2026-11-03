/**
 * Admin page models and helpers (slice-35).
 */

export type Role = "user" | "admin";

/** GET /api/auth/me */
export interface Me {
  user_id: number;
  name: string;
  email: string;
  role: Role;
}

/** One row of GET /api/admin/users (sp_admin_user_overview). */
export interface AdminUser {
  user_id: number;
  name: string;
  email: string;
  role: Role;
  created_at: string | null;
  documents: number;
  chunks: number;
  searches: number;
  last_search_at: string | null;
}

/** GET /api/admin/stats (sp_admin_system_stats). */
export interface SystemStats {
  users: number;
  admins: number;
  documents: number;
  documents_processing: number;
  documents_ready: number;
  documents_error: number;
  chunks: number;
  searches: number;
  searches_today: number;
  deletions: number;
}

/** One row of GET /api/admin/deletions (the deletion_audit table). */
export interface DeletionLogItem {
  audit_id: number;
  doc_id: number;
  /** NULL for deletions logged before migration 010. */
  title: string | null;
  user_id: number | null;
  deleted_at: string | null;
}

export const ADMINS_ONLY_MESSAGE = "Admins only";

/** Whether a /api/auth/me response belongs to an admin. */
export function isAdmin(me: unknown): boolean {
  return (
    typeof me === "object" &&
    me !== null &&
    (me as { role?: unknown }).role === "admin"
  );
}

/** The System stats tiles, in display order. */
export const STAT_TILES: ReadonlyArray<{
  key: keyof SystemStats;
  label: string;
}> = [
  { key: "users", label: "Users" },
  { key: "admins", label: "Admins" },
  { key: "documents", label: "Documents" },
  { key: "documents_ready", label: "Ready" },
  { key: "documents_processing", label: "Processing" },
  { key: "documents_error", label: "Failed" },
  { key: "chunks", label: "Passages" },
  { key: "searches", label: "Searches" },
  { key: "searches_today", label: "Searches today (UTC)" },
  { key: "deletions", label: "Deletions logged" },
];

export type AdminData = {
  users: AdminUser[];
  stats: SystemStats;
  deletions: DeletionLogItem[];
};

export type AdminLoadResult =
  | { status: "ok"; data: AdminData }
  | { status: "unauthorized" }
  | { status: "forbidden" }
  | { status: "error"; message: string };

/**
 * Load the three admin endpoints in parallel. Any 401 means the session is
 * gone; any 403 means the user is not an admin (the backend decides).
 */
export async function loadAdminData(
  fetchFn: typeof fetch = fetch,
): Promise<AdminLoadResult> {
  try {
    const responses = await Promise.all([
      fetchFn("/api/admin/users"),
      fetchFn("/api/admin/stats"),
      fetchFn("/api/admin/deletions"),
    ]);
    if (responses.some((res) => res.status === 401)) return { status: "unauthorized" };
    if (responses.some((res) => res.status === 403)) return { status: "forbidden" };
    const failed = responses.find((res) => !res.ok);
    if (failed) {
      const body = await failed.json().catch(() => ({}));
      return {
        status: "error",
        message: body.error || `Failed to load the admin view (${failed.status})`,
      };
    }
    const [users, stats, deletions] = await Promise.all(responses.map((res) => res.json()));
    return {
      status: "ok",
      data: {
        users: Array.isArray(users) ? users : [],
        stats,
        deletions: Array.isArray(deletions) ? deletions : [],
      },
    };
  } catch (err) {
    return {
      status: "error",
      message: err instanceof Error ? err.message : "Failed to load the admin view",
    };
  }
}
