"""Database operations for the auth module using raw SQL with mysql-connector-python.

As per project guidelines (AGENTS.md):
- No ORMs (no SQLAlchemy, no abstractions)
- Explicit, visible SQL queries
- Manages connection and parameterized execution to prevent SQL injection
"""
import os
import urllib.parse
import mysql.connector
from mysql.connector import errors


def get_db_config():
    """Extract MySQL connection parameters from environment variables."""
    mysql_url = os.getenv("MYSQL_URL")
    if mysql_url:
        parsed = urllib.parse.urlparse(mysql_url)
        return {
            "user": urllib.parse.unquote(parsed.username) if parsed.username else "root",
            "password": urllib.parse.unquote(parsed.password) if parsed.password else "",
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "database": parsed.path.lstrip("/") if parsed.path else "prism",
            "autocommit": True,
        }

    return {
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "database": os.getenv("MYSQL_DATABASE", "prism"),
        "autocommit": True,
    }


def get_db_connection():
    """Establish and return a new connection to the MySQL database."""
    config = get_db_config()
    return mysql.connector.connect(**config)


def find_user_by_email(email: str, conn=None):
    """Fetch user record by email using raw SQL.
    
    Returns a dictionary of user columns or None if not found.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor(dictionary=True)
        # Explicit raw SQL query as required by PRISM DBMS guidelines
        query = "SELECT user_id, name, email, password_hash, created_at FROM users WHERE email = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        cursor.close()
        return user
    finally:
        if should_close and conn:
            conn.close()


def create_user(name: str, email: str, password_hash: str, conn=None) -> int:
    """Insert a new user record into MySQL using raw SQL.
    
    Returns the newly generated user_id.
    Raises mysql.connector.errors.IntegrityError if the email already exists.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        # Explicit raw SQL insert as required by PRISM DBMS guidelines
        query = "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)"
        cursor.execute(query, (name, email, password_hash))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        return user_id
    finally:
        if should_close and conn:
            conn.close()
