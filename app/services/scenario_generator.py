
import sqlite3

from database.db import get_connection


def create_test_scenarios():
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        cursor = connection.cursor()

        # Clear old reconciliation results
        cursor.execute("DELETE FROM resolutions")
        cursor.execute("DELETE FROM exceptions")
        cursor.execute("DELETE FROM reconciliation_matches")

        # Remove an extra test record from an earlier run
        cursor.execute("""
            DELETE FROM bank_statement_lines
            WHERE bank_line_id = 'BANK-TEST-EXTRA-001'
        """)

        # Read original bank records
        bank_lines = cursor.execute("""
            SELECT bank_line_id, amount_minor, currency, transaction_date
            FROM bank_statement_lines
            ORDER BY bank_line_id
        """).fetchall()

        if len(bank_lines) < 6:
            raise ValueError("At least 6 bank records are required.")

        # Scenario 1: Amount mismatch (reduce by ₹100)
        cursor.execute("""
            UPDATE bank_statement_lines
            SET amount_minor = amount_minor - 10000
            WHERE bank_line_id = ?
        """, (bank_lines[0]["bank_line_id"],))

        # Scenario 2: Currency mismatch
        cursor.execute("""
            UPDATE bank_statement_lines
            SET currency = 'USD'
            WHERE bank_line_id = ?
        """, (bank_lines[1]["bank_line_id"],))

        # Scenario 3: Date mismatch (move forward 10 days)
        cursor.execute("""
            UPDATE bank_statement_lines
            SET transaction_date = date(transaction_date, '+10 days')
            WHERE bank_line_id = ?
        """, (bank_lines[2]["bank_line_id"],))

        # Scenario 4: Missing bank record
        cursor.execute("""
            DELETE FROM bank_statement_lines
            WHERE bank_line_id = ?
        """, (bank_lines[3]["bank_line_id"],))

        # Scenario 5: Extra unmatched bank record
        extra_line = bank_lines[4]

        cursor.execute("""
            INSERT INTO bank_statement_lines (
                bank_line_id,
                merchant_id,
                bank_reference,
                amount_minor,
                currency,
                transaction_date,
                description
            )
            SELECT
                'BANK-TEST-EXTRA-001',
                merchant_id,
                'BANK-REF-TEST-EXTRA-001',
                50000,
                currency,
                transaction_date,
                'Test extra unmatched bank record'
            FROM bank_statement_lines
            WHERE bank_line_id = ?
        """, (extra_line["bank_line_id"],))

        connection.commit()

        print("Test scenarios created successfully!")
        print("1. Amount mismatch")
        print("2. Currency mismatch")
        print("3. Date mismatch")
        print("4. Missing bank record")
        print("5. Extra unmatched bank record")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    create_test_scenarios()
