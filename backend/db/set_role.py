"""Set a user's role to admin or user (slice-35).

Registration always creates a 'user'; this script is the only way to make
someone an admin. The change takes effect on their next request, because the
admin check reads the role from MySQL every time.

    python backend/db/set_role.py --email someone@example.com --role admin
    python backend/db/set_role.py --email someone@example.com --role user
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Allow running as `python backend/db/set_role.py` from the repo root (the
# Docker image already sets PYTHONPATH=/app).
sys.path.insert(0, str(REPO_ROOT))

ROLES = ("user", "admin")

FIND_USER_QUERY = "SELECT user_id, role FROM users WHERE email = %s"
SET_ROLE_QUERY = "UPDATE users SET role = %s WHERE user_id = %s"


def set_role(mysql_conn, email: str, role: str) -> int:
    """Set the role of the account with this email. Returns the exit code."""
    email = email.strip().lower()
    # Prepared statements: the email is sent apart from the SQL (ADR-017).
    cursor = mysql_conn.cursor(prepared=True)
    try:
        cursor.execute(FIND_USER_QUERY, (email,))
        row = cursor.fetchone()
        if row is None:
            print(f"No account with the email {email}.")
            return 1

        user_id, current_role = row[0], row[1]
        if isinstance(current_role, (bytes, bytearray)):
            current_role = current_role.decode()
        if current_role == role:
            print(f"{email} (user_id={user_id}) is already {role}.")
            return 0

        cursor.execute(SET_ROLE_QUERY, (role, user_id))
        mysql_conn.commit()
        print(f"{email} (user_id={user_id}): {current_role} → {role}.")
        return 0
    finally:
        cursor.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Set a PRISM user's role.")
    parser.add_argument("--email", required=True, help="the account's email address")
    parser.add_argument("--role", required=True, choices=ROLES, help="the new role")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    from backend.db.migrate import get_mysql_conn

    try:
        mysql_conn = get_mysql_conn()
    except Exception as e:
        print(f"Cannot connect to MySQL: {e}")
        return 1
    if mysql_conn is None:
        print("MYSQL_URL is not set.")
        return 1

    try:
        return set_role(mysql_conn, args.email, args.role)
    finally:
        mysql_conn.close()


if __name__ == "__main__":
    sys.exit(main())
