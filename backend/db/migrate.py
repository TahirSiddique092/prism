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
    migration_file = Path(__file__).parent / "migrations" / "001_init.sql"
    with open(migration_file, "r") as f:
        content = f.read()

    # Split by ENGINE comments
    parts = content.split("-- ENGINE: ")
    
    mysql_script = ""
    postgres_script = ""
    
    for part in parts:
        if part.startswith("MySQL"):
            mysql_script = part[len("MySQL"):].strip()
        elif part.startswith("Postgres"):
            postgres_script = part[len("Postgres"):].strip()

    # Execute MySQL
    if mysql_script:
        print("Running MySQL migrations...")
        mysql_conn = get_mysql_conn()
        if mysql_conn:
            cursor = mysql_conn.cursor()
            # Split basic statements by semicolon, being careful around trigger
            # For simplicity, using execute multi=True if possible, but triggers fail with DELIMITER in Python.
            # To handle DELIMITER correctly without complex parsing, we extract it manually:
            statements = mysql_script.split("DELIMITER //")
            
            # Normal statements
            for stmt in statements[0].split(";"):
                stmt = stmt.strip()
                if stmt:
                    cursor.execute(stmt)
            
            # Trigger statements
            if len(statements) > 1:
                trigger_block = statements[1].split("DELIMITER ;")[0].strip()
                if trigger_block:
                    cursor.execute(trigger_block)

            mysql_conn.close()
            print("MySQL migrations completed.")

    # Execute Postgres
    if postgres_script:
        print("Running Postgres migrations...")
        pg_conn = get_postgres_conn()
        if pg_conn:
            with pg_conn.cursor() as cursor:
                cursor.execute(postgres_script)
            pg_conn.close()
            print("Postgres migrations completed.")

if __name__ == "__main__":
    run_migrations()
