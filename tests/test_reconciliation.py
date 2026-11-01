import sqlite3
from pathlib import Path
from app.services import reconciliation

def test_reconciliation_schema():
    """Check that reconciliation audit tables exist."""

    database_path = Path("database/schema.sql")

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        connection.executescript(
            database_path.read_text(encoding="utf-8")
        )

        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        assert "reconciliation_runs" in tables
        assert "reconciliation_matches" in tables
        assert "exceptions" in tables

    finally:
        connection.close()


def test_match_requires_valid_reconciliation_run():
    """Ensure a match cannot reference a missing reconciliation run."""

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        schema = Path("database/schema.sql").read_text(
            encoding="utf-8"
        )
        connection.executescript(schema)

        try:
            connection.execute(
                """
                INSERT INTO reconciliation_matches (
                    reconciliation_id,
                    run_id,
                    settlement_batch_id,
                    bank_line_id,
                    matched_amount_minor,
                    match_status,
                    matched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "REC-TEST-001",
                    "INVALID-RUN",
                    "INVALID-BATCH",
                    "INVALID-BANK",
                    100,
                    "MATCHED",
                    "2026-11-01",
                ),
            )
            assert False, "Invalid reconciliation run was accepted."

        except sqlite3.IntegrityError:
            pass

    finally:
        connection.close()


def test_exception_requires_valid_reconciliation_run():
    """Ensure an exception cannot reference a missing run."""

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        schema = Path("database/schema.sql").read_text(
            encoding="utf-8"
        )
        connection.executescript(schema)

        try:
            connection.execute(
                """
                INSERT INTO exceptions (
                    exception_id,
                    run_id,
                    exception_type,
                    severity,
                    description,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "EXC-TEST-001",
                    "INVALID-RUN",
                    "AMOUNT_MISMATCH",
                    "HIGH",
                    "Test exception",
                    "2026-11-01",
                ),
            )
            assert False, "Invalid reconciliation run was accepted."

        except sqlite3.IntegrityError:
            pass

    finally:
        connection.close()


