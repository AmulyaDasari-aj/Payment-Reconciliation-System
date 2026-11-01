from collections import defaultdict

from config import SETTLEMENT_BATCH_COUNT
from database.db import get_connection

def generate_settlements():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Remove previously generated settlement records.
        # Run this generator before creating reconciliation records.
        cursor.execute("DELETE FROM settlement_lines")
        cursor.execute("DELETE FROM settlement_batches")

        # Get all successful capture events
        capture_events = cursor.execute(
            """
            SELECT
                pe.event_id,
                pe.processor_event_reference,
                pe.amount_minor,
                pe.currency,
                pe.event_timestamp,
                pa.payment_id,
                pa.processor_name,
                po.merchant_id
            FROM processor_events pe
            JOIN payment_attempts pa
                ON pe.attempt_id = pa.attempt_id
            JOIN payment_orders po
                ON pa.payment_id = po.payment_id
            WHERE pe.event_type = 'CAPTURE'
              AND pe.event_status = 'SUCCESS'
            ORDER BY po.merchant_id, pe.event_id
            """
        ).fetchall()

        if not capture_events:
            print("No successful capture events found.")
            return

        # Group captures by merchant.
        merchant_groups = defaultdict(list)

        for event in capture_events:
            merchant_id = event[7]
            merchant_groups[merchant_id].append(event)


        # Ensure the expected number of settlement batches can be created.
        if len(merchant_groups) != SETTLEMENT_BATCH_COUNT:
            raise ValueError(
                f"Expected {SETTLEMENT_BATCH_COUNT} settlement batches, "
                f"but found {len(merchant_groups)} merchant groups."
            )

        batch_counter = 0

        # Create one settlement batch per merchant.
        for merchant_id, events in sorted(merchant_groups.items()):

            batch_counter += 1
            batch_id = f"SET-2026-{batch_counter:06d}"
            batch_line_counter = 0

            processor_names = {event[6] for event in events}
            currencies = {event[3] for event in events}

            if len(processor_names) != 1:
                raise ValueError(
                    f"Multiple processors found for merchant {merchant_id}"
                )

            if len(currencies) != 1:
                raise ValueError(
                    f"Multiple currencies found for merchant {merchant_id}"
                )

            processor_name = next(iter(processor_names))
            currency = next(iter(currencies))

            gross_amount = sum(event[2] for event in events)

            # Processor fee: 2% of gross amount.
            fee_amount = (gross_amount * 2 + 50) // 100

            net_amount = gross_amount - fee_amount

            settlement_date = max(
                event[4][:10] for event in events
            )

            settlement_reference = (
                f"SETTLEMENT-2026-{batch_counter:06d}"
            )

            cursor.execute(
                """
                INSERT INTO settlement_batches (
                    batch_id,
                    merchant_id,
                    processor_name,
                    settlement_reference,
                    currency,
                    gross_amount_minor,
                    fee_amount_minor,
                    net_amount_minor,
                    settlement_status,
                    settlement_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    merchant_id,
                    processor_name,
                    settlement_reference,
                    currency,
                    gross_amount,
                    fee_amount,
                    net_amount,
                    "SETTLED",
                    settlement_date,
                ),
            )

            # Create a settlement line for each capture.
            for event in events:
                
                batch_line_counter += 1

                (
                    event_id,
                    event_reference,
                    amount,
                    event_currency,
                    event_timestamp,
                    payment_id,
                    event_processor,
                    event_merchant,
                ) = event

                line_id = f"STL-{batch_id}-{batch_line_counter:04d}"

                cursor.execute(
                    """
                    INSERT INTO settlement_lines (
                        settlement_line_id,
                        batch_id,
                        payment_id,
                        processor_event_reference,
                        line_type,
                        amount_minor,
                        currency,
                        line_reference,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        line_id,
                        batch_id,
                        payment_id,
                        event_reference,
                        "CAPTURE",
                        amount,
                        event_currency,
                        f"LINE-CAP-{event_id}",
                        event_timestamp,
                    ),
                )

            # Create one fee line for the batch.
            batch_line_counter += 1

            cursor.execute(
                """
                INSERT INTO settlement_lines (
                    settlement_line_id,
                    batch_id,
                    payment_id,
                    processor_event_reference,
                    line_type,
                    amount_minor,
                    currency,
                    line_reference,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"STL-{batch_id}-{batch_line_counter:04d}",
                    batch_id,
                    None,
                    None,
                    "FEE",
                    -fee_amount,
                    currency,
                    f"LINE-FEE-{batch_id}",
                    settlement_date,
                ),
            )

        connection.commit()

        batch_count = cursor.execute(
            "SELECT COUNT(*) FROM settlement_batches"
        ).fetchone()[0]

        line_count = cursor.execute(
            "SELECT COUNT(*) FROM settlement_lines"
        ).fetchone()[0]

        print("Settlement generation successful!")
        print("Settlement batches:", batch_count)
        print("Settlement lines:", line_count)

    except Exception as error:
        connection.rollback()
        print("Settlement generation failed:", error)
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    generate_settlements()
