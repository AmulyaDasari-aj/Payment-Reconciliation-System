
import random
from datetime import datetime, timedelta
from app.services.event_validator import validate_refund_event
from faker import Faker

from config import (
    RANDOM_SEED,
    MERCHANT_COUNT,
    PAYMENT_COUNT,
    ATTEMPT_COUNT,
    SETTLEMENT_BATCH_COUNT,
    CURRENCY,
)
from database.db import get_connection


def generate_sample_data():
    if MERCHANT_COUNT < SETTLEMENT_BATCH_COUNT:
        raise ValueError(
            "MERCHANT_COUNT must be greater than or equal to "
            "SETTLEMENT_BATCH_COUNT."
        )

    if PAYMENT_COUNT < SETTLEMENT_BATCH_COUNT:
        raise ValueError(
            "PAYMENT_COUNT must be greater than or equal to "
            "SETTLEMENT_BATCH_COUNT."
        )


    retry_count = ATTEMPT_COUNT - PAYMENT_COUNT

    if retry_count < 0 or retry_count > PAYMENT_COUNT:
        raise ValueError(
            "ATTEMPT_COUNT must be between PAYMENT_COUNT "
            "and twice PAYMENT_COUNT."
        )

    
    # Fixed seed for reproducible data
    random.seed(RANDOM_SEED)

    Faker.seed(RANDOM_SEED)
    fake = Faker("en_IN")
    fake.seed_instance(RANDOM_SEED)

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Clear old records in child-first order
        cursor.execute("DELETE FROM resolutions")
        cursor.execute("DELETE FROM exceptions")
        cursor.execute("DELETE FROM reconciliation_matches")
        cursor.execute("DELETE FROM bank_statement_lines")
        cursor.execute("DELETE FROM settlement_lines")
        cursor.execute("DELETE FROM settlement_batches")
        cursor.execute("DELETE FROM processor_events")
        cursor.execute("DELETE FROM payment_attempts")
        cursor.execute("DELETE FROM payment_orders")
        cursor.execute("DELETE FROM merchants")

        print("Old records cleared successfully!")

        # --------------------------------
        # 1. Generate merchants
        # --------------------------------

        merchants = []

        for i in range(1, MERCHANT_COUNT + 1):
            merchant_id = f"MER-{i:06d}"
            merchant_name = fake.company()
            email = f"merchant{i}@example.com"

            merchants.append(merchant_id)

            cursor.execute(
                """
                INSERT INTO merchants (
                    merchant_id,
                    merchant_name,
                    email,
                    country,
                    currency,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    merchant_id,
                    merchant_name,
                    email,
                    "India",
                    CURRENCY,
                    "ACTIVE",
                    "2026-01-01 00:00:00",
                ),
            )

        # --------------------------------
        # 2. Generate payment orders
        # --------------------------------

        payment_ids = []
        order_statuses = []

        for i in range(1, PAYMENT_COUNT + 1):
            payment_id = f"PAY-2026-{i:08d}"
            
            merchant_id = merchants[(i - 1) % SETTLEMENT_BATCH_COUNT]

            amount_minor = random.randint(10000, 500000)
            order_reference = f"ORD-2026-{i:08d}"

            # The final ten orders will have a retry.
            # Their first attempt will fail and their second will capture.
            

            if i <= SETTLEMENT_BATCH_COUNT:
                payment_status = "CAPTURED"
            
            elif i > PAYMENT_COUNT - retry_count:
                payment_status = "CAPTURED"
            else:
                payment_status = random.choice(
                    ["CAPTURED", "FAILED", "AUTHORIZED"]
                )

            created_at = (
                datetime(2026, 1, 1)
                + timedelta(
                    days=random.randint(0, 90),
                    minutes=random.randint(0, 1440),
                )
            ).isoformat(timespec="seconds")

            cursor.execute(
                """
                INSERT INTO payment_orders (
                    payment_id,
                    merchant_id,
                    order_reference,
                    amount_minor,
                    currency,
                    payment_status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payment_id,
                    merchant_id,
                    order_reference,
                    amount_minor,
                    CURRENCY,
                    payment_status,
                    created_at,
                ),
            )

            payment_ids.append(payment_id)
            order_statuses.append(payment_status)

        

        
        # --------------------------------
        # 3. Generate payment attempts
        # --------------------------------

        attempt_counter = 0
        event_counter = 0

        for index, payment_id in enumerate(payment_ids, start=1):
            order_status = order_statuses[index - 1]

            
            if index > PAYMENT_COUNT - retry_count:
                attempt_statuses = ["FAILED", "CAPTURED"]
            else:
                attempt_statuses = [order_status]

            order_row = cursor.execute(
                """
                SELECT amount_minor, created_at, merchant_id
                FROM payment_orders
                WHERE payment_id = ?
                """,
                (payment_id,),
            ).fetchone()

            amount_minor = order_row[0]
            order_created_at = datetime.fromisoformat(order_row[1])

            merchant_id = order_row[2]

            previous_attempt_datetime = order_created_at

            for attempt_number, attempt_status in enumerate(
                attempt_statuses, start=1
            ):
                if attempt_counter >= ATTEMPT_COUNT:
                    break

                attempt_counter += 1

                attempt_id = f"ATT-{payment_id}-{attempt_number:02d}"

                

                processor_name = f"PROCESSOR-{(int(merchant_id.split('-')[1]) % 3) + 1}"

                if attempt_number == 1:
                    attempt_datetime = previous_attempt_datetime + timedelta(
                        minutes=random.randint(1, 1440)
                    )
                else:
                    attempt_datetime = previous_attempt_datetime + timedelta(
                        minutes=random.randint(5, 60)
                    )

                previous_attempt_datetime = attempt_datetime

                attempted_at = attempt_datetime.isoformat(
                    timespec="seconds"
                )

                cursor.execute(
                    """
                    INSERT INTO payment_attempts (
                        attempt_id, payment_id, attempt_number,
                        processor_name, amount_minor, currency,
                        attempt_status, attempted_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        attempt_id,
                        payment_id,
                        attempt_number,
                        processor_name,
                        amount_minor,
                        CURRENCY,
                        attempt_status,
                        attempted_at,
                    ),
                )

                # Generate processor events
                event_counter += 1
                event_id = f"EVT-2026-{event_counter:08d}"

                if attempt_status == "CAPTURED":
                    event_type = "CAPTURE"
                    event_status = "SUCCESS"
                elif attempt_status == "FAILED":
                    event_type = "FAILURE"
                    event_status = "FAILED"
                else:
                    event_type = "AUTHORIZATION"
                    event_status = "SUCCESS"

                event_reference = f"PROC-EVT-{event_counter:08d}"



                if event_type == "REFUND":
                    is_valid, message = validate_refund_event(
                        connection,
                        attempt_id,
                        amount_minor,
                        CURRENCY,
                        attempted_at,
                    )

                    if not is_valid:
                        raise ValueError(message)


                cursor.execute(
                    """
                    INSERT INTO processor_events (
                        event_id, attempt_id,
                        processor_event_reference, event_type,
                        amount_minor, currency, event_status,
                        event_timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        attempt_id,
                        event_reference,
                        event_type,
                        amount_minor,
                        CURRENCY,
                        event_status,
                        attempted_at,
                    ),
                )

        if attempt_counter != ATTEMPT_COUNT:
            raise ValueError(
                f"Expected {ATTEMPT_COUNT} attempts, "
                f"but generated {attempt_counter}."
            )
        connection.commit()

        # --------------------------------
        # 5. Display generation summary
        # --------------------------------

        print("Sample data generated successfully!")

        tables = [
            "merchants",
            "payment_orders",
            "payment_attempts",
            "processor_events",
        ]

        print("\nGenerated record counts:")

        for table in tables:
            count = cursor.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table}: {count}")

    except Exception as error:
        connection.rollback()
        print("Data generation failed:", error)
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    generate_sample_data()
