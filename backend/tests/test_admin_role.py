"""Slice 35: the admin role and the admin API.

1. Migration 010: users.role with its CHECK, deletion_audit owner and title,
   the new trigger body, and the admin functions and procedures
2. Registration still creates a 'user'; set_role.py promotes and demotes by email
3. require_admin: 401 without a session, 403 for a user, and the role is read
   from MySQL on every request
4. GET /api/auth/me
5. The admin routes return what the procedures and the deletion log give,
   never a password hash, search text or document text, and log [DB] lines

The integration test at the bottom is opt-in (PRISM_MYSQL_INTEGRATION=1 plus
MYSQL_URL). It only reads, apart from one UPDATE the CHECK constraint must
reject, run inside a transaction that is rolled back.
"""
import datetime
import logging
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app import create_app
from backend.db import set_role as set_role_cli
from backend.db.migrate import split_mysql_script
from backend.modules.admin.db import (
    DELETION_LOG_LIMIT,
    DELETION_LOG_QUERY,
    get_deletion_log,
    get_system_stats,
    get_user_overview,
)
from backend.modules.auth.db import create_user, find_user_by_id, get_user_role
from backend.modules.auth.service import generate_token

MIGRATION_010 = Path(__file__).parent.parent / "db" / "migrations" / "010_user_roles.sql"

SENSITIVE_KEYS = {"password_hash", "query_text", "chunk_text", "snippet"}

STATS_ROW = {
    "users": 3, "admins": 1, "documents": 5, "documents_processing": 1,
    "documents_ready": 3, "documents_error": 1, "chunks": 120, "searches": 42,
    "searches_today": 4, "deletions": 2,
}


@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture
def auth_header():
    return {"Authorization": f"Bearer {generate_token(user_id=7, email='seven@example.com')}"}


@pytest.fixture
def db_lines(caplog):
    caplog.set_level(logging.INFO, logger="prism.db")
    return lambda: [r.getMessage() for r in caplog.records if r.getMessage().startswith("[DB]")]


def _proc_conn(columns, rows):
    conn = MagicMock()
    result = MagicMock()
    result.column_names = columns
    result.fetchall.return_value = rows
    conn.cursor.return_value.stored_results.return_value = [result]
    return conn


def _statements():
    script = MIGRATION_010.read_text().split("-- ENGINE: ")[1][len("MySQL"):].strip()
    return split_mysql_script(script)


# ============================================================================
# 1. Migration 010
# ============================================================================

def test_migration_010_adds_the_role_column_with_its_check():
    role_stmt, _ = _statements()[0]
    assert "ALTER TABLE users" in role_stmt
    assert "ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'" in role_stmt
    assert "CHECK (role IN ('user', 'admin'))" in role_stmt


def test_migration_010_records_owner_and_title_in_the_deletion_log():
    stmts = _statements()
    audit_stmt, in_block = stmts[1]
    assert not in_block
    assert "ALTER TABLE deletion_audit" in audit_stmt
    assert "ADD COLUMN user_id INT NULL" in audit_stmt
    assert "ADD COLUMN title VARCHAR(255) NULL" in audit_stmt

    assert stmts[2][0] == "DROP TRIGGER IF EXISTS before_document_delete"
    trigger = stmts[3][0]
    assert "BEFORE DELETE ON documents" in trigger
    assert "INSERT INTO deletion_audit (doc_id, user_id, title, deleted_at)" in trigger
    assert "VALUES (OLD.doc_id, OLD.user_id, OLD.title, NOW())" in trigger


def test_migration_010_creates_the_admin_functions_and_procedures():
    stmts = _statements()
    assert len(stmts) == 12
    assert [b for _, b in stmts] == [False, False] + [True] * 10
    for name in ("fn_user_document_count", "fn_user_search_count"):
        sql = next(s for s, _ in stmts if f"CREATE FUNCTION {name}(p_user_id INT)" in s)
        assert "RETURNS INT" in sql and "READS SQL DATA" in sql
    for name in ("sp_admin_user_overview", "sp_admin_system_stats"):
        sql = next(s for s, _ in stmts if f"CREATE PROCEDURE {name}()" in s)
        assert "READS SQL DATA" in sql

    overview = next(s for s, _ in stmts if "CREATE PROCEDURE sp_admin_user_overview" in s)
    for fn in ("fn_user_document_count(u.user_id)", "fn_user_search_count(u.user_id)", "fn_chunk_count(d.doc_id)"):
        assert fn in overview
    # Each routine is dropped first, so the migration can be re-applied.
    drops = [s for s, _ in stmts if s.startswith("DROP ")]
    assert len(drops) == 5


def test_admin_procedures_never_select_secrets_or_text():
    for sql, _ in _statements():
        assert '"' not in sql  # ANSI_QUOTES: strings need single quotes
        if "CREATE PROCEDURE" in sql:
            for column in ("password_hash", "query_text", "chunk_text"):
                assert column not in sql


