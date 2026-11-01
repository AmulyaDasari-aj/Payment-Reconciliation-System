
def validate_refund_event(connection, attempt_id, refund_amount, currency, refund_timestamp):
    """
    Validate that a refund has a successful capture before it.
    """

    capture = connection.execute("""
        SELECT amount_minor, currency, event_timestamp
        FROM processor_events
        WHERE attempt_id = ?
          AND event_type = 'CAPTURE'
          AND event_status = 'SUCCESS'
          AND event_timestamp < ?
        ORDER BY event_timestamp
        LIMIT 1
    """, (attempt_id, refund_timestamp)).fetchone()

    if capture is None:
        return False, "Refund cannot occur before a successful capture."

    if capture[1] != currency:
        return False, "Refund currency does not match capture currency."


    previous_refunds = connection.execute("""
    SELECT COALESCE(SUM(amount_minor), 0)
    FROM processor_events
    WHERE attempt_id = ?
      AND event_type = 'REFUND'
      AND event_status = 'SUCCESS'
""", (attempt_id,)).fetchone()[0]

    if previous_refunds + refund_amount > capture[0]:
        return False, "Total refunds cannot exceed captured amount."

    
    if refund_amount <= 0:
        return False, "Refund amount must be greater than zero."

    return True, "Refund event is valid."
