import os
import urllib.parse
from pathlib import Path
import mysql.connector
import psycopg2
from dotenv import load_dotenv

# Load env config
load_dotenv(Path(__file__).parent.parent.parent / ".env")

def get_mysql_conn():
    url = os.getenv("MYSQL_URL")
    if url:
        parsed = urllib.parse.urlparse(url)
        return mysql.connector.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=urllib.parse.unquote(parsed.username) if parsed.username else "root",
            password=urllib.parse.unquote(parsed.password) if parsed.password else "",
            database=parsed.path.lstrip("/") if parsed.path else "prism",
            autocommit=True
        )
    return None

def get_postgres_conn():
    url = os.getenv("POSTGRES_URL")
    if url:
        # psycopg2 can parse the URL directly
        conn = psycopg2.connect(url)
        conn.autocommit = True
        return conn
    return None

def ensure_schema_migrations_mysql(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_name VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.close()

def get_applied_migrations_mysql(conn):
    try:
        ensure_schema_migrations_mysql(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT migration_name FROM schema_migrations")
        applied = {row[0] for row in cursor.fetchall()}
        cursor.close()
        return applied
    except Exception as e:
        print(f"Warning: could not read schema_migrations in MySQL: {e}")
        return set()

def record_migration_mysql(conn, migration_name):
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT IGNORE INTO schema_migrations (migration_name) VALUES (%s)",
            (migration_name,)
        )
        cursor.close()
    except Exception as e:
        print(f"Warning: could not record {migration_name} in MySQL schema_migrations: {e}")

def ensure_schema_migrations_pg(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_name VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def get_applied_migrations_pg(conn):
    try:
        ensure_schema_migrations_pg(conn)
        with conn.cursor() as cursor:
            cursor.execute("SELECT migration_name FROM schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}
        return applied
    except Exception as e:
        print(f"Warning: could not read schema_migrations in Postgres: {e}")
        return set()

def record_migration_pg(conn, migration_name):
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO schema_migrations (migration_name) VALUES (%s) ON CONFLICT DO NOTHING",
                (migration_name,)
            )
    except Exception as e:
        print(f"Warning: could not record {migration_name} in Postgres schema_migrations: {e}")

def run_migrations():
    migrations_dir = Path(__file__).parent / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    mysql_conn = get_mysql_conn()
    pg_conn = get_postgres_conn()

    applied_mysql = get_applied_migrations_mysql(mysql_conn) if mysql_conn else set()
    applied_pg = get_applied_migrations_pg(pg_conn) if pg_conn else set()

    for migration_file in migration_files:
        name = migration_file.name
        with open(migration_file, "r") as f:
            content = f.read()

        parts = content.split("-- ENGINE: ")
        mysql_script = ""
        postgres_script = ""
        
        for part in parts:
            if part.startswith("MySQL"):
                mysql_script = part[len("MySQL"):].strip()
            elif part.startswith("Postgres"):
                postgres_script = part[len("Postgres"):].strip()

        if mysql_script and mysql_conn:
            if name in applied_mysql:
                print(f"Skipping MySQL migration (already applied): {name}")
            else:
                print(f"Running MySQL migration: {name}")
                cursor = mysql_conn.cursor()
                statements = mysql_script.split("DELIMITER //")
                for stmt in statements[0].split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        try:
                            cursor.execute(stmt)
                        except mysql.connector.Error as err:
                            # 1050: Table already exists, 1060: Duplicate column, 1061: Duplicate key name
                            if err.errno in (1050, 1060, 1061):
                                print(f"Notice: {err.msg} (continuing)")
                            else:
                                raise
                if len(statements) > 1:
                    trigger_block = statements[1].split("DELIMITER ;")[0].strip()
                    if trigger_block.endswith("//"):
                        trigger_block = trigger_block[:-2].strip()
                    if trigger_block:
                        try:
                            cursor.execute(trigger_block)
                        except mysql.connector.Error as err:
                            # 1304: Trigger already exists
                            if err.errno in (1304,):
                                print(f"Notice: {err.msg} (continuing)")
                            else:
                                raise
                cursor.close()
                record_migration_mysql(mysql_conn, name)

        if postgres_script and pg_conn:
            if name in applied_pg:
                print(f"Skipping Postgres migration (already applied): {name}")
            else:
                print(f"Running Postgres migration: {name}")
                with pg_conn.cursor() as cursor:
                    try:
                        cursor.execute(postgres_script)
                    except psycopg2.Error as err:
                        if getattr(err, "pgcode", None) == "42P07":
                            print("Notice: relation already exists in Postgres (continuing)")
                        else:
                            raise
                record_migration_pg(pg_conn, name)

    if mysql_conn:
        mysql_conn.close()
    if pg_conn:
        pg_conn.close()
    print("All migrations completed.")

if __name__ == "__main__":
    run_migrations()