# ============================================================================
# 2. New accounts and set_role.py
# ============================================================================

def test_registration_never_sets_a_role():
    conn = MagicMock()
    create_user("A", "a@example.com", "hash", conn=conn)
    sql = conn.cursor.return_value.execute.call_args.args[0]
    assert sql == "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)"


def _cli_conn(found_row):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = found_row
    return conn


def test_set_role_promotes_by_email_with_prepared_statements(capsys):
    conn = _cli_conn((4, "user"))

    assert set_role_cli.set_role(conn, "  Admin@Example.COM ", "admin") == 0

    conn.cursor.assert_called_once_with(prepared=True)
    cursor = conn.cursor.return_value
    assert [c.args for c in cursor.execute.call_args_list] == [
        ("SELECT user_id, role FROM users WHERE email = %s", ("admin@example.com",)),
        ("UPDATE users SET role = %s WHERE user_id = %s", ("admin", 4)),
    ]
    conn.commit.assert_called_once()
    assert "user → admin" in capsys.readouterr().out


def test_set_role_demotes():
    conn = _cli_conn((4, "admin"))
    assert set_role_cli.set_role(conn, "admin@example.com", "user") == 0
    assert conn.cursor.return_value.execute.call_args.args == (
        "UPDATE users SET role = %s WHERE user_id = %s", ("user", 4))


def test_set_role_leaves_an_unchanged_role_alone(capsys):
    conn = _cli_conn((4, "admin"))
    assert set_role_cli.set_role(conn, "admin@example.com", "admin") == 0
    assert conn.cursor.return_value.execute.call_count == 1
    conn.commit.assert_not_called()
    assert "already admin" in capsys.readouterr().out


def test_set_role_unknown_email_prints_an_error_and_exits_1(capsys):
    conn = _cli_conn(None)
    with patch("backend.db.migrate.get_mysql_conn", return_value=conn), \
         patch("dotenv.load_dotenv"):
        assert set_role_cli.main(["--email", "nobody@example.com", "--role", "admin"]) == 1
    assert "No account with the email nobody@example.com" in capsys.readouterr().out
    assert conn.cursor.return_value.execute.call_count == 1
    conn.close.assert_called_once()


def test_set_role_accepts_only_the_two_roles():
    with pytest.raises(SystemExit) as exc:
        set_role_cli.main(["--email", "a@example.com", "--role", "owner"])
    assert exc.value.code == 2


# ============================================================================
# 3. require_admin
# ============================================================================

ADMIN_ROUTES = ["/api/admin/users", "/api/admin/stats", "/api/admin/deletions"]


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_admin_routes_need_a_session(client, path):
    with patch("backend.modules.auth.middleware.get_user_role") as role:
        assert client.get(path).status_code == 401
    role.assert_not_called()


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_admin_routes_refuse_a_user(client, auth_header, path):
    with patch("backend.modules.auth.middleware.get_user_role", return_value="user") as role, \
         patch("backend.modules.admin.routes.get_user_overview") as overview, \
         patch("backend.modules.admin.routes.get_system_stats") as stats, \
         patch("backend.modules.admin.routes.get_deletion_log") as deletions:
        res = client.get(path, headers=auth_header)
    assert res.status_code == 403
    assert res.get_json() == {"error": "Admins only"}
    role.assert_called_once_with(7)
    overview.assert_not_called()
    stats.assert_not_called()
    deletions.assert_not_called()


def test_an_account_that_no_longer_exists_is_refused(client, auth_header):
    with patch("backend.modules.auth.middleware.get_user_role", return_value=None):
        assert client.get("/api/admin/stats", headers=auth_header).status_code == 403


def test_demotion_takes_effect_on_the_next_request(client, auth_header):
    """Same token, role read again each time: admin, then user after set_role.py."""
    with patch("backend.modules.auth.middleware.get_user_role", side_effect=["admin", "user"]) as role, \
         patch("backend.modules.admin.routes.get_system_stats", return_value=STATS_ROW):
        assert client.get("/api/admin/stats", headers=auth_header).status_code == 200
        assert client.get("/api/admin/stats", headers=auth_header).status_code == 403
    assert role.call_count == 2


def test_get_user_role_reads_the_users_table():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = ("admin",)
    assert get_user_role(7, conn=conn) == "admin"
    conn.cursor.return_value.execute.assert_called_once_with(
        "SELECT role FROM users WHERE user_id = %s", (7,))

    conn.cursor.return_value.fetchone.return_value = None
    assert get_user_role(99, conn=conn) is None


# ============================================================================
# 4. GET /api/auth/me
# ============================================================================

