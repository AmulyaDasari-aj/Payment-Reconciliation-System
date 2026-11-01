
PRAGMA foreign_keys = ON;

-- 1. Merchants
CREATE TABLE IF NOT EXISTS merchants (
    merchant_id TEXT PRIMARY KEY,
    merchant_name TEXT NOT NULL,
    email TEXT UNIQUE,
    country TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Payment orders
CREATE TABLE IF NOT EXISTS payment_orders (
    payment_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    order_reference TEXT NOT NULL UNIQUE,
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    currency TEXT NOT NULL,
    payment_status TEXT NOT NULL
        CHECK (payment_status IN (
            'CREATED', 'PENDING', 'AUTHORIZED',
            'CAPTURED', 'FAILED', 'REFUNDED', 'CANCELLED'
        )),
    created_at TEXT NOT NULL,
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);

-- 3. Payment attempts
CREATE TABLE IF NOT EXISTS payment_attempts (
    attempt_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    processor_name TEXT NOT NULL,
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    currency TEXT NOT NULL,
    attempt_status TEXT NOT NULL
        CHECK (attempt_status IN (
            'INITIATED', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'REFUNDED'
        )),
    attempted_at TEXT NOT NULL,
    UNIQUE (payment_id, attempt_number),
    FOREIGN KEY (payment_id) REFERENCES payment_orders(payment_id)
);

-- 4. Processor events
CREATE TABLE IF NOT EXISTS processor_events (
    event_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    processor_event_reference TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'AUTHORIZATION', 'CAPTURE', 'REFUND', 'FAILURE'
        )),
    amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
    currency TEXT NOT NULL,
    event_status TEXT NOT NULL
        CHECK (event_status IN ('SUCCESS', 'FAILED', 'PENDING')),
    event_timestamp TEXT NOT NULL,
    FOREIGN KEY (attempt_id) REFERENCES payment_attempts(attempt_id)
);

-- 5. Settlement batches
CREATE TABLE IF NOT EXISTS settlement_batches (
    batch_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    processor_name TEXT NOT NULL,
    settlement_reference TEXT NOT NULL UNIQUE,
    currency TEXT NOT NULL,
    gross_amount_minor INTEGER NOT NULL CHECK (gross_amount_minor >= 0),
    fee_amount_minor INTEGER NOT NULL CHECK (fee_amount_minor >= 0),
    net_amount_minor INTEGER NOT NULL CHECK (net_amount_minor >= 0),
    settlement_status TEXT NOT NULL
        CHECK (settlement_status IN ('CREATED', 'PROCESSED', 'SETTLED')),
    settlement_date TEXT NOT NULL,
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id),
    CHECK (gross_amount_minor >= fee_amount_minor),
    CHECK (net_amount_minor = gross_amount_minor - fee_amount_minor)
);

-- 6. Settlement lines
CREATE TABLE IF NOT EXISTS settlement_lines (
    settlement_line_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    payment_id TEXT,
    processor_event_reference TEXT,
    line_type TEXT NOT NULL
        CHECK (line_type IN ('CAPTURE', 'REFUND', 'FEE', 'ADJUSTMENT')),
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL,
    line_reference TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (batch_id) REFERENCES settlement_batches(batch_id),
    FOREIGN KEY (payment_id) REFERENCES payment_orders(payment_id)
);

-- 7. Bank statement lines
CREATE TABLE IF NOT EXISTS bank_statement_lines (
    bank_line_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    settlement_batch_id TEXT,
    bank_reference TEXT NOT NULL UNIQUE,
    description TEXT,
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id),
    FOREIGN KEY (settlement_batch_id) REFERENCES settlement_batches(batch_id)
);


-- 8. Reconciliation runs
CREATE TABLE IF NOT EXISTS reconciliation_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    run_status TEXT NOT NULL
        CHECK (run_status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    total_batches INTEGER NOT NULL DEFAULT 0,
    total_bank_lines INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0,
    exception_count INTEGER NOT NULL DEFAULT 0
);


-- 9. Reconciliation matches
CREATE TABLE IF NOT EXISTS reconciliation_matches (
    reconciliation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    settlement_batch_id TEXT NOT NULL,
    bank_line_id TEXT NOT NULL,
    matched_amount_minor INTEGER NOT NULL
        CHECK (matched_amount_minor > 0),
    match_status TEXT NOT NULL
        CHECK (match_status IN (
            'MATCHED',
            'PARTIAL',
            'AMOUNT_MISMATCH',
            'CURRENCY_MISMATCH',
            'DATE_MISMATCH'
        )),
    match_rule TEXT,
    matched_at TEXT NOT NULL,

    UNIQUE (run_id, settlement_batch_id, bank_line_id),

    FOREIGN KEY (run_id)
        REFERENCES reconciliation_runs(run_id),

    FOREIGN KEY (settlement_batch_id)
        REFERENCES settlement_batches(batch_id),

    FOREIGN KEY (bank_line_id)
        REFERENCES bank_statement_lines(bank_line_id)
);


-- 10. Exceptions
CREATE TABLE IF NOT EXISTS exceptions (
    exception_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    reconciliation_id TEXT,
    exception_type TEXT NOT NULL
        CHECK (exception_type IN (
            'UNMATCHED_SETTLEMENT', 'UNMATCHED_BANK_LINE',
            'AMOUNT_MISMATCH', 'CURRENCY_MISMATCH',
            'DATE_MISMATCH', 'FEE_MISMATCH', 'DUPLICATE_EVENT',
            'DUPLICATE_SETTLEMENT_LINE', 'OTHER'
        )),
    severity TEXT NOT NULL
        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    description TEXT NOT NULL,
    exception_status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (exception_status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')),
    created_at TEXT NOT NULL,

    FOREIGN KEY (run_id)
        REFERENCES reconciliation_runs(run_id),

    FOREIGN KEY (reconciliation_id)
        REFERENCES reconciliation_matches(reconciliation_id)
);


-- 10. Exception resolutions
CREATE TABLE IF NOT EXISTS resolutions (
    resolution_id TEXT PRIMARY KEY,
    exception_id TEXT NOT NULL,
    resolved_by TEXT NOT NULL,
    resolution_action TEXT NOT NULL,
    resolution_notes TEXT,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    FOREIGN KEY (exception_id) REFERENCES exceptions(exception_id)
);

-- Indexes for faster searches and reconciliation
CREATE INDEX IF NOT EXISTS idx_orders_merchant
    ON payment_orders(merchant_id);

CREATE INDEX IF NOT EXISTS idx_attempts_payment
    ON payment_attempts(payment_id);

CREATE INDEX IF NOT EXISTS idx_events_attempt
    ON processor_events(attempt_id);

CREATE INDEX IF NOT EXISTS idx_settlement_merchant
    ON settlement_batches(merchant_id);

CREATE INDEX IF NOT EXISTS idx_settlement_lines_batch
    ON settlement_lines(batch_id);

CREATE INDEX IF NOT EXISTS idx_bank_merchant
    ON bank_statement_lines(merchant_id);

CREATE INDEX IF NOT EXISTS idx_reconciliation_run
    ON reconciliation_matches(run_id);

CREATE INDEX IF NOT EXISTS idx_exception_run
    ON exceptions(run_id);


