
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "payment_reconciliation.db"


def migrate_reconciliation():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()

        # Prevent accidental duplicate migration
        existing = cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'reconciliation_runs'
            """
        ).fetchone()

        if existing:
            print("Migration already completed. No changes made.")
            return

        cursor.execute("BEGIN")

        # 1. Create reconciliation runs table
        cursor.execute(
            """
            CREATE TABLE reconciliation_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                run_status TEXT NOT NULL
                    CHECK (run_status IN (
                        'RUNNING', 'COMPLETED', 'FAILED'
                    )),
                total_batches INTEGER DEFAULT 0,
                total_bank_lines INTEGER DEFAULT 0,
                matched_count INTEGER DEFAULT 0,
                exception_count INTEGER DEFAULT 0
            )
            """
        )

        # 2. Create the first historical run
        historical_run_id = "RUN-2026-000001"

        cursor.execute(
            """
            INSERT INTO reconciliation_runs (
                run_id,
                started_at,
                completed_at,
                run_status,
                total_batches,
                total_bank_lines,
                matched_count,
                exception_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                historical_run_id,
                "2026-10-31T23:00:03",
                "2026-10-31T23:00:03",
                "COMPLETED",
                20,
                20,
                16,
                5,
            ),
        )

        # 3. Rebuild reconciliation_matches
        cursor.execute(
            """
            CREATE TABLE reconciliation_matches_new (
                reconciliation_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                settlement_batch_id TEXT NOT NULL,
                bank_line_id TEXT NOT NULL,
                matched_amount_minor INTEGER NOT NULL
                    CHECK (matched_amount_minor > 0),
                match_status TEXT NOT NULL
                    CHECK (match_status IN (
                        'MATCHED', 'PARTIAL',
                        'AMOUNT_MISMATCH',
                        'CURRENCY_MISMATCH',
                        'DATE_MISMATCH'
                    )),
                match_rule TEXT,
                matched_at TEXT NOT NULL,

                UNIQUE (
                    run_id,
                    settlement_batch_id,
                    bank_line_id
                ),

                FOREIGN KEY (run_id)
                    REFERENCES reconciliation_runs(run_id),

                FOREIGN KEY (settlement_batch_id)
                    REFERENCES settlement_batches(batch_id),

                FOREIGN KEY (bank_line_id)
                    REFERENCES bank_statement_lines(bank_line_id)
            )
            """
        )

        cursor.execute(
            """
            INSERT INTO reconciliation_matches_new (
                reconciliation_id,
                run_id,
                settlement_batch_id,
                bank_line_id,
                matched_amount_minor,
                match_status,
                match_rule,
                matched_at
            )
            SELECT
                reconciliation_id,
                ?,
                settlement_batch_id,
                bank_line_id,
                matched_amount_minor,
                match_status,
                match_rule,
                matched_at
            FROM reconciliation_matches
            """,
            (historical_run_id,),
        )

        # 4. Rebuild exceptions with run_id
        cursor.execute(
            """
            CREATE TABLE exceptions_new (
                exception_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                reconciliation_id TEXT,
                exception_type TEXT NOT NULL
                    CHECK (exception_type IN (
                        'UNMATCHED_SETTLEMENT',
                        'UNMATCHED_BANK_LINE',
                        'AMOUNT_MISMATCH',
                        'CURRENCY_MISMATCH',
                        'DATE_MISMATCH',
                        'DUPLICATE_EVENT',
                        'DUPLICATE_SETTLEMENT_LINE',
                        'OTHER'
                    )),
                severity TEXT NOT NULL
                    CHECK (severity IN (
                        'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
                    )),
                description TEXT NOT NULL,
                exception_status TEXT NOT NULL DEFAULT 'OPEN'
                    CHECK (exception_status IN (
                        'OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'
                    )),
                created_at TEXT NOT NULL,

                FOREIGN KEY (run_id)
                    REFERENCES reconciliation_runs(run_id),

                FOREIGN KEY (reconciliation_id)
                    REFERENCES reconciliation_matches_new(
                        reconciliation_id
                    )
            )
            """
        )

        cursor.execute(
            """
            INSERT INTO exceptions_new (
                exception_id,
                run_id,
                reconciliation_id,
                exception_type,
                severity,
                description,
                exception_status,
                created_at
            )
            SELECT
                exception_id,
                ?,
                reconciliation_id,
                exception_type,
                severity,
                description,
                exception_status,
                created_at
            FROM exceptions
            """,
            (historical_run_id,),
        )

        # 5. Rebuild resolutions to reference new exceptions
        cursor.execute(
            """
            CREATE TABLE resolutions_new (
                resolution_id TEXT PRIMARY KEY,
                exception_id TEXT NOT NULL,
                resolved_by TEXT NOT NULL,
                resolution_action TEXT NOT NULL,
                resolution_notes TEXT,
                previous_status TEXT,
                new_status TEXT NOT NULL,
                resolved_at TEXT NOT NULL,

                FOREIGN KEY (exception_id)
                    REFERENCES exceptions_new(exception_id)
            )
            """
        )

        cursor.execute(
            """
            INSERT INTO resolutions_new (
                resolution_id,
                exception_id,
                resolved_by,
                resolution_action,
                resolution_notes,
                previous_status,
                new_status,
                resolved_at
            )
            SELECT
                resolution_id,
                exception_id,
                resolved_by,
                resolution_action,
                resolution_notes,
                previous_status,
                new_status,
                resolved_at
            FROM resolutions
            """
        )

        # 6. Replace old tables
        cursor.execute("DROP TABLE resolutions")
        cursor.execute("DROP TABLE exceptions")
        cursor.execute("DROP TABLE reconciliation_matches")

        cursor.execute(
            "ALTER TABLE reconciliation_matches_new "
            "RENAME TO reconciliation_matches"
        )

        cursor.execute(
            "ALTER TABLE exceptions_new RENAME TO exceptions"
        )

        cursor.execute(
            "ALTER TABLE resolutions_new RENAME TO resolutions"
        )

        # 7. Recreate indexes
        cursor.execute(
            """
            CREATE INDEX idx_reconciliation_status
            ON reconciliation_matches(match_status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX idx_exceptions_status
            ON exceptions(exception_status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX idx_reconciliation_run
            ON reconciliation_matches(run_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX idx_exceptions_run
            ON exceptions(run_id)
            """
        )

        connection.commit()

        print("Migration completed successfully!")
        print("Historical run:", historical_run_id)
        print("Matches preserved:", cursor.execute(
            "SELECT COUNT(*) FROM reconciliation_matches"
        ).fetchone()[0])
        print("Exceptions preserved:", cursor.execute(
            "SELECT COUNT(*) FROM exceptions"
        ).fetchone()[0])

    except Exception as error:
        connection.rollback()
        print("Migration failed:", error)
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    migrate_reconciliation()
