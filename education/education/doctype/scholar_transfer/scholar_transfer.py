# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ScholarTransfer(Document):
    def before_save(self):
        if self.from_school == self.to_school:
            frappe.throw(_("To School cannot be the same as From School."))

    def before_submit(self):
        if getdate(self.transfer_request_date) > getdate():
            frappe.throw(
                _("Scholar Transfer cannot be submitted before Transfer Request Date."),
                frappe.DocstatusTransitionError,
            )

    def on_submit(self):
        scholar = frappe.get_doc("Scholar", self.scholar)
        scholar = update_scholar_transfer_history(
            scholar, self.from_school, self.to_school, date=self.transfer_request_date
        )

        scholar.save(ignore_permissions=True)

    def on_cancel(self):
        scholar = frappe.get_doc("Scholar", self.scholar)
        scholar = update_scholar_transfer_history(
            scholar,
            self.from_school,
            self.to_school,
            date=self.transfer_request_date,
            cancel=True,
        )

        scholar.save(ignore_permissions=True)


def update_scholar_transfer_history(
    scholar, previous_school, current_school, date=None, cancel=False
):
    internal_transfer_history = {
        "previous_school": previous_school,
        "current_school": current_school,
        "status_at_transfer": scholar.status,
    }
    new_school = current_school if not cancel else previous_school
    setattr(scholar, "official_school_name", new_school)

    if internal_transfer_history and not cancel:
        internal_transfer_history["transfer_date"] = date
        scholar.append("scholar_transfer_details", internal_transfer_history)

    if cancel:
        delete_scholar_transfer_history(scholar, current_school)

    return scholar


def delete_scholar_transfer_history(scholar, current_school):
    for history in scholar.scholar_transfer_details:
        if history.current_school == current_school:
            scholar.remove(history)
            break

    return scholar
