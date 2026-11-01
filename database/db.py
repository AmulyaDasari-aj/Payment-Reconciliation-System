
import sqlite3
from pathlib import Path

# Find the database folder
BASE_DIR = Path(__file__).resolve().parent

# Database file location
DB_PATH = BASE_DIR / "payment_reconciliation_scale.db"
# DB_PATH = BASE_DIR / "payment_reconciliation_exception_test.db"

# SQL schema file location
SCHEMA_PATH = BASE_DIR / "schema.sql"


def get_connection():
    """Create and return a database connection."""
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    """Create all database tables using schema.sql."""
    connection = get_connection()

    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as file:
            schema = file.read()

        connection.executescript(schema)
        connection.commit()

        print("Database initialized successfully!")

    except Exception as error:
        connection.rollback()
        print("Database initialization failed:", error)
        raise

    finally:
        connection.close()


def get_all_tables():
    """Return all table names in the database."""
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )

        return [row[0] for row in cursor.fetchall()]

    finally:
        connection.close()
