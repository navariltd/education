# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import csv

import frappe
import openpyxl
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, strip_html
from frappe.utils.file_manager import get_file_path

from education.education.doctype.fee_request.fee_request import (
    allocate_amount,
    get_export_lines,
    get_payment_group_key,
)


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

    def on_cancel(self):
        # Submitted payments block the cancel through their link to this import. Drafts
        # waiting for review do not, and must not be submitted for a cancelled import.
        drafts = frappe.get_all(
            "Fee Request Payment",
            filters={"fee_request_payment_import": self.name, "docstatus": 0},
            pluck="name",
        )
        for payment in self.payments:
            if payment.fee_request_payment in drafts:
                payment.db_set("fee_request_payment", None)

        for name in drafts:
            frappe.delete_doc("Fee Request Payment", name, ignore_permissions=True)

        if drafts:
            frappe.msgprint(
                _(
                    "Deleted the draft Fee Request Payments created by this import: {0}"
                ).format(", ".join(drafts)),
                alert=True,
            )

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
                        "scholar": payment.scholar,
                        "payment_type": "Payment",
                        "fee_request_payment_import": self.name,
                        "allocations": [
                            {
                                "fee_request": allocation.fee_request,
                                "academic_term": allocation.academic_term,
                                "amount": allocation.amount,
                                "export_line": allocation.export_line,
                            }
                            for allocation in payment.flags.allocations
                        ],
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
                "{0} overpayment(s) were saved as draft Fee Request Payments for review."
            ).format(drafts)
        frappe.msgprint(message + " " + _("Other rows with remarks were not created."))

    def validate_rows(self):
        """Match every row to the bank row it pays, split its amount over that row's terms
        and record why a row will be skipped in its remarks, before anything is created.
        """
        if not self.fee_request_export:
            frappe.throw(_("Select the Fee Request Export this bank file answers."))

        lines = get_export_lines(export=self.fee_request_export)
        if not lines:
            frappe.throw(
                _("Fee Request Export {0} is not submitted.").format(
                    self.fee_request_export
                )
            )

        claimed_groups = set()
        claimed_amounts = {}
        for payment in self.payments:
            payment.update(
                {
                    "fee_request": None,
                    "payment_group": None,
                    "exported_amount": 0,
                    "payment_result": None,
                    "export_line": None,
                    "overpayment": 0,
                }
            )
            payment.flags.allocations = []
            payment.remarks = self.get_row_problem(
                payment, lines, claimed_groups, claimed_amounts
            )

    def get_bank_row_lines(self, reference, lines):
        prefix = f"{self.fee_request_export}-"
        if reference.startswith(prefix) and reference[len(prefix) :].isdigit():
            payment_group = int(reference[len(prefix) :])
            return [line for line in lines if line.payment_group == payment_group]

        # Exports made before bank rows were numbered used the Fee Request as the reference.
        return [
            line
            for line in lines
            if not line.payment_group and line.fee_request == reference
        ]

    def get_row_problem(self, payment, lines, claimed_groups, claimed_amounts):
        # Rows read before references named bank rows hold the Fee Request instead.
        reference = (payment.reference or payment.fee_request or "").strip()
        if not reference:
            return _("No reference in the bank row.")

        group = self.get_bank_row_lines(reference, lines)
        if not group:
            return _("{0} is not a row of Fee Request Export {1}.").format(
                reference, self.fee_request_export
            )

        first = group[0]
        payment.update(
            {
                "fee_request": first.fee_request,
                "payment_group": first.payment_group,
                "export_line": first.name,
                "exported_amount": sum(flt(line.amount) for line in group),
            }
        )
        if payment.scholar and payment.scholar != first.scholar:
            return _("Scholar does not match bank row {0} ({1}).").format(
                reference, first.scholar
            )
        payment.scholar = payment.scholar or first.scholar

        key = get_payment_group_key(first)
        if key in claimed_groups:
            return _("This bank row appears more than once in the file.")
        claimed_groups.add(key)

        settled = next((line for line in group if line.status == "Settled"), None)
        if settled:
            return _(
                "Bank row already settled by {0} {1}. This looks like a duplicate upload."
            ).format(settled.settled_by_doctype or "", settled.settled_by or "")

        pending = [line for line in group if line.status == "Pending"]
        if not pending:
            return _("This bank row was withdrawn from the export.")

        draft = frappe.db.get_value(
            "Fee Request Payment Allocation",
            {
                "parenttype": "Fee Request Payment",
                "export_line": ["in", [line.name for line in pending]],
                "docstatus": 0,
            },
            "parent",
        )
        if draft:
            return _(
                "Draft Fee Request Payment {0} is already waiting for review for this bank row. This looks like a duplicate upload."
            ).format(draft)

        if flt(payment.amount) <= 0:
            return _("Amount must be greater than zero.")

        terms = []
        for line in pending:
            term = frappe.db.get_value(
                "Fee Request Term",
                {
                    "parent": line.fee_request,
                    "parenttype": "Fee Request",
                    "academic_term": line.academic_term,
                },
                ["term_start_date", "outstanding_amount", "purchase_invoice"],
                as_dict=True,
            )
            if not term:
                return _("Fee Request {0} does not cover {1}.").format(
                    line.fee_request, line.academic_term
                )
            if term.purchase_invoice:
                return _(
                    "Fee Request {0} uses accounting. Record its payment with a Payment Entry against {1}."
                ).format(line.fee_request, term.purchase_invoice)

            pair = (line.fee_request, line.academic_term)
            terms.append(
                frappe._dict(
                    fee_request=line.fee_request,
                    academic_term=line.academic_term,
                    term_start_date=term.term_start_date,
                    outstanding_amount=flt(term.outstanding_amount)
                    - claimed_amounts.get(pair, 0),
                    export_line=line.name,
                )
            )

        # Oldest term first; anything over what is owed lands on the latest term.
        terms.sort(key=lambda term: (term.term_start_date or getdate("1900-01-01"),))
        payment.flags.allocations, _remaining = allocate_amount(
            payment.amount, terms, "outstanding_amount", excess_to_last=True
        )
        for allocation in payment.flags.allocations:
            pair = (allocation.fee_request, allocation.academic_term)
            claimed_amounts[pair] = claimed_amounts.get(pair, 0) + allocation.amount

        difference = flt(payment.amount) - flt(payment.exported_amount)
        payment.payment_result = (
            "Over" if difference > 0.005 else "Short" if difference < -0.005 else "Full"
        )

        owed = sum(max(term.outstanding_amount, 0) for term in terms)
        if flt(payment.amount) > owed + 0.005:
            payment.overpayment = 1
            return _(
                "Overpayment: {0} exceeds the outstanding {1}. A draft Fee Request Payment will be created with the excess on the latest term; tick Allow Overpayment and submit it if the school was really paid more."
            ).format(payment.amount, flt(owed, 2))

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
                "reference": details[0] if len(details) > 0 else None,
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
                "reference": details[0] if len(details) > 0 else None,
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
                "reference": details[0] if len(details) > 0 else None,
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
