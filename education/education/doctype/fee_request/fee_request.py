# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import datetime

import frappe
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions,
)
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Min, Sum
from frappe.utils import cint, flt, formatdate, get_link_to_form, getdate, nowdate

from education.education.doctype.scholar.scholar import is_eligible_status

EXPORT_LINE_DOCTYPES = (
    "KCB Fee Request Export Item",
    "Standard Chartered Fee Request Export Item",
    "Stipend Fee Request Export Item",
)

# Entry types that count towards the paid amount; the rest count as adjustments.
PAID_ENTRY_TYPES = ("Payment", "Refund", "Transfer In", "Transfer Out")


class FeeRequest(Document):
    def validate(self):
        self.validate_lines()
        self.validate_supplementary()
        self.validate_term_overlap()
        self.set_terms()

    def before_submit(self):
        self.validate_scholar_active_for_terms()
        if self.should_create_purchase_invoice():
            self.validate_purchase_invoice_prerequisites()

    def on_submit(self):
        if self.should_create_purchase_invoice():
            self.create_purchase_invoices()

            # A supplier advance may have been allocated to the new invoices.
            if any(
                get_purchase_invoice_activity(term.purchase_invoice, term.academic_term)
                for term in self.terms
            ):
                refresh_fee_request(self.name)

    def before_cancel(self):
        self.validate_no_payments()
        self.validate_no_supplementary_requests()
        self.validate_no_open_export_lines()

    def on_cancel(self):
        self.ignore_linked_doctypes = (
            "Purchase Invoice",
            "Fee Request Export",
            "Fee Request Payment Import",
        )
        self.cancel_purchase_invoices()

    def should_create_purchase_invoice(self):
        if self.request_type != "Fees":
            return False

        enabled = frappe.db.get_single_value(
            "Education Settings", "create_purchase_invoice_on_fee_request"
        )
        if enabled is None:
            return True
        return bool(cint(enabled))

    def has_purchase_invoices(self):
        return any(term.purchase_invoice for term in self.terms)

    def get_term(self, academic_term):
        return next(
            (term for term in self.terms if term.academic_term == academic_term), None
        )

    def validate_lines(self):
        if not self.fee_components:
            frappe.throw(_("Add at least one Fee Component."))

        seen = set()
        for row in self.fee_components:
            if not row.academic_term:
                frappe.throw(
                    _("Fee Components row {0}: Academic Term is required.").format(
                        row.idx
                    )
                )

            if flt(row.amount) <= 0:
                frappe.throw(
                    _(
                        "Fee Components row {0}: Amount must be greater than zero."
                    ).format(row.idx)
                )

            key = (row.academic_term, row.fees_category)
            if key in seen:
                frappe.throw(
                    _(
                        "Fee Components row {0}: {1} is already listed for {2}. Each fee category can appear only once per term."
                    ).format(row.idx, row.fees_category, row.academic_term)
                )
            seen.add(key)

        term_years = dict(
            frappe.get_all(
                "Academic Term",
                filters={"name": ["in", list(self.get_term_names())]},
                fields=["name", "academic_year"],
                as_list=True,
            )
        )
        for row in self.fee_components:
            if term_years.get(row.academic_term) != self.academic_year:
                frappe.throw(
                    _(
                        "Fee Components row {0}: {1} does not belong to Academic Year {2}."
                    ).format(row.idx, row.academic_term, self.academic_year)
                )

        if len(self.get_term_names()) > 1:
            if self.request_type == "Stipend":
                frappe.throw(_("A Stipend request must cover exactly one term."))

            if get_term_mode() != "Allow Multiple Terms":
                frappe.throw(
                    _(
                        "A Fee Request must cover exactly one term. To allow several terms, set Fee Request Term Mode to Allow Multiple Terms in Education Settings."
                    )
                )

    def validate_supplementary(self):
        if not self.is_supplementary:
            self.against_fee_request = None
            return

        if not self.against_fee_request:
            frappe.throw(
                _("Against Fee Request is required for a supplementary request.")
            )

        original = frappe.db.get_value(
            "Fee Request",
            self.against_fee_request,
            [
                "docstatus",
                "scholar",
                "academic_year",
                "request_type",
                "is_supplementary",
            ],
            as_dict=True,
        )
        if not original or original.docstatus != 1:
            frappe.throw(
                _("Against Fee Request {0} must be submitted.").format(
                    self.against_fee_request
                )
            )

        if original.is_supplementary:
            frappe.throw(
                _(
                    "Against Fee Request must be the original request, not another supplementary request."
                )
            )

        for fieldname in ("scholar", "academic_year", "request_type"):
            if original.get(fieldname) != self.get(fieldname):
                frappe.throw(
                    _("{0} must match Against Fee Request {1}.").format(
                        self.meta.get_label(fieldname), self.against_fee_request
                    )
                )

        original_terms = set(
            frappe.get_all(
                "Fee Request Term",
                filters={
                    "parent": self.against_fee_request,
                    "parenttype": "Fee Request",
                },
                pluck="academic_term",
            )
        )
        missing = self.get_term_names() - original_terms
        if missing:
            frappe.throw(
                _("{0} is not on Against Fee Request {1}.").format(
                    ", ".join(sorted(missing)), self.against_fee_request
                )
            )

    def validate_term_overlap(self):
        if self.is_supplementary or not self.get_term_names():
            return

        FR = frappe.qb.DocType("Fee Request")
        FRT = frappe.qb.DocType("Fee Request Term")
        overlaps = (
            frappe.qb.from_(FRT)
            .join(FR)
            .on(FRT.parent == FR.name)
            .select(FR.name, FRT.academic_term)
            .where(
                (FRT.parenttype == "Fee Request")
                & (FR.docstatus == 1)
                & (FR.scholar == self.scholar)
                & (FR.request_type == self.request_type)
                & (FR.is_supplementary == 0)
                & (FR.name != (self.name or ""))
                & (FRT.academic_term.isin(list(self.get_term_names())))
            )
        ).run(as_dict=True)

        if overlaps:
            frappe.throw(
                _(
                    "{0} already has a submitted {1} for {2}: {3}. Use a supplementary request to add to it."
                ).format(
                    self.scholar,
                    self.request_type,
                    ", ".join(sorted({row.academic_term for row in overlaps})),
                    ", ".join(
                        get_link_to_form("Fee Request", name)
                        for name in sorted({row.name for row in overlaps})
                    ),
                )
            )

    def get_term_names(self):
        return {row.academic_term for row in self.fee_components if row.academic_term}

    def set_terms(self):
        amounts = {}
        for row in self.fee_components:
            amounts[row.academic_term] = amounts.get(row.academic_term, 0) + flt(
                row.amount
            )

        start_dates = dict(
            frappe.get_all(
                "Academic Term",
                filters={"name": ["in", list(amounts)]},
                fields=["name", "term_start_date"],
                as_list=True,
            )
        )
        ordered = sorted(
            amounts, key=lambda term: (start_dates.get(term) or datetime.date.min, term)
        )

        self.set("terms", [])
        for term in ordered:
            self.append(
                "terms",
                {
                    "academic_term": term,
                    "term_start_date": start_dates.get(term),
                    "amount": amounts[term],
                    "outstanding_amount": amounts[term],
                    "payment_status": "Unpaid",
                },
            )

        self.terms_label = ", ".join(ordered)
        self.set_totals()

    def set_totals(self):
        self.total_amount = sum(flt(term.amount) for term in self.terms)
        self.paid_amount = sum(flt(term.paid_amount) for term in self.terms)
        self.adjusted_amount = sum(flt(term.adjusted_amount) for term in self.terms)
        self.outstanding_amount = sum(
            flt(term.outstanding_amount) for term in self.terms
        )
        self.payment_status = get_overall_status(
            [term.payment_status for term in self.terms]
        )

    @frappe.whitelist()
    def recalculate_balances(self):
        self.check_permission("write")
        refresh_fee_request(self.name)

    def refresh_balances(self, save=True):
        """Rebuild term balances, payment history and export line settlement from the
        source documents. Safe to call any number of times."""
        precision = frappe.get_precision("Fee Request Term", "outstanding_amount")
        activity = self.get_payment_activity()
        in_flight = sync_export_lines(self.name, activity)

        for term in self.terms:
            rows = [row for row in activity if row.academic_term == term.academic_term]
            term.paid_amount = flt(
                sum(
                    row.paid_amount
                    for row in rows
                    if row.entry_type in PAID_ENTRY_TYPES
                ),
                precision,
            )
            term.adjusted_amount = flt(
                sum(
                    row.paid_amount
                    for row in rows
                    if row.entry_type not in PAID_ENTRY_TYPES
                ),
                precision,
            )
            term.outstanding_amount = flt(
                flt(term.amount) - term.paid_amount - term.adjusted_amount, precision
            )
            term.in_flight_amount = flt(in_flight.get(term.academic_term), precision)
            term.payment_status = get_term_status(
                term.paid_amount, term.adjusted_amount, term.outstanding_amount
            )

        self.set("payments", [])
        for row in sorted(
            activity, key=lambda row: (row.payment_date or datetime.date.min)
        ):
            self.append(
                "payments",
                {
                    "payment_type": row.payment_type,
                    "payment": row.payment,
                    "entry_type": row.entry_type,
                    "academic_term": row.academic_term,
                    "paid_amount": row.paid_amount,
                    "payment_date": row.payment_date,
                },
            )

        self.set_totals()
        if save:
            self.flags.ignore_validate_update_after_submit = True
            # Only calculated values change here; a linked invoice cancelled in the same
            # transaction must not block the save.
            self.flags.ignore_links = True
            self.save(ignore_permissions=True)

    def get_payment_activity(self):
        """Every document that changed what is owed on each term. `paid_amount` is the
        amount by which the outstanding went down (negative for refunds and transfers out).
        """
        if self.has_purchase_invoices():
            activity = []
            for term in self.terms:
                if term.purchase_invoice:
                    activity.extend(
                        get_purchase_invoice_activity(
                            term.purchase_invoice, term.academic_term
                        )
                    )
            return activity

        return get_fee_request_payment_activity(self.name)

    def validate_scholar_active_for_terms(self):
        scholar = frappe.db.get_value(
            "Scholar", self.scholar, ["status", "date_of_inactive"], as_dict=True
        )
        if is_eligible_status(scholar.status):
            return

        terms = [
            term.academic_term
            for term in self.terms
            if not is_term_payable(
                scholar.status, scholar.date_of_inactive, term.term_start_date
            )
        ]
        if terms:
            frappe.throw(
                _("{0} is {1}{2}, so {3} cannot be requested.").format(
                    self.scholar,
                    scholar.status,
                    (
                        _(" since {0}").format(formatdate(scholar.date_of_inactive))
                        if scholar.date_of_inactive
                        else ""
                    ),
                    ", ".join(terms),
                )
            )

    def validate_purchase_invoice_prerequisites(self):
        if not self.official_school_name:
            frappe.throw(
                _("Official School Name is required to create a Purchase Invoice.")
            )

        for row in self.fee_components:
            if not frappe.db.get_value("Fee Category", row.fees_category, "item"):
                frappe.throw(
                    _(
                        "Fee Category {0} has no linked Item. A Purchase Invoice cannot be created."
                    ).format(row.fees_category)
                )

    def create_purchase_invoices(self):
        dimensions = self.get_accounting_dimension_values()
        for term in self.terms:
            components = [
                row
                for row in self.fee_components
                if row.academic_term == term.academic_term
            ]
            invoice = self.make_purchase_invoice(term, components, dimensions)
            term.db_set("purchase_invoice", invoice.name)

    def make_purchase_invoice(self, term, components, dimensions):
        items = []
        for row in components:
            items.append(
                {
                    "item_code": frappe.db.get_value(
                        "Fee Category", row.fees_category, "item"
                    ),
                    "qty": 1,
                    "rate": flt(row.amount),
                    "description": f"{row.fees_category} ({term.academic_term})",
                }
            )

        invoice = frappe.get_doc(
            {
                "doctype": "Purchase Invoice",
                "supplier": self.official_school_name,
                "company": self.company,
                "posting_date": nowdate(),
                "bill_date": nowdate(),
                "bill_no": f"{self.name}/{term.academic_term}",
                "update_stock": 0,
                "ignore_pricing_rule": 1,
                "disable_rounded_total": 1,
                "fee_request": self.name,
                "academic_year": self.academic_year,
                "academic_term": term.academic_term,
                "items": items,
                "remarks": f"Against Fee Request {self.name} for {self.student_name}, {term.academic_term}",
                **dimensions,
            }
        )
        invoice.flags.ignore_permissions = True
        invoice.set_missing_values()

        if not invoice.payment_terms_template and term.term_start_date:
            invoice.due_date = max(getdate(nowdate()), getdate(term.term_start_date))
            invoice.set("payment_schedule", [])

        for fieldname, value in dimensions.items():
            invoice.set(fieldname, value)

        for invoice_item, component in zip(invoice.items, components):
            invoice_item.qty = 1
            invoice_item.rate = flt(component.amount)
            self.set_accounting_dimensions(invoice_item, dimensions)

        for tax in invoice.get("taxes") or []:
            self.set_accounting_dimensions(tax, dimensions)

        invoice.insert(ignore_permissions=True)
        invoice.submit()
        return invoice

    def cancel_purchase_invoices(self):
        for term in self.terms:
            if not term.purchase_invoice:
                continue

            invoice = frappe.get_doc("Purchase Invoice", term.purchase_invoice)
            if invoice.docstatus != 1:
                continue

            invoice.flags.ignore_permissions = True
            invoice.cancel()

    def validate_no_payments(self):
        payments = frappe.get_all(
            "Fee Request Payment",
            filters={"docstatus": 1},
            or_filters={"fee_request": self.name, "target_fee_request": self.name},
            pluck="name",
        )
        if payments:
            frappe.throw(
                _(
                    "Cannot cancel: submitted Fee Request Payments are linked to this request ({0}). Cancel them first."
                ).format(
                    ", ".join(
                        get_link_to_form("Fee Request Payment", name)
                        for name in payments
                    )
                )
            )

        for term in self.terms:
            if term.purchase_invoice and get_purchase_invoice_activity(
                term.purchase_invoice, term.academic_term
            ):
                frappe.throw(
                    _(
                        "Cannot cancel: Purchase Invoice {0} has payments or debit notes against it. Unreconcile or cancel them first."
                    ).format(
                        get_link_to_form("Purchase Invoice", term.purchase_invoice)
                    )
                )

    def validate_no_supplementary_requests(self):
        supplementary = frappe.get_all(
            "Fee Request",
            filters={"against_fee_request": self.name, "docstatus": 1},
            pluck="name",
        )
        if supplementary:
            frappe.throw(
                _(
                    "Cannot cancel: cancel the supplementary requests first ({0})."
                ).format(
                    ", ".join(
                        get_link_to_form("Fee Request", name) for name in supplementary
                    )
                )
            )

    def validate_no_open_export_lines(self):
        exports = sorted(
            {
                line.export
                for line in get_export_lines(self.name)
                if line.status in ("Pending", "Settled")
            }
        )
        if exports:
            frappe.throw(
                _(
                    "Cannot cancel: this request is in Fee Request Export {0}. Withdraw its line or cancel the export first."
                ).format(
                    ", ".join(
                        get_link_to_form("Fee Request Export", name) for name in exports
                    )
                )
            )

    def get_accounting_dimension_values(self):
        values = {}
        for fieldname in ("cost_center", "project", *get_accounting_dimensions()):
            if self.meta.has_field(fieldname) and self.get(fieldname):
                values[fieldname] = self.get(fieldname)
        return values

    @staticmethod
    def set_accounting_dimensions(target, dimensions):
        for fieldname, value in dimensions.items():
            if target.meta.has_field(fieldname):
                target.set(fieldname, value)


