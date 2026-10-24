# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import csv

import frappe
import openpyxl
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, strip_html
from frappe.utils.file_manager import get_file_path

from education.education.doctype.fee_request.fee_request import get_export_lines


class FeeRequestPaymentImport(Document):
    def before_save(self):
        if self.payments:
            total_amount = sum(p.amount for p in self.payments)
            self.total_amount = total_amount

        if self.request_type == "Stipend":
            self.bank = ""

    def before_submit(self):
        if not self.payments:
            frappe.throw("No payments to process.")

        self.validate_rows()

    def on_submit(self):
        created = drafts = 0
        for payment in self.payments:
            if payment.remarks and not payment.overpayment:
                continue

            try:
                frappe.db.savepoint("fee_request_payment")
                frp = frappe.get_doc(
                    {
                        "doctype": "Fee Request Payment",
                        "fee_request": payment.fee_request,
                        "scholar": payment.scholar,
                        "payment_type": "Payment",
                        "paid_amount": payment.amount,
                        "academic_year": self.academic_year,
                        "academic_term": self.academic_term,
                        "export_line": payment.export_line,
                        "fee_request_payment_import": self.name,
                    }
                )
                frp.flags.from_payment_import = True
                frp.save(ignore_permissions=True)
                payment.db_set("fee_request_payment", frp.name)

                # Overpayments stay in draft until someone ticks Allow Overpayment and submits.
                if payment.overpayment:
                    drafts += 1
                    continue

                frp.submit()
                payment.db_set("payment_created", True)
                created += 1
            except Exception as e:
                frappe.db.rollback(save_point="fee_request_payment")
                frappe.clear_last_message()
                frappe.log_error(
                    frappe.get_traceback(), "Payment Record Creation Failed"
                )
                payment.db_set(
                    {
                        "remarks": strip_html(str(e))
                        or _("Payment could not be created."),
                        "overpayment": 0,
                        "fee_request_payment": None,
                    }
                )

        message = _("{0} of {1} payments created.").format(created, len(self.payments))
        if drafts:
            message += " " + _(
                "{0} overpayments were saved as draft Fee Request Payments for review."
            ).format(drafts)
        frappe.msgprint(message + " " + _("Other rows with remarks were not created."))

    def validate_rows(self):
        """Check every row before anything is created and record why a row will be
        skipped in its remarks."""
        claimed_lines = set()
        claimed_amounts = {}
        for payment in self.payments:
            payment.export_line = None
            payment.overpayment = 0
            payment.remarks = self.get_row_problem(
                payment, claimed_lines, claimed_amounts
            )

    def get_row_problem(self, payment, claimed_lines, claimed_amounts):
        if not payment.fee_request:
            return _("No Fee Request in the bank reference.")

        fee_request = frappe.db.get_value(
            "Fee Request",
            payment.fee_request,
            ["docstatus", "scholar", "request_type", "academic_year"],
            as_dict=True,
        )
        if not fee_request:
            return _("Fee Request {0} not found.").format(payment.fee_request)
        if fee_request.docstatus != 1:
            return _("Fee Request {0} is not submitted.").format(payment.fee_request)
        if payment.scholar and payment.scholar != fee_request.scholar:
            return _("Scholar does not match Fee Request {0}.").format(
                payment.fee_request
            )
        if fee_request.request_type != (self.request_type or "Fee Request"):
            return _("Fee Request {0} is a {1}.").format(
                payment.fee_request, fee_request.request_type
            )
        if fee_request.academic_year != self.academic_year:
            return _("Fee Request {0} is for Academic Year {1}.").format(
                payment.fee_request, fee_request.academic_year
            )

        term = frappe.db.get_value(
            "Fee Request Term",
            {
                "parent": payment.fee_request,
                "parenttype": "Fee Request",
                "academic_term": self.academic_term,
            },
            ["outstanding_amount", "purchase_invoice"],
            as_dict=True,
        )
        if not term:
            return _("Fee Request {0} does not cover {1}.").format(
                payment.fee_request, self.academic_term
            )
        if term.purchase_invoice:
            return _(
                "Fee Request {0} uses accounting. Record its payment with a Payment Entry against {1}."
            ).format(payment.fee_request, term.purchase_invoice)
        if flt(payment.amount) <= 0:
            return _("Amount must be greater than zero.")

        lines = [
            line
            for line in get_export_lines(
                fee_request=payment.fee_request, export=self.fee_request_export
            )
            if line.academic_term == self.academic_term
        ]
        line = next(
            (
                line
                for line in lines
                if line.status == "Pending" and line.name not in claimed_lines
            ),
            None,
        )
        if line:
            draft = frappe.db.get_value(
                "Fee Request Payment", {"export_line": line.name, "docstatus": 0}
            )
            if draft:
                return _(
                    "Draft Fee Request Payment {0} is already waiting for review for this line. This looks like a duplicate upload."
                ).format(draft)

        if not line:
            settled = next((line for line in lines if line.status == "Settled"), None)
            if settled:
                return _(
                    "Export line already settled by {0} {1}. This looks like a duplicate upload."
                ).format(settled.settled_by_doctype, settled.settled_by)
            if self.fee_request_export:
                return _(
                    "Fee Request {0} has no open line in Fee Request Export {1}."
                ).format(payment.fee_request, self.fee_request_export)

        key = (payment.fee_request, self.academic_term)
        outstanding = flt(term.outstanding_amount) - claimed_amounts.get(key, 0)
        overpaid = flt(payment.amount) > outstanding + 0.005

        claimed_amounts[key] = claimed_amounts.get(key, 0) + flt(payment.amount)
        if line:
            claimed_lines.add(line.name)
            payment.export_line = line.name

        if overpaid:
            payment.overpayment = 1
            return _(
                "Overpayment: {0} exceeds the outstanding {1}. A draft Fee Request Payment will be created; tick Allow Overpayment and submit it if the school was really paid more."
            ).format(payment.amount, max(outstanding, 0))

        return None


