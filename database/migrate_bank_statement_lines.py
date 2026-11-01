import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "payment_reconciliation.db"

connection = sqlite3.connect(DB_PATH)

try:
    connection.execute("PRAGMA foreign_keys = ON")

    columns = connection.execute(
        "PRAGMA table_info(bank_statement_lines)"
    ).fetchall()

    column_names = [column[1] for column in columns]

    if "settlement_batch_id" not in column_names:
        connection.execute("""
            ALTER TABLE bank_statement_lines
            ADD COLUMN settlement_batch_id TEXT
            REFERENCES settlement_batches(batch_id)
        """)
        connection.commit()
        print("Column added successfully!")
    else:
        print("Column already exists.")

finally:
    connection.close()