def is_term_payable(
    scholar_status, date_of_inactive, term_start_date, eligible_statuses=None
):
    """An eligible scholar's terms are payable. Once a scholar is no longer eligible, only
    terms that started on or before their Date of Inactive are."""
    if is_eligible_status(scholar_status, eligible_statuses):
        return True
    return bool(
        date_of_inactive
        and term_start_date
        and getdate(term_start_date) <= getdate(date_of_inactive)
    )


def get_term_mode():
    return (
        frappe.db.get_single_value("Education Settings", "fee_request_term_mode")
        or "Single Term Only"
    )


def get_term_status(paid, adjusted, outstanding):
    if outstanding < 0:
        return "Overpaid"
    if outstanding == 0 and (paid or adjusted):
        return "Paid"
    if paid > 0:
        return "Partially Paid"
    return "Unpaid"


def get_overall_status(statuses):
    if not statuses:
        return "Unpaid"
    if "Overpaid" in statuses:
        return "Overpaid"
    if all(status == "Paid" for status in statuses):
        return "Paid"
    if all(status == "Unpaid" for status in statuses):
        return "Unpaid"
    return "Partially Paid"


def refresh_fee_request(name):
    fee_request = frappe.get_doc("Fee Request", name, for_update=True)
    if fee_request.docstatus != 1:
        return

    fee_request.refresh_balances()


