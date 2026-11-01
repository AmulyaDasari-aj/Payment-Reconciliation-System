from database.db import get_connection

def validate_database(connection=None):

    close_connection = connection is None

    if connection is None:
        connection = get_connection()

    results = {}

    print("\n========== DATA VALIDATION ==========\n")

    try:

        # 1. Check duplicate primary IDs
        tables = {
            "merchants": "merchant_id",
            "payment_orders": "payment_id",
            "payment_attempts": "attempt_id",
            "processor_events": "event_id",
            "settlement_batches": "batch_id",
            "settlement_lines": "settlement_line_id",
            "bank_statement_lines": "bank_line_id",
            "reconciliation_matches": "reconciliation_id",
            "exceptions": "exception_id",
            "resolutions": "resolution_id"
        }

        for table, column in tables.items():

            query = f"""
                SELECT COUNT(*) - COUNT(DISTINCT {column})
                FROM {table}
            """

            duplicates = connection.execute(query).fetchone()[0]


            results[f"{table}_duplicate_ids"] = duplicates

            print(
                f"{table} duplicate IDs: {duplicates}"
            )

        # 2. Check settlement calculations
        incorrect_settlements = connection.execute("""
            SELECT COUNT(*)
            FROM settlement_batches
            WHERE gross_amount_minor - fee_amount_minor
                != net_amount_minor
        """).fetchone()[0]

        results["incorrect_settlements"] = incorrect_settlements
        print(
            "\nIncorrect settlement calculations:",
            incorrect_settlements
        )

        # 3. Check missing payment merchants
        missing_merchants = connection.execute("""
            SELECT COUNT(*)
            FROM payment_orders p
            LEFT JOIN merchants m
            ON p.merchant_id = m.merchant_id
            WHERE m.merchant_id IS NULL
        """).fetchone()[0]


        results["missing_merchants"] = missing_merchants
        print(
            "Payments with missing merchants:",
            missing_merchants
        )

        # 4. Check reconciliation references
        missing_bank_lines = connection.execute("""
            SELECT COUNT(*)
            FROM reconciliation_matches r
            LEFT JOIN bank_statement_lines b
            ON r.bank_line_id = b.bank_line_id
            WHERE b.bank_line_id IS NULL
        """).fetchone()[0]


        results["missing_bank_lines"] = missing_bank_lines
        print(
            "Reconciliations with missing bank lines:",
            missing_bank_lines
        )

        # 5. Check all foreign-key relationships
        foreign_key_tables = [
            "payment_orders",
            "payment_attempts",
            "processor_events",
            "settlement_batches",
            "settlement_lines",
            "bank_statement_lines",
            "reconciliation_matches",
            "exceptions",
            "resolutions"
        ]

        print("\nForeign Key Validation:")

        for table in foreign_key_tables:

            result = connection.execute(
                f"PRAGMA foreign_key_check({table})"
            ).fetchall()



            results[f"{table}_foreign_key_errors"] = len(result)
            print(
                f"{table}: {len(result)} foreign key errors"
            )

        # 6. Check invalid payment statuses
        valid_payment_statuses = (
            "CAPTURED", "FAILED", "AUTHORIZED"
        )

        placeholders = ",".join(
            "?" for _ in valid_payment_statuses
        )

        invalid_payments = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM payment_orders
            WHERE payment_status NOT IN ({placeholders})
               OR payment_status IS NULL
            """,
            valid_payment_statuses
        ).fetchone()[0]


        results["invalid_payments"] = invalid_payments
        print(
            "\nPayments with invalid statuses:",
            invalid_payments
        )

        # 7. Check invalid attempt statuses
        valid_attempt_statuses = (
            "CAPTURED", "FAILED", "AUTHORIZED"
        )

        placeholders = ",".join(
            "?" for _ in valid_attempt_statuses
        )

        invalid_attempts = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM payment_attempts
            WHERE attempt_status NOT IN ({placeholders})
               OR attempt_status IS NULL
            """,
            valid_attempt_statuses
        ).fetchone()[0]


        results["invalid_attempts"] = invalid_attempts
        print(
            "Attempts with invalid statuses:",
            invalid_attempts
        )


        # 8. Check payment attempt dates
        invalid_attempt_dates = connection.execute("""
            SELECT COUNT(*)
            FROM payment_attempts a
            JOIN payment_orders p
            ON a.payment_id = p.payment_id
            WHERE a.attempted_at < p.created_at
        """).fetchone()[0]


        results["invalid_attempt_dates"] = invalid_attempt_dates
        print(
            "\nAttempts before payment creation:",
            invalid_attempt_dates
        )

        print("\n========== VALIDATION COMPLETED ==========")

        return results

    finally:
        if close_connection:
            connection.close()


if __name__ == "__main__":
    validate_database()