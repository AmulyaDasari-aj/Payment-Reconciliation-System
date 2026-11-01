
from datetime import datetime
from database.db import get_connection


def view_exceptions():
    """Display all exceptions."""

    connection = get_connection()
    connection.row_factory = __import__("sqlite3").Row

    try:
        rows = connection.execute("""
            SELECT
                exception_id,
                exception_type,
                severity,
                description,
                exception_status,
                created_at
            FROM exceptions
            ORDER BY created_at DESC
        """).fetchall()

        print("\n--- EXCEPTION LIST ---")

        for row in rows:
            print(
                row["exception_id"],
                "|", row["exception_type"],
                "|", row["severity"],
                "|", row["exception_status"]
            )

        print("\nTotal exceptions:", len(rows))

    finally:
        connection.close()


def update_exception_status(
    exception_id,
    new_status,
    resolved_by,
    notes=""
):
    """Update exception status and save audit history."""

    allowed_statuses = [
        "OPEN",
        "IN_PROGRESS",
        "RESOLVED",
        "CLOSED"
    ]

    if new_status not in allowed_statuses:
        print("Invalid exception status!")
        return

    connection = get_connection()

    try:
        cursor = connection.cursor()

        exception = cursor.execute("""
            SELECT exception_status
            FROM exceptions
            WHERE exception_id = ?
        """, (exception_id,)).fetchone()

        if exception is None:
            print("Exception not found!")
            return

        previous_status = exception[0]

        if previous_status == new_status:
            print("Exception already has this status.")
            return

        if previous_status in ("RESOLVED", "CLOSED"):
            print("This exception is already finalized.")
            return

        if new_status == "CLOSED" and previous_status != "RESOLVED":
            print("Resolve the exception before closing it.")
            return

        resolved_at = datetime.now().isoformat(timespec="seconds")

        resolution_id = (
            f"RES-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        )

        # Update exception status
        cursor.execute("""
            UPDATE exceptions
            SET exception_status = ?
            WHERE exception_id = ?
        """, (new_status, exception_id))

        # Store audit history
        cursor.execute("""
            INSERT INTO resolutions (
                resolution_id,
                exception_id,
                resolved_by,
                resolution_action,
                resolution_notes,
                previous_status,
                new_status,
                resolved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            resolution_id,
            exception_id,
            resolved_by,
            f"STATUS_CHANGED_TO_{new_status}",
            notes,
            previous_status,
            new_status,
            resolved_at
        ))

        connection.commit()

        print("\nException updated successfully!")
        print("Exception ID:", exception_id)
        print("Previous status:", previous_status)
        print("New status:", new_status)
        print("Resolution ID:", resolution_id)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    view_exceptions()

    update_exception_status(
        exception_id="EXC-2026-000001",
        new_status="RESOLVED",
        resolved_by="Operations Analyst",
        notes="Investigated the amount difference and recorded the resolution."
    )
    view_exceptions()