def get_purchase_invoice_activity(purchase_invoice, academic_term):
    """Payments, journal entries and debit notes against a term's Purchase Invoice, read
    from the Payment Ledger so reconciliation and unreconciliation are always reflected.
    """
    PLE = frappe.qb.DocType("Payment Ledger Entry")
    entries = (
        frappe.qb.from_(PLE)
        .select(
            PLE.voucher_type,
            PLE.voucher_no,
            Sum(PLE.amount).as_("amount"),
            Min(PLE.posting_date).as_("posting_date"),
            Min(PLE.creation).as_("creation"),
        )
        .where(
            (PLE.against_voucher_type == "Purchase Invoice")
            & (PLE.against_voucher_no == purchase_invoice)
            & (PLE.delinked == 0)
        )
        .groupby(PLE.voucher_type, PLE.voucher_no)
    ).run(as_dict=True)

    def is_invoice(entry):
        return (
            entry.voucher_type == "Purchase Invoice"
            and entry.voucher_no == purchase_invoice
        )

    invoice_amount = sum(flt(entry.amount) for entry in entries if is_invoice(entry))
    sign = -1 if invoice_amount < 0 else 1

    # Reconciling a debit note against the invoice posts a "Debit Note" journal entry.
    journal_entries = [
        e.voucher_no for e in entries if e.voucher_type == "Journal Entry"
    ]
    debit_note_journals = set(
        frappe.get_all(
            "Journal Entry",
            filters={"name": ["in", journal_entries], "voucher_type": "Debit Note"},
            pluck="name",
        )
        if journal_entries
        else []
    )

    activity = []
    for entry in entries:
        if is_invoice(entry):
            continue

        amount = -flt(entry.amount) * sign
        if not amount:
            continue

        if (
            entry.voucher_type == "Purchase Invoice"
            or entry.voucher_no in debit_note_journals
        ):
            entry_type = "Reduction"
        else:
            entry_type = "Payment" if amount > 0 else "Refund"

        activity.append(
            frappe._dict(
                payment_type=entry.voucher_type,
                payment=entry.voucher_no,
                entry_type=entry_type,
                academic_term=academic_term,
                paid_amount=amount,
                payment_date=entry.posting_date,
                recorded_on=entry.creation,
                export_line=None,
            )
        )

    return activity


