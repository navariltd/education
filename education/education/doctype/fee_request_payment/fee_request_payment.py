# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_link_to_form

from education.education.doctype.fee_request.fee_request import (
    get_export_lines,
    get_fee_request_payment_activity,
    get_group_fee_requests,
    get_term_balance,
    refresh_fee_request,
)


class FeeRequestPayment(Document):
    def validate(self):
        self.payment_type = self.payment_type or "Payment"
        if self.payment_type != "Transfer":
            self.target_fee_request = self.target_academic_term = None

        self.validate_allocations()
        for row in self.allocations:
            fee_request = self.get_fee_request(row.fee_request)
            self.validate_amount(
                row, fee_request, fee_request.get_term(row.academic_term)
            )
        self.validate_export_lines()

    def on_submit(self):
        self.refresh_fee_requests()

    def before_cancel(self):
        self.validate_no_dependent_entries()

    def on_cancel(self):
        # The import's row only records which payment it created.
        self.ignore_linked_doctypes = ("Fee Request", "Fee Request Payment Import")
        self.refresh_fee_requests()

    def validate_allocations(self):
        if not self.allocations:
            frappe.throw(_("Add the terms this entry applies to in Allocations."))

        if self.payment_type == "Transfer" and len(self.allocations) > 1:
            frappe.throw(
                _(
                    "A Transfer moves an overpayment from one term. Keep only that term in Allocations."
                )
            )

        first = None
        seen = set()
        for row in self.allocations:
            key = (row.fee_request, row.academic_term)
            if key in seen:
                frappe.throw(
                    _(
                        "Row {0}: {1} of Fee Request {2} is allocated more than once."
                    ).format(row.idx, row.academic_term, row.fee_request)
                )
            seen.add(key)

            if flt(row.amount) <= 0:
                frappe.throw(
                    _("Row {0}: Amount must be greater than zero.").format(row.idx)
                )

            fee_request = self.get_fee_request(row.fee_request)
            self.get_open_term(fee_request, row.academic_term)
            if fee_request.scholar != self.scholar:
                frappe.throw(
                    _("Row {0}: Fee Request {1} is for {2}, not {3}.").format(
                        row.idx, row.fee_request, fee_request.scholar, self.scholar
                    )
                )

            # One entry is one amount paid to, or returned by, one school.
            first = first or fee_request
            for fieldname in ("academic_year", "request_type", "official_school_name"):
                if fee_request.get(fieldname) != first.get(fieldname):
                    frappe.throw(
                        _(
                            "Row {0}: every Fee Request in one entry must have the same {1} ({2})."
                        ).format(
                            row.idx,
                            _(fee_request.meta.get_label(fieldname)),
                            first.get(fieldname),
                        )
                    )

        self.academic_year = first.academic_year
        self.official_school_name = first.official_school_name
        self.paid_amount = flt(
            sum(flt(row.amount) for row in self.allocations),
            self.precision("paid_amount"),
        )

    def validate_no_dependent_entries(self):
        """Refunds and transfers were checked against the money on a term when they were
        submitted. Cancelling this entry must not take away money they relied on."""
        terms = [(row.fee_request, row.academic_term) for row in self.allocations]
        if self.payment_type == "Transfer":
            terms.append((self.target_fee_request, self.target_academic_term))

        for fee_request, academic_term in terms:
            amount = frappe.db.get_value(
                "Fee Request Term",
                {
                    "parent": fee_request,
                    "parenttype": "Fee Request",
                    "academic_term": academic_term,
                },
                "amount",
            )
            rows = [
                row
                for row in get_fee_request_payment_activity(fee_request)
                if row.academic_term == academic_term
            ]
            remaining = [row for row in rows if row.payment != self.name]

            # Only block what this cancellation makes worse, so a term that is already
            # out of balance can still be corrected.
            if (
                get_overdrawn_amount(amount, remaining)
                <= get_overdrawn_amount(amount, rows) + 0.005
            ):
                continue

            dependents = sorted(
                {
                    row.payment
                    for row in remaining
                    if row.entry_type in ("Refund", "Transfer Out")
                }
            )
            frappe.throw(
                _(
                    "Cannot cancel {0}: {1} on Fee Request {2} has refunds or transfers that rely on it: {3}. Cancel them first."
                ).format(
                    self.name,
                    academic_term,
                    get_link_to_form("Fee Request", fee_request),
                    ", ".join(
                        get_link_to_form("Fee Request Payment", name)
                        for name in dependents
                    ),
                ),
                title=_("Refunds or Transfers Depend on This Entry"),
            )

    def refresh_fee_requests(self):
        names = {row.fee_request for row in self.allocations}
        if self.payment_type == "Transfer":
            names.add(self.target_fee_request)

        # A payment that settles a bank row also settles the lines of the other requests
        # paid in that row.
        names |= get_group_fee_requests(names)
        for name in sorted(names):
            refresh_fee_request(name)

    def get_fee_request(self, name):
        cache = self.__dict__.setdefault("_fee_requests", {})
        if name in cache:
            return cache[name]

        fee_request = frappe.get_doc("Fee Request", name)
        if fee_request.docstatus != 1:
            frappe.throw(_("Fee Request {0} must be submitted.").format(name))

        if fee_request.has_purchase_invoices():
            frappe.throw(
                _(
                    "Fee Request {0} is linked to Purchase Invoices. Record its payments with a Payment Entry against the invoice."
                ).format(get_link_to_form("Fee Request", name))
            )

        cache[name] = fee_request
        return fee_request

    @staticmethod
    def get_open_term(fee_request, academic_term):
        term = fee_request.get_term(academic_term)
        if not term:
            frappe.throw(
                _("{0} is not one of the terms on Fee Request {1}.").format(
                    academic_term, fee_request.name
                )
            )
        return term

    def validate_amount(self, row, fee_request, term):
        amount = flt(row.amount)
        outstanding = flt(term.outstanding_amount)
        label = _("{0} of {1}").format(term.academic_term, fee_request.name)

        if self.payment_type == "Payment":
            self.validate_not_overpaid(amount, outstanding, label)

        elif self.payment_type == "Refund" and amount > flt(term.paid_amount):
            frappe.throw(
                _("A refund cannot exceed the amount paid for {0} ({1}).").format(
                    label, term.paid_amount
                )
            )

        elif self.payment_type == "Reduction" and amount > max(outstanding, 0):
            frappe.throw(
                _(
                    "A reduction cannot exceed the outstanding amount for {0} ({1})."
                ).format(label, max(outstanding, 0))
            )

        elif self.payment_type == "Transfer":
            credit = max(-outstanding, 0)
            if amount > credit:
                frappe.throw(
                    _(
                        "Only an overpayment can be transferred. {0} has {1} available to transfer."
                    ).format(label, credit)
                )

            target = self.get_fee_request(self.target_fee_request)
            target_term = self.get_open_term(target, self.target_academic_term)
            if (target.name, target_term.academic_term) == (
                fee_request.name,
                term.academic_term,
            ):
                frappe.throw(_("Transfer to a different term or Fee Request."))

            if (
                target.scholar != fee_request.scholar
                or target.request_type != fee_request.request_type
            ):
                frappe.throw(
                    _("A transfer must stay with the same scholar and request type.")
                )

            self.validate_not_overpaid(
                amount,
                flt(target_term.outstanding_amount),
                _("{0} of {1}").format(target_term.academic_term, target.name),
            )

    def validate_not_overpaid(self, amount, outstanding, label):
        if amount <= outstanding or self.allow_overpayment:
            return

        message = _(
            "{0} exceeds the outstanding amount for {1} ({2}). Tick Allow Overpayment if the school was really paid more."
        ).format(amount, label, outstanding)

        # A draft can hold an overpayment for review; only submitting needs the tick.
        if self.docstatus == 1:
            frappe.throw(message)
        elif not self.flags.from_payment_import:
            frappe.msgprint(message, title=_("Overpayment"), indicator="orange")

    def validate_export_lines(self):
        self.fee_request_export = None
        if not any(row.export_line for row in self.allocations):
            return

        lines = {
            line.name: line
            for fee_request in {row.fee_request for row in self.allocations}
            for line in get_export_lines(fee_request)
        }
        for row in self.allocations:
            if not row.export_line:
                continue

            line = lines.get(row.export_line)
            if (
                self.payment_type != "Payment"
                or not line
                or (line.fee_request, line.academic_term)
                != (row.fee_request, row.academic_term)
                or line.status == "Withdrawn"
                or (line.status == "Settled" and line.settled_by != self.name)
            ):
                # The line was settled or withdrawn while this payment waited in draft.
                # The payment still counts; it just no longer settles that line.
                row.export_line = None
                continue

            self.fee_request_export = line.export


def get_overdrawn_amount(amount, rows):
    """How far a term's refunds and transfers go beyond the money it has: refunds and
    transfers out greater than what was paid, or transferred credit the term no longer has.
    """
    paid, _adjusted, outstanding = get_term_balance(amount, rows)
    overdrawn = max(-paid, 0)
    if any(row.entry_type == "Transfer Out" for row in rows):
        overdrawn += max(outstanding, 0)
    return overdrawn
