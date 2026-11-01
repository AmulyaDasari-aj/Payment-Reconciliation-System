# Assumptions and Design Decisions

## 1. Project Assumptions

1. The system uses synthetic payment and bank statement data for development and testing.
2. All financial amounts are stored in integer minor units (paise for INR).
3. INR is the default currency for generated sample transactions.
4. Each payment order belongs to one merchant.
5. A payment order can have multiple payment attempts.
6. Only successful capture events are included as capture entries in settlement processing.
7. Settlement batches contain transaction entries and applicable fee entries.
8. Bank statement records represent amounts credited or debited by the bank.
9. A settlement batch is compared with bank statement records belonging to the same merchant.
10. Reconciliation uses transaction references, amounts, currencies, and dates to identify possible matches.

## 2. Design Decisions

### Database

- SQLite is used for simple local development and testing.
- Primary keys provide unique record identification.
- Foreign keys maintain relationships between related records.
- Database constraints help prevent invalid data.
- Integer minor units are used for accurate financial calculations.

### Data Generation

- A fixed random seed is used to support reproducible data generation.
- Record counts are configurable through the project configuration.
- Parent records are generated before their dependent child records.
- Deterministic identifiers make generated records easier to trace.

### Settlement Processing

- Successful capture events are used to calculate gross settlement amounts.
- Fees are calculated and deducted to obtain net settlement amounts.
- Settlement lines maintain details of individual settlement entries.

### Reconciliation

- Each reconciliation execution receives a unique run ID.
- A bank statement line cannot be reused within the same reconciliation run.
- Records are classified using match statuses such as MATCHED, PARTIAL, AMOUNT_MISMATCH, CURRENCY_MISMATCH, and DATE_MISMATCH.
- Transactions that cannot be matched are recorded as exceptions instead of being silently discarded.

### Exception Management

- Exceptions follow a controlled status workflow: OPEN, IN_PROGRESS, RESOLVED, and CLOSED.
- A resolution record stores the previous status, new status, action, notes, user, and timestamp.
- Resolved exceptions must be reviewed before they can be closed.

## 3. Reconciliation Rules

1. Merchant identity must be considered when comparing settlement and bank records.
2. Currency differences are classified as currency mismatches.
3. Amount differences are classified as amount mismatches.
4. Transaction dates more than three days apart are classified as date mismatches.
5. A bank statement line can be assigned to only one settlement batch in a reconciliation run.
6. Unmatched settlement batches and unmatched bank statement lines create separate exceptions.

## 4. Test Data Scenarios

The project includes synthetic scenarios to verify:

- Correctly matched settlement and bank records.
- Settlement amount differences.
- Currency differences.
- Transaction date differences.
- Missing bank statement records.
- Additional unmatched bank statement records.
- Duplicate processor event and settlement line handling.

## 5. Limitations

1. The current system uses synthetic data rather than live banking information.
2. External payment processor integrations are not implemented.
3. The current application uses SQLite and is intended for a development or demonstration environment.
4. Authentication and role-based permissions require further implementation.
5. Matching rules are rule-based and may require improvements for complex real-world transactions.
6. The current fee calculation is a simplified assumption for demonstration purposes.

## 6. Future Improvements

- Integrate real payment processor APIs.
- Import bank statements from CSV and other supported formats.
- Add authentication and role-based access control.
- Improve matching using configurable rules and confidence scores.
- Add notifications for critical exceptions.
- Support production databases and larger transaction volumes.
- Add more comprehensive audit logging and monitoring.

## 7. Conclusion

These assumptions and design decisions define the current scope and behaviour of the Payment Reconciliation and Exception Management System. They provide a clear basis for understanding the implementation, testing the application, and planning future improvements.