def get_fee_request_payment_activity(fee_request):
    fields = [
        "name",
        "payment_type",
        "paid_amount",
        "posting_date",
        "modified",
        "academic_term",
        "target_academic_term",
        "export_line",
    ]
    activity = []

    for payment in frappe.get_all(
        "Fee Request Payment",
        filters={"docstatus": 1, "fee_request": fee_request},
        fields=fields,
    ):
        entry_type, amount = {
            "Payment": ("Payment", payment.paid_amount),
            "Refund": ("Refund", -flt(payment.paid_amount)),
            "Reduction": ("Reduction", payment.paid_amount),
            "Transfer": ("Transfer Out", -flt(payment.paid_amount)),
        }[payment.payment_type or "Payment"]
        activity.append(
            make_payment_activity(payment, entry_type, amount, payment.academic_term)
        )

    for payment in frappe.get_all(
        "Fee Request Payment",
        filters={
            "docstatus": 1,
            "payment_type": "Transfer",
            "target_fee_request": fee_request,
        },
        fields=fields,
    ):
        activity.append(
            make_payment_activity(
                payment,
                "Transfer In",
                payment.paid_amount,
                payment.target_academic_term,
            )
        )

    return activity


def make_payment_activity(payment, entry_type, amount, academic_term):
    return frappe._dict(
        payment_type="Fee Request Payment",
        payment=payment.name,
        entry_type=entry_type,
        academic_term=academic_term,
        paid_amount=flt(amount),
        payment_date=payment.posting_date,
        recorded_on=payment.modified,
        export_line=payment.export_line if entry_type == "Payment" else None,
    )


