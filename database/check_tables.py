import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent / "payment_reconciliation.db"
connection = sqlite3.connect(db_path)

run_id = "RUN-20261101140100235521"

print("New reconciliation run:")

run = connection.execute("""
    SELECT run_status, total_batches, total_bank_lines,
           matched_count, exception_count
    FROM reconciliation_runs
    WHERE run_id = ?
""", (run_id,)).fetchone()

print(run)

print("\nMatch status counts:")

statuses = connection.execute("""
    SELECT match_status, COUNT(*)
    FROM reconciliation_matches
    WHERE run_id = ?
    GROUP BY match_status
""", (run_id,)).fetchall()

for status in statuses:
    print(status)

print("\nTotal reconciliation runs:",
      connection.execute(
          "SELECT COUNT(*) FROM reconciliation_runs"
      ).fetchone()[0])

print("Foreign key errors:",
      connection.execute("PRAGMA foreign_key_check").fetchall())

connection.close()

import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent / "payment_reconciliation.db"
connection = sqlite3.connect(db_path)

rows = connection.execute("""
    SELECT
        b.bank_line_id,
        b.bank_reference,
        COUNT(DISTINCT r.settlement_batch_id) AS batch_count,
        GROUP_CONCAT(DISTINCT r.settlement_batch_id)
    FROM bank_statement_lines b
    LEFT JOIN reconciliation_matches r
        ON b.bank_line_id = r.bank_line_id
    WHERE b.settlement_batch_id IS NULL
    GROUP BY b.bank_line_id, b.bank_reference
    ORDER BY b.bank_line_id
""").fetchall()

print("Historical bank-line links:")

for row in rows:
    print(row)

connection.close()