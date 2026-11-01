
from database.db import get_connection


def generate_bank_statements():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Read settled batches
        batches = cursor.execute(
            """
            SELECT
                batch_id,
                merchant_id,
                settlement_reference,
                net_amount_minor,
                currency,
                settlement_date
            FROM settlement_batches
            WHERE settlement_status = 'SETTLED'
            ORDER BY batch_id
            """
        ).fetchall()

        bank_counter = 0
        created_count = 0
        skipped_count = 0

        for batch in batches:
            (
                batch_id,
                merchant_id,
                settlement_reference,
                net_amount,
                currency,
                settlement_date,
            ) = batch

            bank_counter += 1

            # Split the net settlement amount into 5 parts
            base_amount, remainder = divmod(net_amount, 5)

            for line_number in range(1, 6):

                bank_line_id = (
                    f"BANK-SPLIT-2026-{bank_counter:06d}-{line_number:02d}"
                )

                bank_reference = (
                    f"BANK-SPLIT-REF-{bank_counter:06d}-{line_number:02d}"
                )

                # Avoid duplicate records when running again
                existing_record = cursor.execute(
                    """
                    SELECT bank_line_id
                    FROM bank_statement_lines
                    WHERE bank_line_id = ?
                    """,
                    (bank_line_id,),
                ).fetchone()

                if existing_record:
                    skipped_count += 1
                    continue

                # Distribute the remainder without losing any paise
                amount = base_amount

                if line_number <= remainder:
                    amount += 1

                description = (
                    f"Settlement part {line_number}/5 for "
                    f"{settlement_reference}"
                )

                cursor.execute(
                    """
                    INSERT INTO bank_statement_lines (
                        bank_line_id,
                        merchant_id,
                        settlement_batch_id,
                        bank_reference,
                        description,
                        amount_minor,
                        currency,
                        transaction_date
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bank_line_id,
                        merchant_id,
                        batch_id,
                        bank_reference,
                        description,
                        amount,
                        currency,
                        settlement_date,
                    ),
                )

                created_count += 1



                # Validate that bank lines equal each batch's net amount.
        for batch_id, net_amount in cursor.execute(
            """
            SELECT batch_id, net_amount_minor
            FROM settlement_batches
            WHERE settlement_status = 'SETTLED'
            """
        ).fetchall():

            bank_total = cursor.execute(
                """
                SELECT COALESCE(SUM(amount_minor), 0)
                FROM bank_statement_lines
                WHERE settlement_batch_id = ?
                """,
                (batch_id,),
            ).fetchone()[0]

            if bank_total != net_amount:
                raise ValueError(
                    f"Bank amount mismatch for {batch_id}: "
                    f"expected {net_amount}, found {bank_total}"
                )
        connection.commit()

        count = cursor.execute(
            "SELECT COUNT(*) FROM bank_statement_lines"
        ).fetchone()[0]

        total_amount = cursor.execute(
            "SELECT SUM(amount_minor) FROM bank_statement_lines"
        ).fetchone()[0]

        print("Bank statement generation successful!")
        print("New bank lines created:", created_count)
        print("Existing lines skipped:", skipped_count)
        print("Total bank statement lines:", count)
        print("Total bank amount:", total_amount)

    except Exception as error:
        connection.rollback()
        print("Bank statement generation failed:", error)
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    generate_bank_statements()
