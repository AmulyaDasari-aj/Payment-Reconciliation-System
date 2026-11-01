
import sqlite3
from pathlib import Path

from app.services import data_generator


def setup_test_database(tmp_path, monkeypatch):
    db_path = tmp_path / "test_database.db"
    schema_path = Path("database/schema.sql")

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")

    schema = schema_path.read_text(encoding="utf-8")
    connection.executescript(schema)
    connection.commit()
    connection.close()

    def temporary_connection():
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    monkeypatch.setattr(
        data_generator,
        "get_connection",
        temporary_connection
    )

    return db_path



def test_generated_record_counts(tmp_path, monkeypatch):
    from config import (
        MERCHANT_COUNT,
        PAYMENT_COUNT,
        ATTEMPT_COUNT,
    )

    db_path = setup_test_database(tmp_path, monkeypatch)

    data_generator.generate_sample_data()

    connection = sqlite3.connect(db_path)

    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM merchants"
        ).fetchone()[0] == MERCHANT_COUNT

        assert connection.execute(
            "SELECT COUNT(*) FROM payment_orders"
        ).fetchone()[0] == PAYMENT_COUNT

        assert connection.execute(
            "SELECT COUNT(*) FROM payment_attempts"
        ).fetchone()[0] == ATTEMPT_COUNT

        assert connection.execute(
            "SELECT COUNT(*) FROM processor_events"
        ).fetchone()[0] == ATTEMPT_COUNT

    finally:
        connection.close()




def test_generated_ids_are_unique(tmp_path, monkeypatch):
    db_path = setup_test_database(tmp_path, monkeypatch)

    data_generator.generate_sample_data()

    connection = sqlite3.connect(db_path)

    try:
        tables = {
            "merchants": "merchant_id",
            "payment_orders": "payment_id",
            "payment_attempts": "attempt_id",
            "processor_events": "event_id",
        }

        for table, column in tables.items():
            total = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            unique = connection.execute(
                f"SELECT COUNT(DISTINCT {column}) FROM {table}"
            ).fetchone()[0]

            assert total == unique, f"Duplicate IDs found in {table}"

    finally:
        connection.close()




def test_generated_foreign_keys_are_valid(tmp_path, monkeypatch):
    db_path = setup_test_database(tmp_path, monkeypatch)

    data_generator.generate_sample_data()

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert errors == [], f"Foreign key errors found: {errors}"

    finally:
        connection.close()




def test_generator_is_reproducible(tmp_path, monkeypatch):
    db_path = setup_test_database(tmp_path, monkeypatch)

    tables = [
        "merchants",
        "payment_orders",
        "payment_attempts",
        "processor_events",
    ]

    def get_snapshot():
        connection = sqlite3.connect(db_path)

        try:
            snapshot = {}

            for table in tables:
                snapshot[table] = connection.execute(
                    f"SELECT * FROM {table} ORDER BY 1"
                ).fetchall()

            return snapshot

        finally:
            connection.close()

    # First generation
    data_generator.generate_sample_data()
    first_result = get_snapshot()

    # Second generation using the same seed
    data_generator.generate_sample_data()
    second_result = get_snapshot()

    assert first_result == second_result, (
        "Generated data is not reproducible!"
    )