def test_me_needs_a_session(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_the_profile_with_the_role(client, auth_header):
    profile = {"user_id": 7, "name": "Seven", "email": "seven@example.com", "role": "admin"}
    with patch("backend.modules.auth.routes.find_user_by_id", return_value=profile) as find:
        res = client.get("/api/auth/me", headers=auth_header)
    assert res.status_code == 200
    assert res.get_json() == profile
    find.assert_called_once_with(7)


def test_me_for_a_deleted_account_is_401(client, auth_header):
    with patch("backend.modules.auth.routes.find_user_by_id", return_value=None):
        assert client.get("/api/auth/me", headers=auth_header).status_code == 401


def test_find_user_by_id_never_selects_the_password_hash():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (7, "Seven", "seven@example.com", "user")
    assert find_user_by_id(7, conn=conn) == {
        "user_id": 7, "name": "Seven", "email": "seven@example.com", "role": "user"}
    sql = conn.cursor.return_value.execute.call_args.args[0]
    assert sql == "SELECT user_id, name, email, role FROM users WHERE user_id = %s"


# ============================================================================
# 5. The admin API
# ============================================================================

OVERVIEW_COLUMNS = ("user_id", "name", "email", "role", "created_at",
                    "documents", "chunks", "searches", "last_search_at")


def test_user_overview_maps_the_procedure_rows_and_logs(db_lines):
    conn = _proc_conn(OVERVIEW_COLUMNS, [
        (1, "Ann", "ann@example.com", "admin", datetime.datetime(2026, 10, 1, 9, 0, 0),
         2, 43, 7, datetime.datetime(2026, 11, 3, 10, 30, 0)),
        (2, "Bo", "bo@example.com", "user", datetime.datetime(2026, 10, 2, 9, 0, 0),
         0, 0, 0, None),
    ])

    users = get_user_overview(conn=conn)

    conn.cursor.return_value.callproc.assert_called_once_with("sp_admin_user_overview", ())
    assert users == [
        {"user_id": 1, "name": "Ann", "email": "ann@example.com", "role": "admin",
         "created_at": "2026-10-01T09:00:00Z", "documents": 2, "chunks": 43, "searches": 7,
         "last_search_at": "2026-11-03T10:30:00Z"},
        {"user_id": 2, "name": "Bo", "email": "bo@example.com", "role": "user",
         "created_at": "2026-10-02T09:00:00Z", "documents": 0, "chunks": 0, "searches": 0,
         "last_search_at": None},
    ]
    procedure, function = db_lines()
    assert re.fullmatch(r"\[DB\] PROCEDURE sp_admin_user_overview\(\) → 2 rows in \d+ ms", procedure)
    assert function == ("[DB] FUNCTION  fn_user_document_count, fn_user_search_count and "
                        "fn_chunk_count inside sp_admin_user_overview: 2 users")
    assert not any("@" in line for line in db_lines())  # no email addresses in the log


def test_system_stats_returns_the_procedure_totals_and_logs(db_lines):
    conn = _proc_conn(tuple(STATS_ROW), [tuple(STATS_ROW.values())])

    assert get_system_stats(conn=conn) == STATS_ROW

    conn.cursor.return_value.callproc.assert_called_once_with("sp_admin_system_stats", ())
    (line,) = db_lines()
    assert re.fullmatch(r"\[DB\] PROCEDURE sp_admin_system_stats\(\) → 1 rows? in \d+ ms", line)


def test_deletion_log_reads_the_latest_audit_rows_and_logs(db_lines):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.return_value = [
        (9, 12, "old.pdf", 1, datetime.datetime(2026, 11, 3, 10, 0, 0)),
        (3, 4, None, None, datetime.datetime(2026, 10, 20, 8, 0, 0)),  # before migration 010
    ]

    rows = get_deletion_log(conn=conn)

    cursor.execute.assert_called_once_with(DELETION_LOG_QUERY, (50,))
    assert DELETION_LOG_LIMIT == 50
    assert "FROM deletion_audit" in DELETION_LOG_QUERY
    assert "ORDER BY deleted_at DESC" in DELETION_LOG_QUERY
    assert rows == [
        {"audit_id": 9, "doc_id": 12, "title": "old.pdf", "user_id": 1,
         "deleted_at": "2026-11-03T10:00:00Z"},
        {"audit_id": 3, "doc_id": 4, "title": None, "user_id": None,
         "deleted_at": "2026-10-20T08:00:00Z"},
    ]
    (line,) = db_lines()
    assert re.fullmatch(
        r"\[DB\] TRIGGER   deletion_audit read \(rows written by before_document_delete\) → 2 rows in \d+ ms", line)


def test_admin_routes_return_the_data_without_sensitive_fields(client, auth_header):
    users = [{"user_id": 1, "name": "Ann", "email": "ann@example.com", "role": "admin",
              "created_at": "2026-10-01T09:00:00Z", "documents": 2, "chunks": 43,
              "searches": 7, "last_search_at": None}]
    deletions = [{"audit_id": 9, "doc_id": 12, "title": "old.pdf", "user_id": 1,
                  "deleted_at": "2026-11-03T10:00:00Z"}]
    with patch("backend.modules.auth.middleware.get_user_role", return_value="admin"), \
         patch("backend.modules.admin.routes.get_user_overview", return_value=users), \
         patch("backend.modules.admin.routes.get_system_stats", return_value=STATS_ROW), \
         patch("backend.modules.admin.routes.get_deletion_log", return_value=deletions):
        got_users = client.get("/api/admin/users", headers=auth_header)
        got_stats = client.get("/api/admin/stats", headers=auth_header)
        got_deletions = client.get("/api/admin/deletions", headers=auth_header)

    assert [r.status_code for r in (got_users, got_stats, got_deletions)] == [200, 200, 200]
    assert got_users.get_json() == users
    assert got_stats.get_json() == STATS_ROW
    assert got_deletions.get_json() == deletions
    for row in got_users.get_json() + got_deletions.get_json() + [got_stats.get_json()]:
        assert not SENSITIVE_KEYS & set(row)


def test_admin_route_errors_do_not_leak_details(client, auth_header):
    with patch("backend.modules.auth.middleware.get_user_role", return_value="admin"), \
         patch("backend.modules.admin.routes.get_user_overview", side_effect=RuntimeError("secret detail")):
        res = client.get("/api/admin/users", headers=auth_header)
    assert res.status_code == 500
    assert "secret detail" not in res.get_data(as_text=True)


# ============================================================================
# Integration (opt-in): real MySQL
# ============================================================================

integration = pytest.mark.skipif(
    os.getenv("PRISM_MYSQL_INTEGRATION") != "1" or not os.getenv("MYSQL_URL"),
    reason="set PRISM_MYSQL_INTEGRATION=1 and MYSQL_URL to run against a real MySQL server",
)


@integration
def test_integration_roles_routines_and_counts():
    import mysql.connector

    from backend.modules.auth.db import get_db_config

    conn = mysql.connector.connect(**get_db_config())
    try:
        cur = conn.cursor()
        cur.execute("SELECT COLUMN_DEFAULT, IS_NULLABLE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'role'")
        default, nullable = cur.fetchone()
        assert default.strip("'") == "user" and nullable == "NO"

        cur.execute("SELECT COUNT(*) FROM users WHERE role NOT IN ('user', 'admin')")
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'deletion_audit'")
        assert {"user_id", "title"} <= {r[0] for r in cur.fetchall()}

        cur.execute("SELECT ROUTINE_NAME FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = DATABASE()")
        assert {"fn_user_document_count", "fn_user_search_count",
                "sp_admin_user_overview", "sp_admin_system_stats"} <= {r[0] for r in cur.fetchall()}

        # Totals equal direct COUNT queries
        stats = get_system_stats(conn=conn)
        direct = {
            "users": "SELECT COUNT(*) FROM users",
            "admins": "SELECT COUNT(*) FROM users WHERE role = 'admin'",
            "documents": "SELECT COUNT(*) FROM documents",
            "documents_ready": "SELECT COUNT(*) FROM documents WHERE status = 'ready'",
            "chunks": "SELECT COUNT(*) FROM chunks",
            "searches": "SELECT COUNT(*) FROM search_log",
            "deletions": "SELECT COUNT(*) FROM deletion_audit",
        }
        for key, sql in direct.items():
            cur.execute(sql)
            assert stats[key] == cur.fetchone()[0], key

        # Per-user counts equal direct COUNT queries
        for user in get_user_overview(conn=conn):
            uid = user["user_id"]
            cur.execute("SELECT COUNT(*) FROM documents WHERE user_id = %s", (uid,))
            assert user["documents"] == cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM chunks c JOIN documents d ON d.doc_id = c.doc_id "
                        "WHERE d.user_id = %s", (uid,))
            assert user["chunks"] == cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM search_log WHERE user_id = %s", (uid,))
            assert user["searches"] == cur.fetchone()[0]
            assert not SENSITIVE_KEYS & set(user)

        # The CHECK constraint rejects any other role (rolled back either way)
        cur.execute("SELECT MIN(user_id) FROM users")
        uid = cur.fetchone()[0]
        if uid is not None:
            conn.start_transaction()
            try:
                with pytest.raises(mysql.connector.Error) as exc:
                    cur.execute("UPDATE users SET role = 'owner' WHERE user_id = %s", (uid,))
                assert exc.value.errno == 3819  # ER_CHECK_CONSTRAINT_VIOLATED
            finally:
                conn.rollback()
        cur.close()
    finally:
        conn.close()
