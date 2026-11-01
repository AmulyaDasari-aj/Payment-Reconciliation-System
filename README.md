# Payment Reconciliation and Exception Management System

## Project Overview

The Payment Reconciliation and Exception Management System is a Python-based application designed to automate the reconciliation of payment records, processor events, settlement batches, and bank statement transactions.

The system identifies matching transactions, detects discrepancies, generates exceptions, and supports exception resolution with an audit history.

## Key Features

- Automated payment data generation.
- Settlement batch generation with fee calculations.
- Bank statement generation.
- Transaction reconciliation.
- Detection of amount, currency, and date mismatches.
- Identification of unmatched settlements and bank transactions.
- Exception management and resolution tracking.
- Database validation and reproducible test data.

## Installation and Setup

### 1. Clone the Repository

```bash
git clone <your-github-repository-url>
cd Payment_recognition_system


## Running the Project

### Run the Flask Application

```bash
python run.py


## Project Configuration

The project uses a fixed random seed to generate reproducible sample data.

| Configuration | Value |
|---|---:|
| Random Seed | 20261022 |
| Merchants | 2,000 |
| Payment Orders | 50,000 |
| Payment Attempts | 55,000 |
| Settlement Batches | 1,000 |
| Bank Statement Lines | 5,000 |
| Currency | INR |

## Technology Stack

- Python
- Flask
- SQLite
- SQLAlchemy
- Pandas
- NumPy
- Faker
- Pytest


## Assumptions and Limitations

### Assumptions
- All monetary amounts are stored in minor units (paise).
- The default transaction currency is INR.
- Settlement fees are calculated at 2% of the gross settlement amount.
- Bank statement amounts are generated from settlement net amounts.
- A fixed random seed ensures reproducible test data.

### Limitations
- The project uses generated sample data rather than live payment gateway or bank integrations.
- Reconciliation currently uses deterministic matching rules.
- The application is intended as a prototype and may require additional security and scalability improvements for production use.