@frappe.whitelist()
def process_payment_file(docname):
    doc = frappe.get_doc("Fee Request Payment Import", docname)

    if not doc.payment_file:
        frappe.throw("Please attach a payment file.")

    doc.status = "Processing"
    doc.save(ignore_permissions=True)

    try:
        file_path = get_file_path(doc.payment_file)
        rows = read_file(file_path)
        # bank = doc.bank

        payments = parse_file(rows, doc)

        doc.set("payments", [])  # Clear existing payments if any
        for payment in payments:
            doc.append("payments", payment)

        doc.validate_rows()
        doc.status = "Completed"
        doc.save(ignore_permissions=True)
    except Exception as e:
        doc.status = "Failed"
        doc.save(ignore_permissions=True)
        frappe.log_error(frappe.get_traceback(), "Payment Import Failed")
        frappe.throw(str(e))


def read_file(file_path):
    if file_path.endswith(".csv"):
        with open(file_path, newline="", encoding="utf-8") as f:
            return list(csv.reader(f))

    elif file_path.endswith(".xlsx"):
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        return [[cell.value for cell in row] for row in ws.iter_rows()]

    else:
        frappe.throw("Unsupported file format")


def parse_file(rows, doc):
    if doc.request_type != "Stipend":
        if doc.bank == "KCB":
            return parse_kcb(rows)
        elif doc.bank == "Standard Chartered":
            return parse_standard_chartered(rows)
        else:
            frappe.throw("Unsupported bank")
    else:
        return parse_teen_mom_stipend(rows)


# KCB
def parse_kcb(rows):
    header_index, headers = find_header_index(rows, "Description", bank="KCB")
    idx = {h: i for i, h in enumerate(headers)}

    data = []
    for row in rows[header_index + 1 :]:
        if not any(row):
            continue

        description = row[idx["Description"]]
        parsed = parse_kcb_description(description)
        if not parsed:
            continue

        details = parsed.get("beneficiary_reference").split("|")
        amount = parsed.get("transfer_amount")
        if isinstance(amount, str):
            amount = (
                amount.replace(",", "").replace(" KES", "").replace("Sh", "").strip()
            )
            amount = float(amount) if amount else 0
        else:
            amount = float(amount or 0)
        data.append(
            {
                "scholar": details[1] if len(details) > 1 else None,
                "fee_request": details[0] if len(details) > 0 else None,
                "amount": amount,
            }
        )

    return data


def parse_kcb_description(description):
    """
    Convert multi-line description into dict
    """
    result = {}

    if not description:
        return result

    lines = description.split("\n")

    for line in lines:
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()

        result[key] = value

    return result


# Standard Chartered
def parse_standard_chartered(rows):
    header_index, headers = find_header_index(
        rows, "Payment Details in English 1", bank="Standard Chartered"
    )
    idx = {h: i for i, h in enumerate(headers)}

    data = []
    for row in rows[header_index + 1 :]:
        if not any(row):
            continue

        if (
            row[idx["Payment Details in English 1"]] == ""
            or row[idx["Payment Details in English 1"]] is None
        ):
            continue

        details = row[idx["Payment Details in English 1"]].split("|")
        amount = row[idx["Payment Amount"]]
        if isinstance(amount, str):
            amount = (
                amount.replace(",", "").replace(" KES", "").replace("Sh", "").strip()
            )
            amount = float(amount) if amount else 0
        else:
            amount = float(amount or 0)
        data.append(
            {
                "scholar": details[1] if len(details) > 1 else None,
                "fee_request": details[0] if len(details) > 0 else None,
                "amount": amount,
            }
        )

    return data


def parse_teen_mom_stipend(rows):
    header_index, headers = find_header_index(rows, "REFERENCE")
    idx = {h: i for i, h in enumerate(headers)}

    data = []
    for row in rows[header_index + 1 :]:
        if not any(row):
            continue

        if row[idx["REFERENCE"]] == "" or row[idx["REFERENCE"]] is None:
            continue

        details = row[idx["REFERENCE"]].split("|")
        amount = row[idx["AMOUNT"]]
        if isinstance(amount, str):
            amount = (
                amount.replace(",", "").replace(" KES", "").replace("Sh", "").strip()
            )
            amount = float(amount) if amount else 0
        else:
            amount = float(amount or 0)
        data.append(
            {
                "scholar": details[1] if len(details) > 1 else None,
                "fee_request": details[0] if len(details) > 0 else None,
                "amount": amount,
            }
        )

    return data


def find_header_index(rows, expected_header, bank="Stipend"):
    for i, row in enumerate(rows):
        if expected_header in row:
            return i, row

    frappe.throw(
        f"Header '{expected_header}' not found. Please ensure the file attached is in the correct format for {bank}."
    )
