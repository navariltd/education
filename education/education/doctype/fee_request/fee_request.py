# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions,
)
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate


class FeeRequest(Document):
    def before_save(self):
        if self.docstatus != 0:
            return

        if self.fee_components:
            total_amount = sum(
                [flt(component.amount) for component in self.fee_components]
            )
            self.total_amount = total_amount
            self.outstanding_amount = total_amount

    def on_submit(self):
        if self.request_type != "Fee Request":
            return

        if not self.should_create_purchase_invoice():
            return

        self.create_purchase_invoice()

    def on_cancel(self):
        self.ignore_linked_doctypes = ("Payment Entry",)
        self.validate_no_submitted_payments()
        self.cancel_allocated_payment_entries()
        self.cancel_purchase_invoice()

    def should_create_purchase_invoice(self):
        enabled = frappe.db.get_single_value(
            "Education Settings", "create_purchase_invoice_on_fee_request"
        )
        if enabled is None:
            return True
        return bool(cint(enabled))

    def validate_no_submitted_payments(self):
        if self.payments and any(
            payment.payment_type == "Fee Request Payment"
            and payment.payment
            and frappe.db.get_value("Fee Request Payment", payment.payment, "docstatus")
            == 1
            for payment in self.payments
        ):
            frappe.throw(
                "Cannot cancel Fee Request as there are submitted Fee Request Payment(s) linked to it. Cancel the linked Fee Request Payment(s) before cancelling this Fee Request."
            )

    def cancel_allocated_payment_entries(self):
        for allocation in get_purchase_invoice_payments(self.purchase_invoice):
            payment_entry = frappe.get_doc("Payment Entry", allocation.payment_entry)
            if payment_entry.docstatus != 1:
                continue

            payment_entry.flags.ignore_permissions = True
            payment_entry.cancel()

    def update_payment_amounts(self):
        total_paid = sum(flt(payment.paid_amount) for payment in self.payments)
        self.paid_amount = total_paid
        self.outstanding_amount = flt(self.total_amount) - total_paid

        if total_paid > 0 and self.outstanding_amount <= 0:
            self.payment_status = "Paid"
        elif total_paid > 0:
            self.payment_status = "Partially Paid"
        else:
            self.payment_status = "Unpaid"

    def sync_purchase_invoice_payments(self):
        for row in list(self.payments or []):
            if row.payment_type == "Payment Entry":
                self.remove(row)

        for allocation in get_purchase_invoice_payments(self.purchase_invoice):
            if not flt(allocation.paid_amount):
                continue
            self.append(
                "payments",
                {
                    "payment_type": "Payment Entry",
                    "payment": allocation.payment_entry,
                    "paid_amount": allocation.paid_amount,
                    "payment_date": allocation.posting_date,
                },
            )

        self.update_payment_amounts()

    def create_purchase_invoice(self):
        if not self.official_school_name:
            frappe.throw(
                "Official School Name is required to create a Purchase Invoice."
            )

        if not self.fee_components:
            frappe.throw(
                "Add at least one Fee Component before creating a Purchase Invoice."
            )

        items = []
        for row in self.fee_components:
            item_code = frappe.db.get_value("Fee Category", row.fees_category, "item")
            if not item_code:
                frappe.throw(
                    f"Fee Category {row.fees_category} has no linked Item. A Purchase Invoice cannot be created."
                )

            items.append(
                {
                    "item_code": item_code,
                    "qty": 1,
                    "rate": flt(row.amount),
                    "description": row.fees_category,
                }
            )

        dimensions = self.get_accounting_dimension_values()
        invoice = frappe.get_doc(
            {
                "doctype": "Purchase Invoice",
                "supplier": self.official_school_name,
                "company": self.company,
                "posting_date": nowdate(),
                "bill_date": nowdate(),
                # "bill_no": self.name,
                "update_stock": 0,
                "ignore_pricing_rule": 1,
                "items": items,
                "remarks": f"Against Fee Request {self.name} for {self.student_name}",
                **dimensions,
            }
        )
        invoice.flags.ignore_permissions = True
        invoice.set_missing_values()

        for fieldname, value in dimensions.items():
            invoice.set(fieldname, value)

        for invoice_item, component in zip(invoice.items, self.fee_components):
            invoice_item.qty = 1
            invoice_item.rate = flt(component.amount)
            self.set_accounting_dimensions(invoice_item, dimensions)

        for tax in invoice.get("taxes") or []:
            self.set_accounting_dimensions(tax, dimensions)

        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.db_set("purchase_invoice", invoice.name)

    def cancel_purchase_invoice(self):
        if not self.purchase_invoice:
            return

        invoice = frappe.get_doc("Purchase Invoice", self.purchase_invoice)
        if invoice.docstatus != 1:
            return

        invoice.flags.ignore_permissions = True
        invoice.cancel()

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


def update_fee_request_from_payment_entry(doc, method=None):
    if method == "on_cancel":
        doc.ignore_linked_doctypes = (*doc.ignore_linked_doctypes, "Payment Entry")

    invoices = set()
    for payment in (doc, doc.get_doc_before_save()):
        if not payment:
            continue
        for row in payment.get("references") or []:
            if row.reference_doctype == "Purchase Invoice" and row.reference_name:
                invoices.add(row.reference_name)

    if not invoices:
        return

    for name in frappe.get_all(
        "Fee Request",
        filters={"purchase_invoice": ["in", list(invoices)], "docstatus": 1},
        pluck="name",
    ):
        fee_request = frappe.get_doc("Fee Request", name)
        fee_request.flags.ignore_validate_update_after_submit = True
        fee_request.sync_purchase_invoice_payments()
        fee_request.save(ignore_permissions=True)


def get_purchase_invoice_payments(purchase_invoice):
    if not purchase_invoice:
        return []

    return frappe.db.sql(
        """
        SELECT pe.name AS payment_entry,
            pe.posting_date,
            SUM(per.allocated_amount) AS paid_amount
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
        WHERE pe.docstatus = 1
            AND per.reference_doctype = 'Purchase Invoice'
            AND per.reference_name = %s
        GROUP BY pe.name, pe.posting_date
        """,
        purchase_invoice,
        as_dict=True,
    )


@frappe.whitelist()
def get_fee_structure_template(fee_structure_template):
    fee_component_doc = frappe.get_doc("Fee Structure", fee_structure_template)
    return fee_component_doc.components