def get_export_lines(fee_request=None, export=None):
    """Lines of submitted Fee Request Exports, with their export's term and submission time."""
    E = frappe.qb.DocType("Fee Request Export")
    lines = []
    for doctype in EXPORT_LINE_DOCTYPES:
        L = frappe.qb.DocType(doctype)
        query = (
            frappe.qb.from_(L)
            .join(E)
            .on(L.parent == E.name)
            .select(
                L.name,
                L.fee_request,
                L.amount,
                L.status,
                L.paid_amount,
                L.settled_by_doctype,
                L.settled_by,
                E.name.as_("export"),
                E.academic_term,
                E.submitted_on,
                E.modified.as_("export_modified"),
            )
            .where((E.docstatus == 1) & (L.parenttype == "Fee Request Export"))
        )
        if fee_request:
            query = query.where(L.fee_request == fee_request)
        if export:
            query = query.where(E.name == export)

        for line in query.run(as_dict=True):
            line.doctype = doctype
            line.status = line.status or "Pending"
            line.exported_on = line.submitted_on or line.export_modified
            lines.append(line)

    return sorted(lines, key=lambda line: (line.exported_on, line.name))


def sync_export_lines(fee_request, activity):
    """Settle each Pending export line with the first payment recorded for its term after
    the export was submitted. A line whose settling payment no longer counts goes back to
    Pending. Withdrawn lines are left alone. Returns the Pending amount per term."""
    lines = [
        line
        for line in get_export_lines(fee_request)
        if line.status != "Withdrawn"
        # Lines settled before payments were tracked per line stay settled.
        and not (line.status == "Settled" and not line.settled_by)
    ]
    payments = {
        (row.payment_type, row.payment): row
        for row in activity
        if row.entry_type == "Payment" and row.paid_amount > 0
    }
    used = set()
    settled = {}

    def settle(line, key):
        used.add(key)
        settled[line.name] = key

    # A payment that names its export line (from a payment import) settles that line.
    for line in lines:
        key = next(
            (key for key, row in payments.items() if row.export_line == line.name), None
        )
        if key and key not in used:
            settle(line, key)

    # Keep earlier settlements that still count, so lines don't change hands.
    for line in lines:
        key = (line.settled_by_doctype, line.settled_by)
        if line.name not in settled and key in payments and key not in used:
            settle(line, key)

    # First unused payment for the term recorded after the export was submitted.
    for line in lines:
        if line.name in settled:
            continue

        for key, row in sorted(payments.items(), key=lambda item: item[1].recorded_on):
            if (
                key not in used
                and row.academic_term == line.academic_term
                and row.recorded_on >= line.exported_on
            ):
                settle(line, key)
                break

    in_flight = {}
    for line in lines:
        key = settled.get(line.name)
        if key:
            values = {
                "status": "Settled",
                "paid_amount": payments[key].paid_amount,
                "settled_by_doctype": key[0],
                "settled_by": key[1],
            }
        else:
            values = {
                "status": "Pending",
                "paid_amount": 0,
                "settled_by_doctype": None,
                "settled_by": None,
            }
            in_flight[line.academic_term] = in_flight.get(line.academic_term, 0) + flt(
                line.amount
            )

        if any(
            (line.get(field) or None) != (value or None)
            for field, value in values.items()
        ):
            frappe.db.set_value(line.doctype, line.name, values, update_modified=False)

    return in_flight


