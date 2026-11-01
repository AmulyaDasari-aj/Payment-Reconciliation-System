# Payment Reconciliation System – Data Dictionary

## 1. Overview

This document describes the database structure of the Payment Reconciliation and Exception Management System.

The system uses SQLite to store merchant information, payment orders, payment attempts, processor events, settlement batches, bank statement records, reconciliation results, exceptions, and resolution history.

All monetary amounts are stored as integer minor units (paise for INR) to avoid floating-point calculation errors.

## 2. Database Tables

### 2.1 Merchants

Stores merchant and business information.

| Column | Description |
|---|---|
| merchant_id | Unique merchant identifier (Primary Key) |
| merchant_name | Merchant or business name |
| email | Merchant email address (Unique) |
| country | Merchant country |
| currency | Merchant currency (Default: INR) |
| status | Merchant account status (ACTIVE/INACTIVE) |
| created_at | Merchant creation timestamp |

### 2.2 Payment Orders

Stores customer payment instructions and order details.

| Column | Description |
|---|---|
| payment_id | Unique payment identifier (Primary Key) |
| merchant_id | Associated merchant (Foreign Key) |
| order_reference | Unique order reference |
| amount_minor | Payment amount in minor units |
| currency | Payment currency |
| payment_status | Current payment status |
| created_at | Payment creation timestamp |

**Allowed payment statuses:** CREATED, PENDING, AUTHORIZED, CAPTURED, FAILED, REFUNDED, CANCELLED.

### 2.3 Payment Attempts

Stores individual payment processing attempts.

| Column | Description |
|---|---|
| attempt_id | Unique attempt identifier (Primary Key) |
| payment_id | Associated payment (Foreign Key) |
| attempt_number | Attempt sequence number |
| processor_name | Payment processor |
| amount_minor | Attempt amount |
| currency | Transaction currency |
| attempt_status | Attempt processing status |
| attempted_at | Attempt timestamp |

**Allowed attempt statuses:** INITIATED, AUTHORIZED, CAPTURED, FAILED, REFUNDED.

A unique constraint prevents duplicate attempt numbers for the same payment.

### 2.4 Processor Events

Stores events received from payment processors.

| Column | Description |
|---|---|
| event_id | Unique event identifier (Primary Key) |
| attempt_id | Associated payment attempt (Foreign Key) |
| processor_event_reference | Unique processor event reference |
| event_type | Processor event type |
| amount_minor | Event amount |
| currency | Transaction currency |
| event_status | Event processing status |
| event_timestamp | Event timestamp |

**Allowed event types:** AUTHORIZATION, CAPTURE, REFUND, FAILURE.

**Allowed event statuses:** SUCCESS, FAILED, PENDING.

### 2.5 Settlement Batches

Stores payment processor settlement batch information.

| Column | Description |
|---|---|
| batch_id | Unique settlement batch identifier (Primary Key) |
| merchant_id | Associated merchant (Foreign Key) |
| processor_name | Payment processor |
| settlement_reference | Unique settlement reference |
| currency | Settlement currency |
| gross_amount_minor | Total gross settlement amount |
| fee_amount_minor | Processing fees |
| net_amount_minor | Final settlement amount |
| settlement_status | Settlement processing status |
| settlement_date | Settlement date |

**Allowed settlement statuses:** CREATED, PROCESSED, SETTLED.

Settlement calculation:

Net Amount = Gross Amount − Fee Amount.

The database checks that the gross amount is not less than the fee amount and that the net amount is calculated correctly.

### 2.6 Settlement Lines

Stores individual transaction entries within settlement batches.

| Column | Description |
|---|---|
| settlement_line_id | Unique settlement line identifier (Primary Key) |
| batch_id | Associated settlement batch (Foreign Key) |
| payment_id | Related payment (Optional Foreign Key) |
| processor_event_reference | Related processor event reference |
| line_type | Settlement entry type |
| amount_minor | Settlement line amount |
| currency | Transaction currency |
| line_reference | Unique settlement line reference |
| created_at | Settlement line creation timestamp |

**Allowed line types:** CAPTURE, REFUND, FEE, ADJUSTMENT.

### 2.7 Bank Statement Lines

