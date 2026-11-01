import sqlite3
from pathlib import Path


def test_exception_status_values():
    """Check that valid exception statuses are accepted."""

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        schema = Path("database/schema.sql").read_text(
            encoding="utf-8"
        )
        connection.executescript(schema)

        connection.execute(
            """
            INSERT INTO reconciliation_runs (
                run_id, started_at, run_status
            )
            VALUES (?, ?, ?)
            """,
            ("RUN-TEST-001", "2026-11-01", "COMPLETED"),
        )

        valid_statuses = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]

        for index, status in enumerate(valid_statuses, start=1):
            connection.execute(
                """
                INSERT INTO exceptions (
                    exception_id, run_id, exception_type,
                    severity, description, exception_status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"EXC-TEST-{index:03d}",
                    "RUN-TEST-001",
                    "AMOUNT_MISMATCH",
                    "HIGH",
                    "Test exception",
                    status,
                    "2026-11-01",
                ),
            )

        count = connection.execute(
            "SELECT COUNT(*) FROM exceptions"
        ).fetchone()[0]

        assert count == 4

    finally:
        connection.close()


def test_invalid_exception_status_is_rejected():
    """Ensure invalid exception statuses are rejected."""

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        schema = Path("database/schema.sql").read_text(
            encoding="utf-8"
        )
        connection.executescript(schema)

        connection.execute(
            """
            INSERT INTO reconciliation_runs (
                run_id, started_at, run_status
            )
            VALUES (?, ?, ?)
            """,
            ("RUN-TEST-002", "2026-11-01", "COMPLETED"),
        )

        try:
            connection.execute(
                """
                INSERT INTO exceptions (
                    exception_id, run_id, exception_type,
                    severity, description, exception_status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "EXC-INVALID-001",
                    "RUN-TEST-002",
                    "AMOUNT_MISMATCH",
                    "HIGH",
                    "Invalid status test",
                    "INVALID_STATUS",
                    "2026-11-01",
                ),
            )
            assert False, "Invalid status was accepted."

        except sqlite3.IntegrityError:
            pass

    finally:
        connection.close()


def test_resolution_history_is_recorded():
    """Verify that exception status changes are stored."""

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        schema = Path("database/schema.sql").read_text(
            encoding="utf-8"
        )
        connection.executescript(schema)

        connection.execute(
            """
            INSERT INTO reconciliation_runs (
                run_id, started_at, run_status
            )
            VALUES (?, ?, ?)
            """,
            ("RUN-TEST-003", "2026-11-01", "COMPLETED"),
        )

        connection.execute(
            """
            INSERT INTO exceptions (
                exception_id, run_id, exception_type,
                severity, description, exception_status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "EXC-TEST-003",
                "RUN-TEST-003",
                "AMOUNT_MISMATCH",
                "HIGH",
                "Test exception",
                "OPEN",
                "2026-11-01",
            ),
        )

        connection.execute(
            """
            INSERT INTO resolutions (
                resolution_id, exception_id, resolved_by,
                resolution_action, resolution_notes,
                previous_status, new_status, resolved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RES-TEST-001",
                "EXC-TEST-003",
                "Operations Analyst",
                "STATUS_UPDATED",
                "Investigation started",
                "OPEN",
                "IN_PROGRESS",
                "2026-11-01",
            ),
        )

        result = connection.execute(
            """
            SELECT previous_status, new_status
            FROM resolutions
            WHERE exception_id = ?
            """,
            ("EXC-TEST-003",),
        ).fetchone()

        assert result == ("OPEN", "IN_PROGRESS")

    finally:
        connection.close()


def test_resolution_requires_valid_exception():
    """Ensure a resolution cannot reference a missing exception."""

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
                INSERT INTO resolutions (
                    resolution_id, exception_id, resolved_by,
                    resolution_action, resolution_notes,
                    previous_status, new_status, resolved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "RES-INVALID-001",
                    "EXC-NOT-EXIST",
                    "Operations Analyst",
                    "STATUS_UPDATED",
                    "Test",
                    "OPEN",
                    "IN_PROGRESS",
                    "2026-11-01",
                ),
            )
            assert False, "Resolution with invalid exception was accepted."

        except sqlite3.IntegrityError:
            pass

    finally:
        connection.close()