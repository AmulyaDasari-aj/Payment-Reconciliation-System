# System Architecture – Payment Reconciliation and Exception Management System

## 1. Overview

The Payment Reconciliation and Exception Management System is a Python-based application designed to compare payment settlement records with bank statement transactions.

The system identifies matched transactions, detects discrepancies, creates exceptions, and maintains a history of reconciliation runs and exception resolutions.

## 2. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Flask | Web application and routing |
| SQLite | Database storage |
| SQLAlchemy | Database toolkit |
| Pandas | Data processing and reporting |
| NumPy | Numerical operations |
| Faker | Synthetic test data generation |
| Bootstrap | User interface styling |
| Chart.js | Dashboard charts |
| Pytest | Automated testing |

## 3. High-Level Architecture

The application follows a layered architecture:

1. **Presentation Layer:** Flask routes and HTML templates provide the user interface.
2. **Application Layer:** Python services handle data generation, settlement processing, reconciliation, exception management, and metrics.
3. **Data Layer:** SQLite stores merchants, payments, attempts, processor events, settlements, bank statements, reconciliation records, exceptions, and resolutions.
4. **Validation and Testing Layer:** Data validation and automated tests verify data integrity and application behaviour.
5. **Export Layer:** CSV reports allow users to download payment and reconciliation information.

## 4. Main Application Modules

### Data Generation Module

- Generates synthetic merchant and payment records.
- Creates payment attempts and processor events.
- Uses a configurable random seed for reproducibility.
- Generates unique identifiers and maintains valid relationships between records.

### Settlement Generation Module

- Processes successful capture events.
- Groups transactions into settlement batches.
- Calculates gross amounts, fees, and net settlement amounts.
- Creates settlement lines for reconciliation.

### Bank Statement Generation Module

- Generates bank statement records using settlement information.
- Maintains merchant, currency, reference, and transaction details.
- Supports test scenarios involving unmatched and incorrect bank records.

### Reconciliation Module

- Compares settlement batches with bank statement lines.
- Checks merchant, currency, amount, and transaction date.
- Prevents the same bank statement line from being reused within a reconciliation run.
- Records matched and mismatched transactions.
- Creates a separate record for each reconciliation run.

### Exception Management Module

- Creates exceptions for unmatched transactions and reconciliation discrepancies.
- Supports OPEN, IN_PROGRESS, RESOLVED, and CLOSED statuses.
- Records resolution actions, notes, users, and timestamps.
- Maintains an audit history of exception status changes.

### Dashboard and Reporting Module

- Displays payment, settlement, and reconciliation summaries.
- Shows exception counts and financial information.
- Provides CSV exports for payments, settlements, bank statements, reconciliation results, and exceptions.

### Data Validation Module

- Checks duplicate identifiers.
- Verifies foreign key relationships.
- Checks settlement calculations.
- Identifies invalid payment and attempt statuses.
- Checks payment and attempt date consistency.

## 5. Database Architecture

The system uses SQLite with relational tables.

The main entities are:

- Merchants
- Payment Orders
- Payment Attempts
- Processor Events
- Settlement Batches
- Settlement Lines
- Bank Statement Lines
- Reconciliation Runs
- Reconciliation Matches
- Exceptions
- Resolutions

Primary keys uniquely identify records, while foreign keys maintain relationships between related tables.

Financial amounts are stored as integer minor units (paise for INR) to avoid floating-point calculation errors.

## 6. Reconciliation Workflow

1. Generate merchant and payment data.
2. Create payment attempts and processor events.
3. Generate settlement batches and settlement lines.
4. Generate bank statement records.
5. Run the reconciliation process.
6. Compare settlement and bank records.
7. Store matched transactions.
8. Create exceptions for discrepancies.
9. Allow operations users to investigate and resolve exceptions.
10. Generate reports and validation results.

## 7. Exception Scenarios

The system supports testing of the following scenarios:

- Settlement and bank amount mismatch.
- Currency mismatch.
- Transaction date mismatch.
- Missing bank statement record.
- Unmatched bank statement record.
- Duplicate event or settlement line detection.

## 8. Reliability and Testing

The application uses automated tests to verify:

- Database schema and relationships.
- Reconciliation run history.
- Exception and resolution history.
- Generated record counts and unique identifiers.
- Foreign key integrity.
- Data generation reproducibility.

The data generator uses a fixed random seed so that the same configuration can reproduce the same synthetic records.

## 9. Limitations and Future Improvements

- The current implementation uses SQLite and synthetic payment data.
- External payment processor and banking integrations are not included.
- Authentication and role-based access control can be added.
- The application can be extended to support larger datasets using a production database.
- Automated scheduling, notifications, and advanced fraud detection can be added in future versions.

## 10. Conclusion

The system provides an organized workflow for generating payment data, processing settlements, reconciling bank statements, identifying exceptions, and tracking resolutions. Its modular design supports testing, reporting, and future enhancements.