Stores imported bank transaction records.

| Column | Description |
|---|---|
| bank_line_id | Unique bank line identifier (Primary Key) |
| merchant_id | Associated merchant (Foreign Key) |
| settlement_batch_id | Optional associated settlement batch (Foreign Key) |
| bank_reference | Unique bank transaction reference |
| description | Bank transaction description |
| amount_minor | Bank transaction amount |
| currency | Transaction currency |
| transaction_date | Bank transaction date |
| imported_at | Bank record import timestamp |

### 2.8 Reconciliation Runs

Stores the history and summary of reconciliation executions.

| Column | Description |
|---|---|
| run_id | Unique reconciliation run identifier (Primary Key) |
| started_at | Run start timestamp |
| completed_at | Run completion timestamp |
| run_status | Reconciliation execution status |
| total_batches | Number of settlement batches processed |
| total_bank_lines | Number of bank statement lines processed |
| matched_count | Number of matched records |
| exception_count | Number of exceptions created |

**Allowed run statuses:** RUNNING, COMPLETED, FAILED.

### 2.9 Reconciliation Matches

Stores the results of matching settlement batches with bank statement lines.

| Column | Description |
|---|---|
| reconciliation_id | Unique reconciliation identifier (Primary Key) |
| run_id | Associated reconciliation run (Foreign Key) |
| settlement_batch_id | Associated settlement batch (Foreign Key) |
| bank_line_id | Associated bank statement line (Foreign Key) |
| matched_amount_minor | Matched amount |
| match_status | Reconciliation result |
| match_rule | Rule used for matching |
| matched_at | Matching timestamp |

**Allowed match statuses:** MATCHED, PARTIAL, AMOUNT_MISMATCH, CURRENCY_MISMATCH, DATE_MISMATCH.

A unique constraint prevents the same settlement and bank line combination from being recorded more than once within a reconciliation run.

### 2.10 Exceptions

Stores unmatched and mismatched transactions that require investigation.

| Column | Description |
|---|---|
| exception_id | Unique exception identifier (Primary Key) |
| run_id | Associated reconciliation run (Foreign Key) |
| reconciliation_id | Related reconciliation record (Optional Foreign Key) |
| exception_type | Exception category |
| severity | Exception priority |
| description | Exception details |
| exception_status | Current exception status |
| created_at | Exception creation timestamp |



**Allowed exception types:** UNMATCHED_SETTLEMENT, UNMATCHED_BANK_LINE, AMOUNT_MISMATCH, CURRENCY_MISMATCH, DATE_MISMATCH, FEE_MISMATCH, DUPLICATE_EVENT, DUPLICATE_SETTLEMENT_LINE, OTHER.

**Allowed severity levels:** LOW, MEDIUM, HIGH, CRITICAL.

**Allowed exception statuses:** OPEN, IN_PROGRESS, RESOLVED, CLOSED.

### 2.11 Resolutions

Maintains the history of exception status changes and resolution actions.

| Column | Description |
|---|---|
| resolution_id | Unique resolution identifier (Primary Key) |
| exception_id | Associated exception (Foreign Key) |
| resolved_by | Person handling the exception |
| resolution_action | Action performed |
| resolution_notes | Resolution explanation |
| previous_status | Previous exception status |
| new_status | Updated exception status |
| resolved_at | Resolution timestamp |

## 3. Data Integrity and Constraints

The database uses:

- Primary keys to uniquely identify records.
- Foreign keys to maintain relationships between tables.
- Unique constraints to prevent duplicate references and reconciliation combinations within a run.
- CHECK constraints to restrict invalid statuses and monetary values.
- Integer minor units for accurate financial calculations.
- Indexes to improve search and reconciliation query performance.

## 4. Database Indexes

The following indexes support faster database operations:

- idx_orders_merchant
- idx_attempts_payment
- idx_events_attempt
- idx_settlement_merchant
- idx_settlement_lines_batch
- idx_bank_merchant
- idx_reconciliation_run
- idx_exception_run

## 5. Purpose

This data dictionary provides a technical reference for developers, operations analysts, risk and compliance reviewers, and system administrators working with the Payment Reconciliation and Exception Management System.