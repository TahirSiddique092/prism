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

def run_migrations():
    migrations_dir = Path(__file__).parent / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    mysql_conn = get_mysql_conn()
    pg_conn = get_postgres_conn()

    for migration_file in migration_files:
        print(f"Running migration: {migration_file.name}")
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
            cursor = mysql_conn.cursor()
            statements = mysql_script.split("DELIMITER //")
            for stmt in statements[0].split(";"):
                stmt = stmt.strip()
                if stmt:
                    cursor.execute(stmt)
            if len(statements) > 1:
                trigger_block = statements[1].split("DELIMITER ;")[0].strip()
                if trigger_block:
                    cursor.execute(trigger_block)

        if postgres_script and pg_conn:
            with pg_conn.cursor() as cursor:
                cursor.execute(postgres_script)

    if mysql_conn:
        mysql_conn.close()
    if pg_conn:
        pg_conn.close()
    print("All migrations completed.")

if __name__ == "__main__":
    run_migrations()
