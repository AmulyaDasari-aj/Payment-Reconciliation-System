
import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, Response
import csv
import io
from database.db import get_connection

from flask import request, redirect, url_for
from datetime import datetime

main = Blueprint("main", __name__)


@main.route("/")
def dashboard():
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        merchants = connection.execute(
            "SELECT COUNT(*) FROM merchants"
        ).fetchone()[0]

        payments = connection.execute(
            "SELECT COUNT(*) FROM payment_orders"
        ).fetchone()[0]

        settlements = connection.execute(
            "SELECT COUNT(*) FROM settlement_batches"
        ).fetchone()[0]

        bank_lines = connection.execute(
            "SELECT COUNT(*) FROM bank_statement_lines"
        ).fetchone()[0]


        matched = connection.execute(
            """
            SELECT COUNT(DISTINCT bank_line_id)
            FROM reconciliation_matches
            WHERE match_status = 'MATCHED'
            """
        ).fetchone()[0]


        open_exceptions = connection.execute(
            """
            SELECT COUNT(*)
            FROM exceptions
            WHERE exception_status = 'OPEN'
            """
        ).fetchone()[0]

        recent_exceptions = connection.execute(
            """
            SELECT exception_id, exception_type,
                   severity, description, exception_status
            FROM exceptions
            ORDER BY created_at DESC
            LIMIT 5
            """
        ).fetchall()


        match_rate = (
            round((matched / bank_lines) * 100, 2)
            if bank_lines else 0
        )

        return render_template(
            "dashboard.html",
            merchants=merchants,
            payments=payments,
            settlements=settlements,
            bank_lines=bank_lines,
            matched=matched,
            open_exceptions=open_exceptions,
            match_rate=match_rate,
            recent_exceptions=recent_exceptions
        )

    finally:
        connection.close()


@main.route("/merchants")
def merchants_page():
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        merchant_list = connection.execute(
            """
            SELECT
                m.merchant_id,
                m.merchant_name,
                m.email,
                m.country,
                m.currency,
                m.status,
                m.created_at,
                COUNT(DISTINCT p.payment_id) AS payment_count,
                COUNT(DISTINCT s.batch_id) AS settlement_count
            FROM merchants m
            LEFT JOIN payment_orders p
                ON m.merchant_id = p.merchant_id
            LEFT JOIN settlement_batches s
                ON m.merchant_id = s.merchant_id
            GROUP BY m.merchant_id
            ORDER BY m.created_at DESC
            """
        ).fetchall()

        return render_template(
            "merchants.html",
            merchants=merchant_list
        )

    finally:
        connection.close()


@main.route("/health")
def health():
    return {
        "status": "success",
        "message": "Payment Reconciliation System is running"
    }



@main.route("/payments")
def payments_page():
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        payment_list = connection.execute(
            """
            SELECT
                p.payment_id,
                p.order_reference,
                m.merchant_name,
                p.amount_minor,
                p.currency,
                p.payment_status,
                p.created_at,
                COUNT(DISTINCT a.attempt_id) AS attempt_count
            FROM payment_orders p
            JOIN merchants m
                ON p.merchant_id = m.merchant_id
            LEFT JOIN payment_attempts a
                ON p.payment_id = a.payment_id
            GROUP BY p.payment_id
            ORDER BY p.created_at DESC
            """
        ).fetchall()

        return render_template(
            "payments.html",
            payments=payment_list
        )

    finally:
        connection.close()



@main.route("/settlements")
def settlements_page():
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        settlement_list = connection.execute(
            """
            SELECT
                s.batch_id,
                s.settlement_reference,
                m.merchant_name,
                s.processor_name,
                s.currency,
                s.gross_amount_minor,
                s.fee_amount_minor,
                s.net_amount_minor,
                s.settlement_status,
                s.settlement_date
            FROM settlement_batches s
            JOIN merchants m
                ON s.merchant_id = m.merchant_id
            ORDER BY s.settlement_date DESC
            """
        ).fetchall()

        return render_template(
            "settlements.html",
            settlements=settlement_list
        )

    finally:
        connection.close()



@main.route("/bank-statements")
def bank_statements_page():
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        bank_records = connection.execute("""
            SELECT
                b.bank_line_id,
                b.bank_reference,
                b.description,
                m.merchant_name,
                b.amount_minor,
                b.currency,
                b.transaction_date,
                b.imported_at
            FROM bank_statement_lines b
            JOIN merchants m
                ON b.merchant_id = m.merchant_id
            ORDER BY b.transaction_date DESC
        """).fetchall()

        return render_template(
            "bank_statements.html",
            bank_records=bank_records
        )

    finally:
        connection.close()



@main.route("/reconciliation")
def reconciliation_page():
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        reconciliation_records = connection.execute("""
            SELECT
                r.reconciliation_id,
                r.settlement_batch_id,
                r.bank_line_id,
                r.matched_amount_minor,
                r.match_status,
                r.match_rule,
                r.matched_at,
                s.net_amount_minor,
                s.currency AS settlement_currency,
                s.settlement_date,
                b.amount_minor AS bank_amount_minor,
                b.currency AS bank_currency,
                b.transaction_date
            FROM reconciliation_matches r
            JOIN settlement_batches s
                ON r.settlement_batch_id = s.batch_id
            JOIN bank_statement_lines b
                ON r.bank_line_id = b.bank_line_id
            ORDER BY r.matched_at DESC
        """).fetchall()

        return render_template(
            "reconciliation.html",
            reconciliation_records=reconciliation_records
        )

    finally:
        connection.close()



