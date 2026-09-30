# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class FeeRequest(Document):
    def before_save(self):
        if self.fee_components:
            total_amount = sum(
                [flt(component.amount) for component in self.fee_components]
            )
            self.total_amount = total_amount
            self.outstanding_amount = total_amount

    def on_submit(self):
        if self.request_type != "Fee Request":
            return

        self.create_purchase_invoice()

    def on_cancel(self):
        if self.payments and any(
            frappe.get_doc("Fee Request Payment", payment.fee_request_payment).docstatus
            == 1
            for payment in self.payments
        ):
            frappe.throw(
                "Cannot cancel Fee Request as there are submitted Fee Request Payment(s) linked to it. Cancel the linked Fee Request Payment(s) before cancelling this Fee Request."
            )

        self.cancel_purchase_invoice()

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

        invoice = frappe.get_doc(
            {
                "doctype": "Purchase Invoice",
                "supplier": self.official_school_name,
                "company": self.company,
                "posting_date": nowdate(),
                "bill_date": nowdate(),
                "bill_no": self.name,
                "update_stock": 0,
                "ignore_pricing_rule": 1,
                "items": items,
                "remarks": f"Against Fee Request {self.name} for {self.student_name}",
            }
        )
        invoice.flags.ignore_permissions = True
        invoice.set_missing_values()

        for invoice_item, component in zip(invoice.items, self.fee_components):
            invoice_item.qty = 1
            invoice_item.rate = flt(component.amount)

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


@frappe.whitelist()
def get_fee_structure_template(fee_structure_template):
    fee_component_doc = frappe.get_doc("Fee Structure", fee_structure_template)
    return fee_component_doc.components
