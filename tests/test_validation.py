
from app.services.data_validator import validate_database


def test_database_validation():
    results = validate_database()

    # Check duplicate IDs
    duplicate_keys = [
        key for key in results if key.endswith("_duplicate_ids")
    ]

    for key in duplicate_keys:
        assert results[key] == 0, f"Duplicate IDs found: {key}"

    # Check settlement calculations
    assert results["incorrect_settlements"] == 0

    # Check missing references
    assert results["missing_merchants"] == 0
    assert results["missing_bank_lines"] == 0

    # Check foreign keys
    foreign_key_keys = [
        key for key in results if key.endswith("_foreign_key_errors")
    ]

    for key in foreign_key_keys:
        assert results[key] == 0, f"Foreign key errors: {key}"

    # Check statuses and dates
    assert results["invalid_payments"] == 0
    assert results["invalid_attempts"] == 0
    assert results["invalid_attempt_dates"] == 0
