
from datetime import datetime

from database.db import get_connection


def run_reconciliation():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Create a new reconciliation run
        run_timestamp = datetime.now().isoformat(timespec="microseconds")
        run_id = "RUN-" + datetime.now().strftime("%Y%m%d%H%M%S%f")

        cursor.execute(
            """
            INSERT INTO reconciliation_runs (
                run_id, started_at, run_status
            )
            VALUES (?, ?, ?)
            """,
            (run_id, run_timestamp, "RUNNING"),
        )

        # Read settled batches
        batches = cursor.execute(
            """
            SELECT
                batch_id,
                merchant_id,
                gross_amount_minor,
                fee_amount_minor,
                net_amount_minor,
                currency,
                settlement_date
            FROM settlement_batches
            WHERE settlement_status = 'SETTLED'
            ORDER BY batch_id
            """
        ).fetchall()

        # Read all bank statement lines
        bank_lines = cursor.execute(
            """
            SELECT
                bank_line_id,
                merchant_id,
                settlement_batch_id,
                amount_minor,
                currency,
                transaction_date
            FROM bank_statement_lines
            ORDER BY bank_line_id
            """
        ).fetchall()

        # Group bank lines by settlement batch
        bank_lines_by_batch = {}

        for line in bank_lines:
            batch_id = line[2]

            if batch_id is not None:
                bank_lines_by_batch.setdefault(batch_id, []).append(line)

        used_bank_lines = set()

        matched_count = 0
        exception_count = 0
        reconciliation_counter = 0
        exception_counter = 0
        unmatched_bank_count = 0

        def create_exception(reconciliation_id, exception_type,
                             severity, description):
            nonlocal exception_counter, exception_count

            exception_counter += 1

            cursor.execute(
                """
                INSERT INTO exceptions (
                    exception_id,
                    run_id,
                    reconciliation_id,
                    exception_type,
                    severity,
                    description,
                    exception_status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"EXC-{run_id}-{exception_counter:06d}",
                    run_id,
                    reconciliation_id,
                    exception_type,
                    severity,
                    description,
                    "OPEN",
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

            exception_count += 1

        # Reconcile each settlement batch
        for batch in batches:
            (
                batch_id,
                merchant_id,
                gross_amount,
                fee_amount,
                settlement_amount,
                settlement_currency,
                settlement_date,
            ) = batch

            linked_lines = bank_lines_by_batch.get(batch_id, [])


            # Validate settlement gross amount and fee
            settlement_lines = cursor.execute(
                """
                SELECT
                    line_type,
                    amount_minor,
                    currency
                FROM settlement_lines
                WHERE batch_id = ?
                """,
                (batch_id,),
            ).fetchall()

            capture_total = sum(
                line[1] for line in settlement_lines
                if line[0] == "CAPTURE"
            )

            fee_total = abs(sum(
                line[1] for line in settlement_lines
                if line[0] == "FEE"
            ))

            expected_fee = (gross_amount * 2 + 50) // 100

            fee_mismatch = (
                capture_total != gross_amount
                or fee_total != fee_amount
                or fee_amount != expected_fee
                or gross_amount - fee_amount != settlement_amount
                or any(line[2] != settlement_currency for line in settlement_lines)
            )
            # No bank lines found
            if not linked_lines:
                create_exception(
                    None,
                    "UNMATCHED_SETTLEMENT",
                    "HIGH",
                    f"No bank statement found for {batch_id}",
                )
                continue

            # Only use bank lines belonging to this merchant
            valid_lines = [
                line for line in linked_lines
                if line[1] == merchant_id
            ]

            if not valid_lines:
                create_exception(
                    None,
                    "UNMATCHED_SETTLEMENT",
                    "HIGH",
                    f"No bank lines found for the correct merchant "
                    f"for {batch_id}",
                )
                continue

            for line in valid_lines:
                used_bank_lines.add(line[0])

            # Aggregate all linked bank amounts
            bank_total = sum(line[3] for line in valid_lines)

            # Check currency
            currency_mismatch = any(
                line[4] != settlement_currency
                for line in valid_lines
            )

            # Check transaction dates
            date_mismatch = any(
                abs(
                    (
                        datetime.fromisoformat(settlement_date)
                        - datetime.fromisoformat(line[5])
                    ).days
                ) > 3
                for line in valid_lines
            )

            # Determine reconciliation status
            if currency_mismatch:
                match_status = "CURRENCY_MISMATCH"
                exception_type = "CURRENCY_MISMATCH"
                severity = "CRITICAL"

            elif date_mismatch:
                match_status = "DATE_MISMATCH"
                exception_type = "DATE_MISMATCH"
                severity = "MEDIUM"

            elif settlement_amount != bank_total:
                match_status = "AMOUNT_MISMATCH"
                exception_type = "AMOUNT_MISMATCH"
                severity = "HIGH"

            else:
                match_status = "MATCHED"
                exception_type = None
                severity = None

            # Create one match record for every bank line
            for line in valid_lines:
                bank_line_id = line[0]

                reconciliation_counter += 1

                reconciliation_id = (
                    f"REC-{run_id}-{reconciliation_counter:06d}"
                )

                matched_amount = max(abs(line[3]), 1)

                cursor.execute(
                    """
                    INSERT INTO reconciliation_matches (
                        reconciliation_id,
                        run_id,
                        settlement_batch_id,
                        bank_line_id,
                        matched_amount_minor,
                        match_status,
                        match_rule,
                        matched_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        reconciliation_id,
                        run_id,
                        batch_id,
                        bank_line_id,
                        matched_amount,
                        match_status,
                        "BATCH_BANK_LINE_AGGREGATION",
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )

            # Count matched settlement batches, not individual lines
            if match_status == "MATCHED":
                matched_count += 1

            else:
                create_exception(
                    reconciliation_id,
                    exception_type,
                    severity,
                    (
                        f"{match_status}: Settlement {batch_id}; "
                        f"settlement amount={settlement_amount}; "
                        f"combined bank amount={bank_total}"
                    ),
                )


            # Create a separate exception for fee validation failures
            if fee_mismatch:
                create_exception(
                    reconciliation_id,
                    "FEE_MISMATCH",
                    "HIGH",
                    (
                        f"Fee validation failed for {batch_id}; "
                        f"gross amount={gross_amount}; "
                        f"recorded fee={fee_amount}; "
                        f"expected fee={expected_fee}; "
                        f"capture line total={capture_total}; "
                        f"fee line total={fee_total}"
                    ),
                )

        
        # Find bank lines without a current or historical match
        historically_matched = {
            row[0]
            for row in cursor.execute(
                """
                SELECT DISTINCT bank_line_id
                FROM reconciliation_matches
                WHERE run_id != ?
                """,
                (run_id,),
            ).fetchall()
        }

        for line in bank_lines:
            bank_line_id = line[0]

            if (
                bank_line_id not in used_bank_lines
                and bank_line_id not in historically_matched
            ):
                unmatched_bank_count += 1

                create_exception(
                    None,
                    "UNMATCHED_BANK_LINE",
                    "HIGH",
                    f"Bank line {bank_line_id} has no matching settlement batch.",
                )

        # Update reconciliation run statistics
        completed_at = datetime.now().isoformat(timespec="microseconds")

        cursor.execute(
            """
            UPDATE reconciliation_runs
            SET
                completed_at = ?,
                run_status = 'COMPLETED',
                total_batches = ?,
                total_bank_lines = ?,
                matched_count = ?,
                exception_count = ?
            WHERE run_id = ?
            """,
            (
                completed_at,
                len(batches),
                len(bank_lines),
                matched_count,
                exception_count,
                run_id,
            ),
        )

        connection.commit()

        print("Reconciliation completed successfully!")
        print("Run ID:", run_id)
        print("Settlement batches processed:", len(batches))
        print("Bank statement lines processed:", len(bank_lines))
        print("Matched batches:", matched_count)
        print("Exceptions created:", exception_count)
        print("Unmatched bank lines:", unmatched_bank_count)

    except Exception as error:
        connection.rollback()
        print("Reconciliation failed:", error)
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    run_reconciliation()