def get_exportable_amount(fee_request, academic_term):
    term = frappe.db.get_value(
        "Fee Request Term",
        {
            "parent": fee_request,
            "parenttype": "Fee Request",
            "academic_term": academic_term,
        },
        ["outstanding_amount", "in_flight_amount"],
        as_dict=True,
    )
    if not term:
        return 0
    return flt(term.outstanding_amount) - flt(term.in_flight_amount)


def refresh_fee_requests_for_invoices(invoices):
    if not invoices:
        return

    names = frappe.get_all(
        "Fee Request Term",
        filters={
            "purchase_invoice": ["in", list(invoices)],
            "parenttype": "Fee Request",
            "docstatus": 1,
        },
        pluck="parent",
        distinct=True,
    )
    for name in names:
        refresh_fee_request(name)


def update_fee_request_from_payment_ledger(doc, method=None):
    """Runs for every Payment Ledger Entry: payments, journal entries, debit notes,
    reconciliation and cancellation all post one, so balances stay current."""
    if doc.against_voucher_type != "Purchase Invoice" or not doc.against_voucher_no:
        return

    refresh_fee_requests_for_invoices([doc.against_voucher_no])
    warn_on_scholar_mismatch(doc)


def update_fee_request_from_unreconcile(doc, method=None):
    refresh_fee_requests_for_invoices(
        {
            row.reference_name
            for row in doc.get("allocations") or []
            if row.reference_doctype == "Purchase Invoice"
        }
    )