def test_same_records_can_be_reconciled_in_different_runs():
    """Allow the same settlement and bank line in separate runs."""

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        schema = Path("database/schema.sql").read_text(
            encoding="utf-8"
        )
        connection.executescript(schema)

        connection.execute(
            """
            INSERT INTO merchants (
                merchant_id, merchant_name
            ) VALUES ('MER-001', 'Test Merchant')
            """
        )

        connection.execute(
            """
            INSERT INTO settlement_batches (
                batch_id, merchant_id, processor_name,
                settlement_reference, currency,
                gross_amount_minor, fee_amount_minor,
                net_amount_minor, settlement_status,
                settlement_date
            ) VALUES (
                'SET-001', 'MER-001', 'TEST',
                'REF-001', 'INR', 1000, 100,
                900, 'SETTLED', '2026-11-01'
            )
            """
        )

        connection.execute(
            """
            INSERT INTO bank_statement_lines (
                bank_line_id, merchant_id, bank_reference,
                amount_minor, currency, transaction_date
            ) VALUES (
                'BANK-001', 'MER-001', 'BANK-REF-001',
                900, 'INR', '2026-11-01'
            )
            """
        )

        for run_id in ("RUN-001", "RUN-002"):
            connection.execute(
                """
                INSERT INTO reconciliation_runs (
                    run_id, started_at, run_status
                ) VALUES (?, ?, ?)
                """,
                (run_id, "2026-11-01", "COMPLETED"),
            )

            connection.execute(
                """
                INSERT INTO reconciliation_matches (
                    reconciliation_id, run_id,
                    settlement_batch_id, bank_line_id,
                    matched_amount_minor, match_status,
                    matched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"REC-{run_id}", run_id,
                    "SET-001", "BANK-001",
                    900, "MATCHED", "2026-11-01",
                ),
            )

        count = connection.execute(
            "SELECT COUNT(*) FROM reconciliation_matches"
        ).fetchone()[0]

        assert count == 2

    finally:
        connection.close()


def test_historically_matched_bank_line_is_not_flagged(
    tmp_path, monkeypatch
):
    """Do not flag historical bank lines as newly unmatched."""

    database_path = tmp_path / "test_reconciliation.db"

    def test_connection():
        connection = sqlite3.connect(database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    # Create the test database
    connection = test_connection()
    schema = Path("database/schema.sql").read_text(
        encoding="utf-8"
    )
    connection.executescript(schema)

    connection.execute("""
        INSERT INTO merchants (
            merchant_id, merchant_name
        ) VALUES ('MER-TEST', 'Test Merchant')
    """)

    connection.execute("""
        INSERT INTO settlement_batches (
            batch_id, merchant_id, processor_name,
            settlement_reference, currency,
            gross_amount_minor, fee_amount_minor,
            net_amount_minor, settlement_status,
            settlement_date
        ) VALUES (
            'SET-TEST', 'MER-TEST', 'TEST',
            'REF-TEST', 'INR', 1000, 20,
            980, 'SETTLED', '2026-11-01'
        )
    """)

    # Valid settlement capture and fee lines
    connection.execute("""
        INSERT INTO settlement_lines (
            settlement_line_id, batch_id,
            line_type, amount_minor, currency,
            line_reference, created_at
        ) VALUES (
            'STL-TEST-001', 'SET-TEST',
            'CAPTURE', 1000, 'INR',
            'LINE-TEST-001', '2026-11-01 10:00:00'
        )
    """)



    connection.execute("""
        INSERT INTO settlement_lines (
            settlement_line_id, batch_id,
            line_type, amount_minor, currency,
            line_reference, created_at
        )
        VALUES (
            'STL-TEST-002', 'SET-TEST',
            'FEE', -20, 'INR',
            'LINE-TEST-002', '2026-11-01 10:00:00'
        )
    """)

    # Current bank line linked to the settlement
    connection.execute("""
        INSERT INTO bank_statement_lines (
            bank_line_id, merchant_id,
            settlement_batch_id, bank_reference,
            amount_minor, currency, transaction_date
        ) VALUES (
            'BANK-CURRENT', 'MER-TEST',
            'SET-TEST', 'REF-CURRENT',
            980, 'INR', '2026-11-01'
        )
    """)

    # Old bank line with a historical reconciliation match
    connection.execute("""
        INSERT INTO bank_statement_lines (
            bank_line_id, merchant_id,
            bank_reference, amount_minor,
            currency, transaction_date
        ) VALUES (
            'BANK-HISTORICAL', 'MER-TEST',
            'REF-HISTORICAL', 980,
            'INR', '2026-11-01'
        )
    """)

    # Truly unmatched bank line
    connection.execute("""
        INSERT INTO bank_statement_lines (
            bank_line_id, merchant_id,
            bank_reference, amount_minor,
            currency, transaction_date
        ) VALUES (
            'BANK-EXTRA', 'MER-TEST',
            'REF-EXTRA', 500,
            'INR', '2026-11-01'
        )
    """)

    # Create an earlier reconciliation run
    connection.execute("""
        INSERT INTO reconciliation_runs (
            run_id, started_at, run_status
        ) VALUES (
            'RUN-OLD', '2026-11-01', 'COMPLETED'
        )
    """)

    connection.execute("""
        INSERT INTO reconciliation_matches (
            reconciliation_id, run_id,
            settlement_batch_id, bank_line_id,
            matched_amount_minor, match_status, matched_at
        ) VALUES (
            'REC-OLD', 'RUN-OLD',
            'SET-TEST', 'BANK-HISTORICAL',
            900, 'MATCHED', '2026-11-01'
        )
    """)

    connection.commit()
    connection.close()

    # Use the temporary database for reconciliation
    monkeypatch.setattr(
        reconciliation, "get_connection", test_connection
    )

    reconciliation.run_reconciliation()

    # Verify the new run creates only one exception
    connection = test_connection()

    try:
        exceptions = connection.execute("""
            SELECT exception_type, description
            FROM exceptions
            WHERE run_id != 'RUN-OLD'
        """).fetchall()

        assert len(exceptions) == 1
        assert exceptions[0][0] == "UNMATCHED_BANK_LINE"
        assert "BANK-EXTRA" in exceptions[0][1]
        assert "BANK-HISTORICAL" not in exceptions[0][1]

    finally:
        connection.close()