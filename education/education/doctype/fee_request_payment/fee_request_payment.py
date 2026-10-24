# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_link_to_form

from education.education.doctype.fee_request.fee_request import (
    get_export_lines,
    refresh_fee_request,
)


class FeeRequestPayment(Document):
    def validate(self):
        self.payment_type = self.payment_type or "Payment"
        fee_request = self.get_fee_request(self.fee_request)
        term = self.get_open_term(fee_request, self.academic_term)
        self.academic_year = fee_request.academic_year

        if self.scholar != fee_request.scholar:
            frappe.throw(
                _("Scholar must match Fee Request {0} ({1}).").format(
                    self.fee_request, fee_request.scholar
                )
            )

        if flt(self.paid_amount) <= 0:
            frappe.throw(_("Amount must be greater than zero."))

        if self.payment_type != "Transfer":
            self.target_fee_request = self.target_academic_term = None

        self.validate_amount(fee_request, term)
        self.validate_export_line()

    def on_submit(self):
        self.refresh_fee_requests()

    def on_cancel(self):
        self.ignore_linked_doctypes = ("Fee Request",)
        self.refresh_fee_requests()

    def refresh_fee_requests(self):
        refresh_fee_request(self.fee_request)
        if (
            self.payment_type == "Transfer"
            and self.target_fee_request != self.fee_request
        ):
            refresh_fee_request(self.target_fee_request)

    @staticmethod
    def get_fee_request(name):
        fee_request = frappe.get_doc("Fee Request", name)
        if fee_request.docstatus != 1:
            frappe.throw(_("Fee Request {0} must be submitted.").format(name))

        if fee_request.has_purchase_invoices():
            frappe.throw(
                _(
                    "Fee Request {0} is linked to Purchase Invoices. Record its payments with a Payment Entry against the invoice."
                ).format(get_link_to_form("Fee Request", name))
            )

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

    def validate_amount(self, fee_request, term):
        amount = flt(self.paid_amount)
        outstanding = flt(term.outstanding_amount)

        if self.payment_type == "Payment":
            self.validate_not_overpaid(amount, outstanding, term.academic_term)

        elif self.payment_type == "Refund" and amount > flt(term.paid_amount):
            frappe.throw(
                _("A refund cannot exceed the amount paid for {0} ({1}).").format(
                    term.academic_term, term.paid_amount
                )
            )

        elif self.payment_type == "Reduction" and amount > max(outstanding, 0):
            frappe.throw(
                _(
                    "A reduction cannot exceed the outstanding amount for {0} ({1})."
                ).format(term.academic_term, max(outstanding, 0))
            )

        elif self.payment_type == "Transfer":
            credit = max(-outstanding, 0)
            if amount > credit:
                frappe.throw(
                    _(
                        "Only an overpayment can be transferred. {0} has {1} available to transfer."
                    ).format(term.academic_term, credit)
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
                amount, flt(target_term.outstanding_amount), target_term.academic_term
            )

    def validate_not_overpaid(self, amount, outstanding, academic_term):
        if amount <= outstanding or self.allow_overpayment:
            return

        message = _(
            "{0} exceeds the outstanding amount for {1} ({2}). Tick Allow Overpayment if the school was really paid more."
        ).format(amount, academic_term, outstanding)

        # A draft can hold an overpayment for review; only submitting needs the tick.
        if self.docstatus == 1:
            frappe.throw(message)
        elif not self.flags.from_payment_import:
            frappe.msgprint(message, title=_("Overpayment"), indicator="orange")

    def validate_export_line(self):
        if not self.export_line:
            return

        line = next(
            (
                line
                for line in get_export_lines(self.fee_request)
                if line.name == self.export_line
            ),
            None,
        )
        if (
            self.payment_type != "Payment"
            or not line
            or line.academic_term != self.academic_term
            or line.status == "Withdrawn"
            or (line.status == "Settled" and line.settled_by != self.name)
        ):
            # The line was settled or withdrawn while this payment waited in draft.
            # The payment still counts; it just no longer settles that line.
            self.export_line = self.fee_request_export = None
            return

        self.fee_request_export = line.export