def ignore_fee_request_links(doc, method=None):
    doc.ignore_linked_doctypes = (
        *(doc.get("ignore_linked_doctypes") or ()),
        "Fee Request",
    )


def warn_on_scholar_mismatch(doc):
    """A school advance can be reconciled against any of that school's invoices. Warn when
    a Payment Entry tagged for one scholar lands on another scholar's invoice."""
    if doc.voucher_type != "Payment Entry" or not frappe.get_meta(
        "Payment Entry"
    ).has_field("fee_request"):
        return

    tagged = frappe.db.get_value("Payment Entry", doc.voucher_no, "fee_request")
    invoice_request = frappe.db.get_value(
        "Fee Request Term",
        {"purchase_invoice": doc.against_voucher_no, "parenttype": "Fee Request"},
        "parent",
    )
    if not tagged or not invoice_request or tagged == invoice_request:
        return

    scholars = dict(
        frappe.get_all(
            "Fee Request",
            filters={"name": ["in", [tagged, invoice_request]]},
            fields=["name", "scholar"],
            as_list=True,
        )
    )
    if scholars.get(tagged) != scholars.get(invoice_request):
        frappe.msgprint(
            _(
                "Payment Entry {0} is tagged for Fee Request {1} ({2}) but was allocated to Purchase Invoice {3} of Fee Request {4} ({5})."
            ).format(
                doc.voucher_no,
                tagged,
                scholars.get(tagged),
                doc.against_voucher_no,
                invoice_request,
                scholars.get(invoice_request),
            ),
            title=_("Different scholar"),
            indicator="orange",
        )


def refresh_out_of_sync_fee_requests():
    """Hourly safety net for ledger changes made outside the hooked paths."""
    names = frappe.db.sql_list(
        """
        SELECT DISTINCT frt.parent
        FROM `tabFee Request Term` frt
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = frt.purchase_invoice
        WHERE frt.parenttype = 'Fee Request'
            AND frt.docstatus = 1
            AND pi.docstatus = 1
            AND ABS(pi.outstanding_amount - frt.outstanding_amount) > 0.005
        """
    )
    for name in names:
        try:
            refresh_fee_request(name)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"Fee Request balance refresh failed: {name}")


@frappe.whitelist()
def get_fee_structure_template(fee_structure_template):
    fee_component_doc = frappe.get_doc("Fee Structure", fee_structure_template)
    return fee_component_doc.components


@frappe.whitelist()
def get_fee_request_terms(fee_request):
    frappe.has_permission("Fee Request", doc=fee_request, throw=True)
    return frappe.get_all(
        "Fee Request Term",
        filters={"parent": fee_request, "parenttype": "Fee Request"},
        fields=["academic_term", "amount", "paid_amount", "outstanding_amount"],
        order_by="idx",
    )