@main.route("/exceptions", methods=["GET", "POST"])
def exceptions_page():
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        if request.method == "POST":
            exception_id = request.form.get("exception_id")
            new_status = request.form.get("new_status")
            resolved_by = request.form.get("resolved_by", "").strip()
            notes = request.form.get("notes", "").strip()
            if not notes:
                return "Please enter the resolution notes.", 400

            allowed_statuses = [
                "OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"
            ]

            if new_status not in allowed_statuses:
                return "Invalid exception status", 400

            exception = connection.execute("""
                SELECT exception_status
                FROM exceptions
                WHERE exception_id = ?
            """, (exception_id,)).fetchone()

            if exception is None:
                return "Exception not found", 404

            previous_status = exception["exception_status"]

            if previous_status in ("RESOLVED", "CLOSED"):
                return "This exception is already finalized", 400

            if new_status == "CLOSED" and previous_status != "RESOLVED":
                return "Resolve the exception before closing it", 400

            if new_status == previous_status:
                return redirect(url_for("main.exceptions_page"))

            resolved_at = datetime.now().isoformat(timespec="seconds")
            resolution_id = (
                "RES-" + datetime.now().strftime("%Y%m%d%H%M%S%f")
            )

            connection.execute("""
                UPDATE exceptions
                SET exception_status = ?
                WHERE exception_id = ?
            """, (new_status, exception_id))

            connection.execute("""
                INSERT INTO resolutions (
                    resolution_id,
                    exception_id,
                    resolved_by,
                    resolution_action,
                    resolution_notes,
                    previous_status,
                    new_status,
                    resolved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                resolution_id,
                exception_id,
                resolved_by or "Operations Analyst",
                "STATUS_CHANGED_TO_" + new_status,
                notes,
                previous_status,
                new_status,
                resolved_at
            ))

            connection.commit()
            return redirect(url_for("main.exceptions_page"))

        exception_records = connection.execute("""
            SELECT
                exception_id,
                reconciliation_id,
                exception_type,
                severity,
                description,
                exception_status,
                created_at
            FROM exceptions
            ORDER BY created_at DESC
        """).fetchall()

        return render_template(
            "exceptions.html",
            exception_records=exception_records
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



@main.route("/reports")
def reports_page():
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        payment_summary = connection.execute("""
            SELECT payment_status, COUNT(*) AS total
            FROM payment_orders
            GROUP BY payment_status
        """).fetchall()

        reconciliation_summary = connection.execute("""
            SELECT match_status, COUNT(*) AS total
            FROM reconciliation_matches
            GROUP BY match_status
        """).fetchall()

        exception_summary = connection.execute("""
            SELECT exception_type, COUNT(*) AS total
            FROM exceptions
            GROUP BY exception_type
        """).fetchall()

        financial_summary = connection.execute("""
            SELECT
                COALESCE(SUM(gross_amount_minor), 0) AS gross,
                COALESCE(SUM(fee_amount_minor), 0) AS fees,
                COALESCE(SUM(net_amount_minor), 0) AS net
            FROM settlement_batches
        """).fetchone()

        total_payments = connection.execute(
            "SELECT COUNT(*) FROM payment_orders"
        ).fetchone()[0]

        total_exceptions = connection.execute(
            "SELECT COUNT(*) FROM exceptions"
        ).fetchone()[0]

        open_exceptions = connection.execute("""
            SELECT COUNT(*)
            FROM exceptions
            WHERE exception_status IN ('OPEN', 'IN_PROGRESS')
        """).fetchone()[0]

        return render_template(
            "reports.html",
            payment_summary=payment_summary,
            reconciliation_summary=reconciliation_summary,
            exception_summary=exception_summary,
            financial_summary=financial_summary,
            total_payments=total_payments,
            total_exceptions=total_exceptions,
            open_exceptions=open_exceptions
        )

    finally:
        connection.close()


# CSV Report Export

@main.route("/reports/export/<report_type>")
def export_report(report_type):

    report_tables = {
        "payments": "payment_orders",
        "settlements": "settlement_batches",
        "bank-statements": "bank_statement_lines",
        "reconciliation": "reconciliation_matches",
        "exceptions": "exceptions"
    }

    # Check whether the requested report exists
    if report_type not in report_tables:
        return "Invalid report type", 404

    table_name = report_tables[report_type]

    connection = get_connection()

    try:
        cursor = connection.execute(
            f"SELECT * FROM {table_name}"
        )

        # Get column names
        columns = [description[0] for description in cursor.description]

        # Get all records
        records = cursor.fetchall()

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(columns)

        for record in records:
            writer.writerow(list(record))

        # Prepare CSV response
        csv_data = output.getvalue()
        output.close()

        filename = f"{report_type}_report.csv"

        return Response(
            csv_data,
            mimetype="text/csv",
            headers={
                "Content-Disposition":
                    f"attachment; filename={filename}"
            }
        )

    finally:
        connection.close()